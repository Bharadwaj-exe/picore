"""Numerical verification: independent, evidence-only checks of symbolic results.

Every function here returns ``Evidence``. Passing numerical tests is EVIDENCE,
not proof: a finite number of sample points can never establish an identity.
Callers must present it that way ("checked at 8 points"), never as "proved".

Arithmetic is done with mpmath at 30 significant digits via SymPy's ``evalf``,
so finite-difference and rounding error stay far below the tolerances used.
"""
import random
from dataclasses import dataclass, field

import sympy as sp

DIGITS = 30
REL_TOL = 1e-8


@dataclass
class Evidence:
    status: str                    # "passed" | "failed" | "inconclusive"
    tested: int = 0                # points where both sides could be evaluated
    method: str = ""               # what was compared, in words
    counterexample: dict = field(default_factory=dict)   # {symbol: value} where it failed
    values: tuple = ()             # (left, right) at the counterexample

    @property
    def passed(self):
        return self.status == "passed"

    def summary(self):
        if self.status == "passed":
            return f"{self.method}: agreed at {self.tested} test points (numerical evidence, not a proof)"
        if self.status == "failed":
            where = ", ".join(f"{k} = {v}" for k, v in self.counterexample.items()) or "a test point"
            a, b = (_short(v) for v in self.values)
            return f"{self.method}: disagree at {where} ({a} vs {b})"
        return f"{self.method}: not enough valid test points"


def _short(z):
    z = complex(z)
    if abs(z.imag) < 1e-12:
        return format(z.real, ".6g")
    return f"{z.real:.4g}{z.imag:+.4g}i"


def _value(expr, point):
    """Evaluate to a Python complex, or None if undefined / infinite at ``point``."""
    try:
        v = sp.N(expr.subs(point), DIGITS)
        if v.has(sp.zoo, sp.oo, -sp.oo, sp.nan) or not v.is_number:
            return None
        z = complex(v)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if z != z or abs(z) == float("inf"):
        return None
    return z


def close(a, b, tol=REL_TOL):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def sample_points(symbols, n=10, seed=7, conditions=()):
    """Deterministic pseudo-random rational test points, skipping points that violate
    ``conditions`` (SymPy relationals, e.g. x - 1 ≠ 0)."""
    rng = random.Random(seed)
    symbols = sorted(symbols, key=lambda s: s.name)
    points, attempts = [], 0
    while len(points) < n and attempts < n * 20:
        attempts += 1
        point = {s: sp.Rational(rng.randint(-97, 97), rng.randint(1, 13)) for s in symbols}
        try:
            if all(bool(c.subs(point)) for c in conditions):
                points.append(point)
        except (TypeError, ValueError):
            continue
    return points


def agree(a, b, symbols=None, n=10, conditions=(), method="Values compared"):
    """Compare two expressions numerically at sample points where both are defined."""
    symbols = symbols if symbols is not None else (a.free_symbols | b.free_symbols)
    if not symbols:
        va, vb = _value(a, {}), _value(b, {})
        if va is None or vb is None:
            return Evidence("inconclusive", 0, method)
        return Evidence("passed" if close(va, vb) else "failed", 1, method, {}, (va, vb))
    tested = 0
    for point in sample_points(symbols, n * 2, conditions=conditions):
        va, vb = _value(a, point), _value(b, point)
        if va is None or vb is None:
            continue
        tested += 1
        if not close(va, vb):
            return Evidence("failed", tested, method, point, (va, vb))
        if tested >= n:
            break
    return Evidence("passed" if tested >= 3 else "inconclusive", tested, method)


def check_derivative(f, df, var, n=8):
    """Compare a claimed derivative with the central difference [f(x+h) - f(x-h)] / 2h."""
    h = sp.Rational(1, 10 ** 8)
    numeric = (f.subs(var, var + h) - f.subs(var, var - h)) / (2 * h)
    ev = agree(numeric, df, {var} | df.free_symbols | f.free_symbols, n=n,
               method="Derivative vs finite difference [f(x+h) − f(x−h)]/2h")
    return ev


def check_antiderivative(F, f, var, n=8):
    """An antiderivative F is right if F' = f: check it with finite differences."""
    ev = check_derivative(F, f, var, n)
    ev.method = "d/dx of the antiderivative vs the integrand (finite difference)"
    return ev


def check_definite_integral(f, var, a, b, value):
    """Compare a definite integral with adaptive numerical quadrature (mpmath)."""
    method = "Definite integral vs numerical quadrature"
    try:
        numeric = sp.Integral(f, (var, a, b)).evalf(20)
        va, vb = complex(numeric), complex(sp.N(value, DIGITS))
    except (TypeError, ValueError, ZeroDivisionError):
        return Evidence("inconclusive", 0, method)
    return Evidence("passed" if close(va, vb, 1e-7) else "failed", 1, method, {}, (va, vb))


def check_roots(residual, var, roots):
    """Substitute each root into ``residual`` (lhs − rhs); every result should be ~0."""
    method = "Each solution substituted back into the equation"
    tested = 0
    for r in roots:
        v = _value(residual, {var: r})
        if v is None:
            continue
        tested += 1
        if abs(v) > 1e-9:
            return Evidence("failed", tested, method, {var: r}, (v, 0))
    return Evidence("passed" if tested else "inconclusive", tested, method)
