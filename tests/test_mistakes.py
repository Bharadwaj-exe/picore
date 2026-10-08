"""Mistake Detective 2.0: every rule must name the misconception for its classic error.

Each case is (working, expected rule category, text that must appear in the correction).
"""
import pytest

from picore.engine.checker import check
from picore.reasoning.mistakes import RULES

CASES = [
    # spec example: the first step is valid, the second is not
    ("check x^2-5x+6=0 -> x^2 = 5x-6 -> x = 5 ± √6", "incorrect rearrangement", "x = 2 or x = 3"),
    ("check (x+3)^2 -> x^2+9", "incorrect expansion", "x^2 + 6x + 9"),
    ("check 2(x+3) -> 2x+3", "incorrect distribution", "2x + 6"),
    ("check -(x-4) -> -x-4", "sign error", "4 - x"),
    ("check 5 - (x + 2) -> 5 - x + 2", "sign error", "3 - x"),
    ("check (x+6)/x -> 6", "invalid cancellation", "1 + 6/x"),
    ("check (2x+4)/2 -> x+4", "invalid cancellation", "x + 2"),
    ("check 1/x + 1/y -> 2/(x+y)", "fractions", "(x + y)/(x·y)"),
    ("check x^2 * x^3 -> x^6", "exponent rules", "x^5"),
    ("check (x^2)^3 -> x^5", "exponent rules", "x^6"),
    ("check x^-2 -> -x^2", "exponent rules", "1/x^2"),
    ("check (2x)^3 -> 2x^3", "exponent rules", "8x^3"),
    ("check e^(a+b) -> e^a + e^b", "exponent rules", "e^a · e^b"),
    ("check ln(x y) -> ln(x) ln(y)", "logarithm rules", "ln(x) + ln(y)"),
    ("check ln(x^3) -> ln(x)^3", "logarithm rules", "3ln(x)"),
    ("check sqrt(x^2+9) -> x+3", "function rules", ""),
    ("check sin(2x) -> 2sin(x)", "function rules", "2sin(x)·cos(x)"),
    ("check x + 5 = 12 -> x = 12 + 5", "sign error", "x = 7"),
    ("check 3x + 4 = 2x + 9 -> x + 4 = 9 + 2x", "unbalanced operation", "x + 4 = 9"),
    ("check x^2 = 3x -> x = 3", "missed roots", "x = 0 or x = 3"),
    ("check x^2 = 4 -> x = 2", "missed roots", "x = -2 or x = 2"),
    ("check (x-1)^2 = 9 -> x - 1 = 3", "missed roots", "x = -2 or x = 4"),
    ("check sqrt(x) = x - 2 -> x = (x-2)^2", "extraneous roots", "x = 4"),
    ("check x^2-5x+6 -> (x-2)(x+3)", "incorrect factorisation", "(x - 3)·(x - 2)"),
    ("check (x+2)(x+3) -> x^2+5x+5", "incorrect expansion", "x^2 + 5x + 6"),
    ("check d/dx(x^3) -> 3x^3", "power rule", "3x^2"),
    ("check d/dx(x^5) -> x^4", "power rule", "5x^4"),
    ("check d/dx(x^2 sin(x)) -> 2x cos(x)", "product rule", "x^2·cos(x) + 2x·sin(x)"),
    ("check d/dx(sin(x)/x) -> cos(x)", "quotient rule", "x^2"),
    ("check d/dx(sin(3x)) -> cos(3x)", "chain rule", "3cos(3x)"),
    ("check d/dx((2x+1)^3) -> 3(2x+1)^2", "chain rule", "6(2x + 1)^2"),
    ("check d/dx(cos(x)) -> sin(x)", "trig derivatives", "-sin(x)"),
    ("check d/dx(2^x) -> x 2^(x-1)", "exponentials", "2^x·ln(2)"),
    ("check x^2 -> [d/dx] x", "power rule", "2x"),
    ("check sin(30) -> 1/2", "degrees vs radians", "radians"),
    ("check x^2 + 3x + 2 -> x^2 + 2", "dropped term", "nothing removed"),
]


@pytest.mark.parametrize("working, category, correct", CASES, ids=[c[1] + ":" + c[0][6:30] for c in CASES])
def test_diagnosis(working, category, correct):
    pods = check(working)
    bad = [(t, body) for t, body in pods if " · mistake here" in t or " · check needed" in t]
    assert bad, f"no step was flagged: {pods}"
    body = bad[0][1]
    assert category in body.split("\n")[1].lower(), body
    if correct:
        assert correct in body, body


def test_valid_steps_are_not_flagged():
    for working in ["check 2x+4 = 10 -> x+2 = 5 -> x = 3",
                    "check (x+1)^2 -> x^2+2x+1",
                    "check x^2-5x+6=0 -> (x-2)(x-3)=0 -> x=2 or x=3",
                    "check x^2 = 9 -> x = ±3",
                    "check x^2 = 4 -> x = (0 ± √16)/2",
                    "check (x+1)^2 -> [expand] x^2+2x+1 -> [d/dx] 2x+2 -> [sub x=1] 4"]:
        verdicts = [t.split(" · ")[1] for t, _ in check(working)[2:]]
        assert set(verdicts) == {"correct"}, (working, check(working))


def test_conditional_step_is_correct_but_states_the_restriction():
    _, body = check("check (x^2-1)/(x-1) -> x+1")[2]
    assert "x ≠ 1" in body


def test_unknown_mistake_still_reported_with_evidence_not_a_guess():
    title, body = check("check x^3 + 1 -> x^2 + 7")[2]
    assert title.endswith("mistake here") and "disagree at" in body


def test_final_answer_compared_with_original_problem():
    verdict = check("check sqrt(x) = x - 2 -> x = (x-2)^2 -> x^2-5x+4 = 0 -> x = 1 or x = 4")[0][1]
    assert "original equation's solutions are x = 4" in verdict


def test_every_rule_has_id_and_category():
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids)) >= 15
    assert all(r.category for r in RULES)
