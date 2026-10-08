import pytest
import sympy as sp

from picore.engine import evaluate
from picore.engine.local import plot_target
from picore.engine.parser import ParseError, parse_expr

x, y = sp.symbols("x y")


def pod(resp, title):
    return dict(resp.pods)[title]


@pytest.mark.parametrize("text, expected", [
    ("2x", 2 * x),
    ("2(x+1)", 2 * (x + 1)),
    ("(x+1)(x-1)", (x + 1) * (x - 1)),
    ("x^2", x ** 2),
    ("sin x", sp.sin(x)),
    ("sinx + cosx", sp.sin(x) + sp.cos(x)),
    ("2pi", 2 * sp.pi),
    ("π", sp.pi),
    ("e^(i pi)", -1),
    ("5!", 120),
    ("3(2+1)!", 18),
    ("log(8, 2)", 3),
    ("0.1 + 0.2", sp.Rational(3, 10)),
    ("1e3", 1000),
    ("√4", 2),
    ("xy", x * y),
])
def test_parse(text, expected):
    assert sp.simplify(parse_expr(text) - expected) == 0


@pytest.mark.parametrize("text", [
    "__import__('os')", "().__class__", "x.real", "lambda: 1", "open('f')",
    "9^9^9", "10000000000!", "what is love", "", "1" * 400, "x = = 2",
])
def test_rejects_unsafe_or_garbage(text):
    with pytest.raises(ParseError):
        parse_expr(text)


def test_arithmetic():
    r = evaluate("2+2")
    assert r.source == "local" and pod(r, "Result") == "4"


def test_linear_equation():
    assert pod(evaluate("2x+3=7"), "Solution") == "x = 2"


def test_system():
    assert pod(evaluate("solve x+y=3 and x-y=1"), "Solution") == "x = 2,  y = 1"


def test_quadratic_complex_roots():
    sols = pod(evaluate("x^2 = -1"), "Solutions")
    assert "x = i" in sols and "x = -i" in sols


def test_derivative_and_integral():
    assert pod(evaluate("d/dx x^3"), "Derivative") == "3x^2"
    assert pod(evaluate("integrate x^2 from 0 to 3"), "Definite integral") == "9"
    assert pod(evaluate("integral of 1/x"), "Indefinite integral") == "ln(x) + C"


def test_limit():
    assert pod(evaluate("limit sin(x)/x as x->0"), "Limit") == "1"


def test_factorization_pod():
    assert pod(evaluate("5!"), "Prime factorization") == "2^3 × 3 × 5"


def test_word_question_without_key_is_friendly_error():
    r = evaluate("distance to the moon", wolfram_app_id=None)
    assert r.source == "error" and "Tip" in dict(r.pods)


def test_plot_targets():
    assert plot_target("y = sin(x)/x") == sp.sin(x) / x
    assert plot_target("x^2 - 4") == x ** 2 - 4
    assert plot_target("2+2") is None
    assert plot_target("x + y") is None


# ---- honesty: never claim "no solutions" without proof -------------------------

def test_quintic_gets_numerical_roots_not_no_solutions():
    r = evaluate("x^5 - x - 1 = 0")
    pods = dict(r.pods)
    assert "Solutions (numerical)" in pods and "1.167303978" in pods["Solutions (numerical)"]
    assert "not a proof" in pods["Verification"]


def test_no_solutions_only_when_proved():
    assert "(proved)" in dict(evaluate("exp(x) = 0").pods)["Solutions"]
    assert "(proved)" in dict(evaluate("x = x + 1").pods)["Solutions"]


def test_transcendental_equation_scanned_numerically():
    pods = dict(evaluate("sin(x) = x/2").pods)
    assert "1.895494267" in pods["Solutions (numerical)"]
    assert "not listed" in pods["Why numerical?"]


def test_solutions_are_verified_by_substitution():
    assert dict(evaluate("x^2 + x + 1 = 0").pods)["Verification"].startswith("Proved")


def test_derivative_and_integrals_carry_numerical_verification():
    assert "finite difference" in dict(evaluate("d/dx sin(x^2)").pods)["Verification"]
    assert "quadrature" in dict(evaluate("integrate x^2 from 0 to 3").pods)["Verification"]
    assert "antiderivative" in dict(evaluate("integral of x e^x").pods)["Verification"]


# ---- reasoning commands -----------------------------------------------------------

def test_equiv_command():
    pods = dict(evaluate("equiv (x^2-1)/(x-1) ; x+1").pods)
    assert pods["Verdict"] == "Equivalent, with a domain restriction (x ≠ 1)"
    assert dict(evaluate("is (x+1)^2 = x^2+2x+1").pods)["Verdict"] == "Equivalent"
    assert dict(evaluate("compare sqrt(x^2) with x").pods)["Verdict"] == "Not equivalent"


def test_derive_command():
    pods = evaluate("derive (x+1)^2 : expand, d/dx, sub x=1").pods
    assert [t.split("·")[1].split("(")[1].rstrip(")") for t, _ in pods[1:]] == ["verified symbolically"] * 3
    assert pods[-1][1].startswith("4")
