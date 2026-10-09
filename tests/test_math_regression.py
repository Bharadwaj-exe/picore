"""Mathematical regression suite: answers Pi Core gives must stay mathematically right,
and 'unknown / not found' must never turn into 'false / no solutions'."""
import pytest
import sympy as sp

from picore.engine import evaluate
from picore.reasoning.equivalence import CONDITIONAL, EXACT, NOT, NUMERIC, UNKNOWN, compare

x, y = sp.symbols("x y")


def pods(q):
    r = evaluate(q)
    assert r.source != "error", r.pods
    return dict(r.pods)


# ---- algebra ------------------------------------------------------------------------------

@pytest.mark.parametrize("q, title, expected", [
    ("expand (x+1)^3", "Expanded", "x^3 + 3x^2 + 3x + 1"),
    ("factor x^4 - 1", "Factored", "(x - 1)·(x + 1)·(x^2 + 1)"),
    ("simplify (x^2-1)/(x-1)", "Simplified", "x + 1"),
    ("1/2 + 1/3", "Result", "5/6"),
    ("2^10", "Result", "1024"),
    ("sqrt(50)", "Result", "5√2"),
    ("cbrt(27)", "Result", "3"),
    ("ln(e^3)", "Result", "3"),
    ("log10(1000)", "Result", "3"),
    ("log(8, 2)", "Result", "3"),
    ("-2^2", "Result", "-4"),            # power binds tighter than unary minus
    ("2^3^2", "Result", "512"),          # right-associative
    ("(-2)^2", "Result", "4"),
    ("2(3+4)", "Result", "14"),          # implicit multiplication
    ("5!", "Result", "120"),
    ("0!", "Result", "1"),
    ("1e5", "Result", "100000"),
    ("0.1 + 0.2", "Result", "3/10"),     # exact rationals, no float error
    ("sqrt(-4)", "Result", "2i"),
    ("e^(i pi)", "Result", "-1"),
])
def test_algebra_values(q, title, expected):
    assert pods(q)[title] == expected


@pytest.mark.parametrize("q", ["1/0", "0/0", "ln(0)", "(-3)!", "tan(pi/2)", "inf - inf"])
def test_undefined_values_are_reported_as_undefined(q):
    assert pods(q)["Result"].startswith("Undefined")


# ---- equations ------------------------------------------------------------------------------

@pytest.mark.parametrize("q, expected", [
    ("2x + 3 = 7", "x = 2"),
    ("x^2 - 5x + 6 = 0", "x = 2\nx = 3"),
    ("x^2 - 4x + 4 = 0", "x = 2"),                 # repeated root listed once
    ("x^3 - 3x + 2 = 0", "x = -2\nx = 1"),         # double root at 1
    ("x^4 - 5x^2 + 4 = 0", "x = -2\nx = -1\nx = 1\nx = 2"),
    ("x^2 + 1 = 0", "x = -i\nx = i"),
    ("(x-1)(x-1.0001) = 0", "x = 1\nx = 10001/10000"),   # closely spaced, exact
    ("a x = b", "x = b/a"),
    ("ln(x) = 0", "x = 1"),
    ("sqrt(x) = x - 2", "x = 4"),                  # the extraneous x = 1 is NOT listed
    ("exp(x) = x + 1", "x = 0"),                   # root without a sign change
])
def test_equation_solutions(q, expected):
    p = pods(q)
    sol = p.get("Solution") or p.get("Solutions")
    assert sol == expected
    assert p["Verification"].startswith("Proved")


@pytest.mark.parametrize("q", ["sqrt(x) = -1", "1/(x-1) = 0", "(x^2-1)/(x-1) = 2", "x = x + 1", "exp(x) = 0"])
def test_no_solution_claims_are_proved(q):
    assert "(proved)" in pods(q)["Solutions"]


def test_inconsistent_system_is_proved_empty():
    assert "contradict" in pods("solve x+y=1 and x+y=2")["Solutions"]


def test_identity_is_not_reported_as_no_solutions():
    assert "Every value of x" in pods("x = x")["Solutions"]


@pytest.mark.parametrize("q, families", [
    ("sin(x) = 1/2", ["x = 2π·n + π/6", "x = 2π·n + 5π/6"]),
    ("tan(x) = 1", ["x = π·n + π/4"]),
    ("2sin(x) = 1", ["x = 2π·n + π/6", "x = 2π·n + 5π/6"]),
])
def test_periodic_equations_give_all_solutions(q, families):
    text = pods(q)["All real solutions"]
    assert all(f in text for f in families) and "any integer" in text


