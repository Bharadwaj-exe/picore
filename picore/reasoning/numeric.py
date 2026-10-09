"""Numerical verification: independent, evidence-only checks of symbolic results.

Every check returns ``Evidence``. Agreement at sample points is EVIDENCE, not proof:
finitely many points can never establish an identity. Callers present it as
"numerically supported", never as "proved". A *disagreement* at a point where both
sides are defined is different: it is a genuine counterexample.

Conventions
- Expressions are real-valued: at a sample point where either side is non-real
  (e.g. ln of a negative number) nothing is compared; that point is skipped.
- Pure constants are compared at high precision (60 digits), because they can be:
  e^(π√163) and 640320³ + 744 differ only in the 30th significant digit.
- Arithmetic uses mpmath through SymPy's ``evalf`` (30 significant digits for
  functions of variables), so finite-difference and rounding error stay far
  below the tolerances used.
"""
import random
from dataclasses import dataclass, field

import sympy as sp

DIGITS = 30
CONST_DIGITS = 60
REL_TOL = 1e-8
CONST_REL_TOL = 1e-40
IMAG_TOL = 1e-12

# Real-root search (documented limitations: see real_roots)
ROOT_RANGE = (-20.0, 20.0)
ROOT_GRID = 4001                 # grid step 0.01 on the default range
ROOT_RESIDUAL_TOL = 1e-6         # sign-change roots: |f(r)| must be this small (rejects poles)
TANGENT_RESIDUAL_TOL = 1e-20     # roots without a sign change must make |f| essentially zero
ROOT_MERGE_TOL = 1e-7
MAX_ROOTS = 200                  # stop collecting after this many (e.g. very oscillatory functions)


@dataclass
class Evidence:
    status: str                    # "passed" | "failed" | "inconclusive"
    tested: int = 0                # points where both sides could be evaluated
    method: str = ""               # what was compared, in words
    counterexample: dict = field(default_factory=dict)   # {symbol: value} where it failed
    values: tuple = ()             # (left, right) at the counterexample
    passed_note: str = ""          # optional wording for the passed case

    @property
    def passed(self):
        return self.status == "passed"

    def summary(self):
        if self.status == "passed":
            where = self.passed_note or ("agreed" if self.tested == 1 else f"agreed at {self.tested} test points")
            return f"{self.method}: {where} (numerically supported; numerical evidence, not a proof)"
        if self.status == "failed":
            where = ", ".join(f"{k} = {v}" for k, v in self.counterexample.items()) or "a test point"
            a, b = (_short(v) for v in self.values)
            return f"{self.method}: disagree at {where} ({a} vs {b})"
        return f"{self.method}: not enough valid test points (not verified)"


def _short(z):
    z = complex(z)
    if abs(z.imag) < IMAG_TOL:
        return format(z.real, ".6g")
    return f"{z.real:.4g}{z.imag:+.4g}i"


def _value(expr, point, digits=DIGITS):
    """Evaluate to a Python complex, or None if undefined / infinite at ``point``."""
    try:
        v = sp.N(expr.subs(point), digits)
        if v.has(sp.zoo, sp.oo, -sp.oo, sp.nan) or not v.is_number:
            return None
        z = complex(v)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if z != z or abs(z) == float("inf"):
        return None
    return z


def _is_real(z):
    return abs(z.imag) <= IMAG_TOL * max(1.0, abs(z.real))


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


def _constants_agree(a, b, method):
    """Pure constants: compare at 60 digits, complex values allowed (e^(iπ) = -1)."""
    try:
        va = sp.N(a, CONST_DIGITS)
        vb = sp.N(b, CONST_DIGITS)
        if any(v.has(sp.zoo, sp.oo, -sp.oo, sp.nan) or not v.is_number for v in (va, vb)):
            return Evidence("inconclusive", 0, method)
        diff = abs(sp.N(va - vb, CONST_DIGITS))
        scale = max(1, abs(va), abs(vb))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return Evidence("inconclusive", 0, method)
    ok = diff <= CONST_REL_TOL * scale
    return Evidence("passed" if ok else "failed", 1, method, {}, (complex(va), complex(vb)))


def agree(a, b, symbols=None, n=10, conditions=(), method="Values compared"):
    """Compare two expressions at sample points where both are defined and real."""
    symbols = symbols if symbols is not None else (a.free_symbols | b.free_symbols)
    if not symbols:
        return _constants_agree(a, b, method)
    tested = 0
    for point in sample_points(symbols, n * 3, conditions=conditions):
        va, vb = _value(a, point), _value(b, point)
        if va is None or vb is None or not (_is_real(va) and _is_real(vb)):
            continue
        tested += 1
        if not close(va.real, vb.real):
            return Evidence("failed", tested, method, point, (va.real, vb.real))
        if tested >= n:
            break
    return Evidence("passed" if tested >= 3 else "inconclusive", tested, method)


