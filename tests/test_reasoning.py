"""Equivalence engine, numerical verification and verified derivations."""
import pytest
import sympy as sp

from picore.reasoning import numeric
from picore.reasoning.derivation import CHECKED, FAILED, PROVED, derive, parse_label
from picore.reasoning.equivalence import CONDITIONAL, EXACT, NOT, NUMERIC, compare

x, y = sp.symbols("x y")


# ---- equivalence ----------------------------------------------------------------

@pytest.mark.parametrize("a, b", [
    ("(x+1)^2", "x^2+2x+1"),
    ("sin(x)^2 + cos(x)^2", "1"),
    ("tan(x)", "sin(x)/cos(x)"),
    ("2(x+3)", "2x+6"),
])
def test_exact(a, b):
    assert compare(a, b).verdict == EXACT


@pytest.mark.parametrize("a, b, restriction", [
    ("(x^2-1)/(x-1)", "x+1", "x ≠ 1"),
    ("x/x", "1", "x ≠ 0"),
    ("1/(1/x)", "x", "x ≠ 0"),
    ("ln(x^2)", "2ln(x)", "x ∉ (-∞, 0)"),
    ("exp(ln(x))", "x", "x ∉ (-∞, 0]"),
])
def test_conditional_equivalence_reports_the_restriction(a, b, restriction):
    r = compare(a, b)
    assert r.verdict == CONDITIONAL and r.restrictions == [restriction]


@pytest.mark.parametrize("a, b", [("(a+b)^2", "a^2+b^2"), ("sqrt(x^2)", "x"), ("sin(2x)", "2sin(x)")])
def test_not_equivalent_has_counterexample(a, b):
    r = compare(a, b)
    assert r.verdict == NOT and r.evidence.counterexample


def test_numeric_only_is_labelled_as_evidence():
    r = compare("ln(x y)", "ln(x) + ln(y)")
    assert r.verdict == NUMERIC
    assert any("not a proof" in line for line in r.reasons)
    assert r.right_undefined_more            # ln x + ln y needs x, y > 0; ln(xy) only needs xy > 0


# ---- numerical verification ------------------------------------------------------

def test_derivative_check_passes_and_fails():
    f = sp.sin(x ** 2)
    assert numeric.check_derivative(f, 2 * x * sp.cos(x ** 2), x).passed
    bad = numeric.check_derivative(f, sp.cos(x ** 2), x)
    assert bad.status == "failed" and bad.counterexample


def test_antiderivative_and_definite_integral_checks():
    assert numeric.check_antiderivative(x ** 3 / 3, x ** 2, x).passed
    assert numeric.check_definite_integral(x ** 2, x, 0, 3, 9).passed
    assert numeric.check_definite_integral(x ** 2, x, 0, 3, 10).status == "failed"


def test_root_check():
    assert numeric.check_roots(x ** 2 - 4, x, [2, -2]).passed
    assert numeric.check_roots(x ** 2 - 4, x, [3]).status == "failed"


def test_sampling_respects_domain():
    pts = numeric.sample_points({x}, 10, conditions=[x > 0])
    assert pts and all(p[x] > 0 for p in pts)


# ---- verified derivations ------------------------------------------------------

def test_derive_chain_is_verified():
    steps = derive("(x+1)^2", ["expand", "d/dx", "sub x=1"])
    assert [s.value for s in steps] == [x ** 2 + 2 * x + 1, 2 * x + 2, 4]
    assert all(s.verification.status == PROVED for s in steps)


def test_derive_integrate_adds_constant():
    steps = derive("x^2", ["integrate"])
    assert steps[0].value == x ** 3 / 3 + sp.Symbol("C")
    assert steps[0].verification.status == PROVED


def test_labels():
    assert parse_label("d/dt")[1] == "t"
    assert parse_label("sub x=2")[1] == "x=2"
    with pytest.raises(ValueError):
        parse_label("teleport")


def test_missing_constant_of_integration_is_a_failure():
    t, _ = parse_label("integrate")
    assert t.verify(x ** 2, x ** 3 / 3, "").status == FAILED
    assert t.verify(x ** 2, x ** 3 / 3 + sp.Symbol("C"), "").status in (PROVED, CHECKED)