def test_periodic_equation_without_real_solutions():
    assert "no real solutions (proved)" in pods("sin(x) = 2")["Real solutions"]


@pytest.mark.parametrize("q, roots", [
    ("x^5 - x - 1 = 0", ["1.167303978"]),
    ("sin(x) = x/2", ["-1.895494267", "1.895494267"]),
    ("cos(x) + x^2/2 = 1", ["x ≈ 0"]),             # tangential root (no sign change)
])
def test_numerical_roots_are_labelled_and_never_claimed_complete(q, roots):
    p = pods(q)
    text = p["Solutions (numerical)"]
    assert all(r in text for r in roots)
    assert "Why numerical?" in p and "not a proof" in p["Verification"]


def test_numerical_search_failure_is_not_no_solutions():
    p = pods("exp(x) = -x^2 - 5")          # truly no real roots, but the scan cannot prove it
    assert "not a proof" in p["Solutions"] and "(proved)" not in p["Solutions"]


# ---- calculus ------------------------------------------------------------------------------

@pytest.mark.parametrize("q, expected", [
    ("d/dx x^3", "3x^2"),
    ("d/dx x^2 sin(x)", "x·(x·cos(x) + 2sin(x))"),             # product rule
    ("d/dx sin(x)/x", "(x·cos(x) - sin(x))/x^2"),              # quotient rule
    ("d/dx sin(x^2)", "2x·cos(x^2)"),                          # chain rule
    ("d/dx exp(sin(x))", "exp(sin(x))·cos(x)"),
    ("d/dx abs(x)", "sign(x)"),                                # real-variable derivative
    ("d/dx x^x", "x^x·(ln(x) + 1)"),
])
def test_derivatives(q, expected):
    p = pods(q)
    assert p["Derivative"] == expected
    assert "finite difference" in p["Verification"]


def test_second_derivative_at_a_corner_is_not_a_delta():
    assert "jumps" in pods("d/dx abs(x)")["Second derivative"]


@pytest.mark.parametrize("q, expected", [
    ("integrate x^2", "x^3/3 + C"),
    ("integrate sin(x)^2 from 0 to pi", "π/2"),
    ("integrate 1/x^2 from 1 to oo", "1"),
    ("integrate 1/sqrt(x) from 0 to 1", "2"),                  # improper but convergent
])
def test_integrals(q, expected):
    p = pods(q)
    assert (p.get("Indefinite integral") or p.get("Definite integral")) == expected


def test_divergent_integral_is_reported():
    assert "Does not converge" in pods("integrate 1/x from -1 to 1")["Definite integral"]


def test_ln_antiderivative_has_domain_note():
    assert "ln|u|" in pods("integrate 1/x")["Domain note"]


@pytest.mark.parametrize("q, expected", [
    ("limit sin(x)/x as x->0", "1"), ("limit (1+1/x)^x as x->oo", "e"), ("limit x sin(1/x) as x->0", "0"),
])
def test_limits(q, expected):
    assert pods(q)["Limit"] == expected


# ---- domains and equivalence ----------------------------------------------------------------

@pytest.mark.parametrize("a, b, verdict, right_loses", [
    ("x/x", "1", CONDITIONAL, False),
    ("(x^2-1)/(x-1)", "x+1", CONDITIONAL, False),
    ("sqrt(x)^2", "x", CONDITIONAL, False),
    ("x", "sqrt(x)^2", CONDITIONAL, True),
    ("ln(x^2)", "2ln(x)", CONDITIONAL, True),
    ("1/sqrt(x)", "sqrt(x)/x", EXACT, False),
    ("1/(x-1)", "-1/(1-x)", EXACT, False),
    ("x^(-2) y^3", "y^3/x^2", EXACT, False),
    ("sqrt(x^2)", "x", NOT, False),
    ("ln(x y)", "ln(x) + ln(y)", NUMERIC, True),
    ("(x^a)^b", "x^(a b)", NUMERIC, False),
])
def test_domain_sensitive_equivalence(a, b, verdict, right_loses):
    r = compare(a, b)
    assert r.verdict == verdict, r.reasons
    assert r.right_undefined_more == right_loses


def test_constants_are_compared_at_high_precision():
    assert compare("e^(pi sqrt(163))", "640320^3 + 744").verdict == NOT


def test_unknown_stays_distinct_from_false():
    # the parser rejects unknown words, so the engine says it cannot answer offline (never 'false')
    r = evaluate("is the riemann hypothesis true")
    assert r.source == "error" and "offline" in r.pods[0][0].lower()
    assert UNKNOWN != NOT
