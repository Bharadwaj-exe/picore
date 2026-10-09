import pytest
import sympy as sp

from picore.engine.parser import ParseError
from picore.explore import analyze, make_experiment
from picore.reasoning.numeric import real_roots


def run(text, **values):
    exp = make_experiment(text)
    exp.values = {sp.Symbol(k): v for k, v in values.items()}
    return analyze(exp)


def facts(result):
    return {f.label: f.value for f in result.facts}


def test_parameters_detected():
    exp = make_experiment("y = a x^2 + b x + c")
    assert [p.name for p in exp.params] == ["a", "b", "c"]


@pytest.mark.parametrize("text", ["2x + 1", "a + b", "a b c d f x"])
def test_bad_experiments(text):
    with pytest.raises(ParseError):
        make_experiment(text)


def test_quadratic_two_roots():
    r = run("a x^2 + b x + c", a=1, b=-5, c=6)
    f = facts(r)
    assert r.kind == "Quadratic" and f["Roots"] == "x = 2,  x = 3"
    assert f["Vertex"] == "(2.5, -0.25)" and f["Axis of symmetry"].endswith("2.5")
    assert r.vlines == [2.5]


def test_quadratic_no_real_roots_explains_why():
    r = run("a x^2 + b x + c", a=1, b=0, c=1)
    disc = next(x for x in r.facts if x.label == "Discriminant")
    assert disc.value.endswith("-4") and "no real roots" in disc.why
    assert facts(r)["Roots"] == "x = i,  x = -i"


def test_quadratic_degenerates_to_line():
    r = run("a x^2 + b x + c", a=0, b=2, c=-4)
    assert facts(r)["Shape"] == "a straight line"


def test_sinusoid():
    f = facts(run("A sin(B x + C) + D", A=2, B=3, C=1, D=0.5))
    assert f["Amplitude"] == "2" and f["Period"].endswith("2.094") and f["Midline"] == "y = 0.5"


def test_generic_finds_roots_numerically_and_skips_poles():
    f = facts(run("a e^(b x) - 2", a=1, b=1))
    assert "0.6931" in f["Real roots found in [-10, 10]"]
    assert real_roots(1 / sp.Symbol("x"), sp.Symbol("x"), -5, 5) == []   # sign change at a pole is not a root


def test_linear_has_single_intercept_fact():
    r = run("m x + c", m=2, c=-3)
    assert [f.label for f in r.facts].count("y-intercept") == 1
