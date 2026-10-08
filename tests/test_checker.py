import pytest

from picore.engine.checker import check
from picore.engine.parser import ParseError


def verdicts(text):
    return [t.split(" · ")[1] for t, _ in check(text)[2:]]


def test_all_correct():
    assert verdicts("check 2(x+3)=10 -> 2x+6=10 -> 2x=4 -> x=2") == ["correct"] * 3
    assert check("check 2x=4 -> x=2")[0][1].startswith("All 2 steps check out")


def test_arithmetic_slip():
    pods = check("check 2(x+3)=10 -> 2x+6=10 -> 2x=4 -> x=3")
    assert verdicts("check 2(x+3)=10 -> 2x+6=10 -> 2x=4 -> x=3") == ["correct", "correct", "mistake here"]
    assert "step 4" in pods[0][1]


def test_lost_negative_root():
    _, why = check("check x^2=4 -> x=2")[2]
    assert "A square root has two signs" in why and "x = -2 was lost" in why


def test_or_answers():
    assert verdicts("check x^2-5x+6=0 -> (x-2)(x-3)=0 -> x=2 or x=3") == ["correct", "correct"]


def test_squaring_adds_extraneous_root():
    title, why = check("check sqrt(x)=x-2 -> x=(x-2)^2")[2]
    assert title.endswith("check needed")
    assert "x = 1 is extraneous" in why and "Squaring both sides" in why


def test_expression_rewrites():
    assert verdicts("check (x+1)^2 -> x^2+2x+1") == ["correct"]
    assert verdicts("check (a+b)^2 -> a^2+b^2") == ["mistake here"]


def test_mixed_kinds_are_flagged_unsure():
    assert verdicts("check x+1=2 -> x+1") == ["couldn't check"]


def test_needs_two_steps():
    with pytest.raises(ParseError):
        check("check x=1")