def check_derivative(f, df, var, n=8):
    """Compare a claimed derivative with the central difference [f(x+h) - f(x-h)] / 2h."""
    h = sp.Rational(1, 10 ** 8)
    numeric = (f.subs(var, var + h) - f.subs(var, var - h)) / (2 * h)
    return agree(numeric, df, {var} | df.free_symbols | f.free_symbols, n=n,
                 method="Derivative vs finite difference [f(x+h) − f(x−h)]/2h")


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
    """Substitute each root into ``residual`` (lhs − rhs); every result should be ~0
    relative to the size of the residual's terms at that point."""
    method = "Each solution substituted back into the equation"
    tested = 0
    terms = sp.Add.make_args(sp.expand(residual))
    for r in roots:
        v = _value(residual, {var: r})
        if v is None:
            continue
        scale = max([1.0] + [abs(t) for t in (_value(term, {var: r}) for term in terms) if t is not None])
        tested += 1
        if abs(v) > 1e-9 * scale:
            return Evidence("failed", tested, method, {var: r}, (v, 0))
    ev = Evidence("passed" if tested else "inconclusive", tested, method)
    ev.passed_note = f"every one of the {tested} solutions gives ≈ 0"
    return ev


# ---- real roots ------------------------------------------------------------------------

def _real_fn(expr, var):
    """mpmath-backed f(x) returning a float, or None where undefined / non-real."""
    import mpmath
    mpmath.mp.dps = DIGITS
    raw = sp.lambdify(var, expr, modules="mpmath")

    def f(x):
        try:
            v = raw(mpmath.mpf(x))
            c = complex(v)
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return None
        if c != c or abs(c) == float("inf") or not _is_real(c):
            return None
        return v.real if hasattr(v, "real") else v
    return f


def real_roots(expr, var, lo=ROOT_RANGE[0], hi=ROOT_RANGE[1], n=ROOT_GRID):
    """Real roots of ``expr`` in [lo, hi], found numerically. NOT guaranteed complete.

    Method: evaluate on a uniform grid; (1) every sign change between defined
    neighbours is refined by bisection and kept only if |f| is tiny there (a sign
    change across a pole is rejected); (2) every local minimum of |f| without a sign
    change is refined by golden-section search and kept only if |f| is essentially 0
    (tangential roots such as e^x = x + 1 at 0). Limitations: roots outside [lo, hi]
    are not searched; two roots closer than the grid step (here 0.01) can merge or
    be missed; a function that changes sign only inside one grid cell twice can hide
    both roots. Callers must say "found numerically", never "these are all".
    """
    import mpmath
    try:
        if sp.simplify(expr) == 0:         # identically zero: every point solves it; there are no isolated roots
            return []
    except (TypeError, ValueError, NotImplementedError):
        pass
    f = _real_fn(expr, var)
    step = (hi - lo) / (n - 1)
    xs = [lo + i * step for i in range(n)]
    ys = [f(x) for x in xs]
    found = []

    def keep(r):
        if all(abs(r - q) > ROOT_MERGE_TOL for q in found):
            found.append(r)

    for i in range(n):
        if len(found) >= MAX_ROOTS:
            break
        y = ys[i]
        if y is None:
            continue
        if y == 0:
            keep(xs[i])
            continue
        if i + 1 < n and ys[i + 1] is not None and y * ys[i + 1] < 0:      # sign change
            a, b, fa = mpmath.mpf(xs[i]), mpmath.mpf(xs[i + 1]), y
            for _ in range(80):
                m = (a + b) / 2
                fm = f(m)
                if fm is None:
                    break
                if fa * fm <= 0:
                    b = m
                else:
                    a, fa = m, fm
            r = (a + b) / 2
            fr = f(r)
            if fr is not None and abs(fr) < ROOT_RESIDUAL_TOL:
                keep(float(r))
        elif 0 < i < n - 1 and ys[i - 1] is not None and ys[i + 1] is not None \
                and abs(y) <= abs(ys[i - 1]) and abs(y) <= abs(ys[i + 1]) \
                and ys[i - 1] * y > 0 and y * ys[i + 1] > 0:              # touches without crossing?
            a, b = mpmath.mpf(xs[i - 1]), mpmath.mpf(xs[i + 1])
            g = (mpmath.sqrt(5) - 1) / 2
            c, d = b - g * (b - a), a + g * (b - a)
            fc, fd = f(c), f(d)
            for _ in range(120):
                if fc is None or fd is None:
                    break
                if abs(fc) < abs(fd):
                    b, d, fd = d, c, fc
                    c = b - g * (b - a)
                    fc = f(c)
                else:
                    a, c, fc = c, d, fd
                    d = a + g * (b - a)
                    fd = f(d)
            r = (a + b) / 2
            fr = f(r)
            if fr is not None and abs(fr) < TANGENT_RESIDUAL_TOL:
                keep(float(r))
    return sorted(found)
