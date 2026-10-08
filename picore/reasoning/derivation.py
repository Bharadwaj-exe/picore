"""Verified transformations: the same registry checks a step the user labels ([expand], [d/dx]…)
and generates steps for the ``derive`` command.

Each transform knows how to APPLY itself and how to VERIFY a claimed result independently:
equality-preserving rules are checked with the equivalence engine; d/dx with finite
differences; integration by differentiating back; substitution by direct evaluation.
A step whose result can't be justified is reported as unverified. Nothing is invented.
"""
import re
from dataclasses import dataclass

import sympy as sp

from . import numeric
from .equivalence import EXACT, CONDITIONAL, NUMERIC, NOT, compare

PROVED, CHECKED, FAILED, UNVERIFIED = "proved", "checked", "failed", "unverified"
STATUS_TEXT = {
    PROVED: "verified symbolically",
    CHECKED: "checked numerically (evidence, not proof)",
    FAILED: "does not follow",
    UNVERIFIED: "could not be verified",
}


@dataclass
class Verification:
    status: str
    detail: str = ""


@dataclass
class Transform:
    name: str
    describe: str
    apply: object          # (sympy_value, arg) -> sympy_value
    verify: object         # (prev_value, claimed_value, arg) -> Verification


def _equality_preserving(prev, claimed, _arg):
    r = compare(prev, claimed)
    if r.verdict in (EXACT, CONDITIONAL):
        extra = f" (valid where {', '.join(r.restrictions)})" if r.restrictions else ""
        return Verification(PROVED, "Equal to the previous step" + extra + ".")
    if r.verdict == NUMERIC:
        return Verification(CHECKED, r.reasons[-1])
    if r.verdict == NOT:
        return Verification(FAILED, r.reasons[-1])
    return Verification(UNVERIFIED, "Couldn't decide whether this equals the previous step.")


def _var(expr, arg):
    if arg:
        return sp.Symbol(arg)
    syms = sorted(expr.free_symbols, key=lambda s: s.name)
    return sp.Symbol("x") if not syms or sp.Symbol("x") in syms else syms[0]


def _verify_derivative(prev, claimed, arg):
    var = _var(prev, arg)
    exact = sp.diff(prev, var)
    if sp.simplify(exact - claimed) == 0:
        ev = numeric.check_derivative(prev, claimed, var)
        note = f" Independently: {ev.summary()}." if ev.status != "inconclusive" else ""
        return Verification(PROVED, f"Matches d/d{var} computed symbolically.{note}")
    ev = numeric.check_derivative(prev, claimed, var)
    if ev.status == "failed":
        return Verification(FAILED, ev.summary())
    if ev.passed:
        return Verification(CHECKED, ev.summary())
    return Verification(UNVERIFIED, "Couldn't evaluate the derivative at test points.")


def _integration_constant(expr):
    return [s for s in expr.free_symbols if s.name in ("C", "c", "K", "k")]


def _verify_integral(prev, claimed, arg):
    var = _var(prev, arg)
    consts = _integration_constant(claimed)
    body = claimed.subs({c: 0 for c in consts})
    if sp.simplify(sp.diff(body, var) - prev) == 0:
        if not consts:
            return Verification(FAILED, "The antiderivative is right, but the constant of integration (+ C) is missing.")
        return Verification(PROVED, f"Differentiating it gives back {_fmt(prev)}.")
    ev = numeric.check_antiderivative(body, prev, var)
    if ev.status == "failed":
        return Verification(FAILED, "Differentiating this does not give back the integrand: " + ev.summary())
    if ev.passed:
        return Verification(CHECKED, ev.summary())
    return Verification(UNVERIFIED, "Couldn't check this antiderivative.")


def _parse_sub(arg):
    m = re.match(r"^\s*([A-Za-z])\s*=\s*(.+)$", arg or "")
    if not m:
        raise ValueError("Write substitutions like [sub x=2]")
    from ..engine.parser import parse_expr
    return sp.Symbol(m.group(1)), parse_expr(m.group(2))


def _apply_sub(value, arg):
    var, val = _parse_sub(arg)
    return value.subs(var, val)


def _verify_sub(prev, claimed, arg):
    expected = sp.simplify(_apply_sub(prev, arg))
    if sp.simplify(expected - claimed) == 0:
        return Verification(PROVED, f"Substituting gives {_fmt(expected)}.")
    return Verification(FAILED, f"Substituting gives {_fmt(expected)}, not {_fmt(claimed)}.")


def _fmt(e):
    from ..engine.local import fmt
    return fmt(e)


def _integrate(value, arg):
    var = _var(value, arg)
    result = sp.integrate(value, var)
    if result.has(sp.Integral):
        raise ValueError("No closed-form antiderivative found")
    return result + sp.Symbol("C")


TRANSFORMS = {}


def _add(names, transform):
    for n in names:
        TRANSFORMS[n] = transform


_add(["expand"], Transform("expand", "multiply out", lambda v, a: sp.expand(v), _equality_preserving))
_add(["factor", "factorise", "factorize"], Transform("factor", "factorise", lambda v, a: sp.factor(v), _equality_preserving))
_add(["simplify"], Transform("simplify", "simplify", lambda v, a: sp.simplify(v), _equality_preserving))
_add(["rearrange", "move", "collect", "combine", "cancel"],
     Transform("rearrange", "rewrite", lambda v, a: v, _equality_preserving))
_add(["d/dx", "diff", "differentiate", "derivative"],
     Transform("d/dx", "differentiate", lambda v, a: sp.diff(v, _var(v, a)), _verify_derivative))
_add(["integrate", "int", "∫", "antiderivative"],
     Transform("integrate", "integrate", _integrate, _verify_integral))
_add(["sub", "substitute", "let", "eval", "evaluate"],
     Transform("substitute", "substitute", _apply_sub, _verify_sub))


def parse_label(label):
    """'d/dt' -> (transform, 't'), 'sub x=2' -> (transform, 'x=2'), 'expand' -> (transform, '')."""
    label = label.strip()
    m = re.match(r"^d/d([A-Za-z])$", label)
    if m:
        return TRANSFORMS["d/dx"], m.group(1)
    word, _, rest = label.partition(" ")
    t = TRANSFORMS.get(word.lower())
    if t is None:
        raise ValueError(f"Unknown step rule '[{label}]'. Known: expand, factor, simplify, rearrange, "
                         f"d/dx, integrate, sub x=…")
    if t.name == "d/dx":
        return t, rest.strip() or ""
    return t, rest.strip()


@dataclass
class DerivedStep:
    rule: str
    value: object
    verification: Verification


def derive(start_text, rules):
    """Apply ``rules`` (e.g. ['expand', 'd/dx', 'sub x=1']) in order, verifying each result."""
    from ..engine.parser import parse_expr
    value = parse_expr(start_text)
    steps = []
    for label in rules:
        transform, arg = parse_label(label)
        new = transform.apply(value, arg)
        # verified independently of how it was produced
        steps.append(DerivedStep(f"{transform.name} {arg}".strip(), new, transform.verify(value, new, arg)))
        value = new.subs(sp.Symbol("C"), 0) if transform.name == "integrate" else new   # carry on without + C
    return steps
