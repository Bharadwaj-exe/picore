"""Parameter exploration: a function of x with free parameters (a, b, c, …) plus analyzers.

    explore a x^2 + b x + c
    explore A sin(B x + C) + D

``Experiment`` holds the expression and parameter values. Analyzers are tried in
order. Each one that applies reports facts (roots, vertex, period, ...) with a short
explanation and the points to mark on the graph. Adding a new kind of experiment
means adding one Analyzer subclass to ANALYZERS. No UI code lives here.
"""
from dataclasses import dataclass, field

import numpy as np
import sympy as sp

from .engine.parser import ParseError, parse_expr

X = sp.Symbol("x")
RANGE = (-10.0, 10.0)


@dataclass
class Fact:
    label: str
    value: str
    why: str = ""


@dataclass
class Analysis:
    facts: list = field(default_factory=list)
    markers: list = field(default_factory=list)     # (x, y, label, kind)  kind: root | vertex | point
    vlines: list = field(default_factory=list)      # x positions (axis of symmetry, ...)
    kind: str = ""                                   # which analyzer produced it


@dataclass
class Experiment:
    expr: object
    params: list
    values: dict

    def current(self):
        return self.expr.subs(self.values)


def make_experiment(text):
    text = text.strip()
    for prefix in ("y=", "f(x)=", "y =", "f(x) ="):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break
    expr = parse_expr(text)
    if X not in expr.free_symbols:
        raise ParseError("Explore needs a function of x, e.g.  explore a x^2 + b x + c")
    params = sorted(expr.free_symbols - {X}, key=lambda s: s.name)
    if not params:
        raise ParseError("Add a parameter to vary, e.g.  explore a x^2 + b x + c")
    if len(params) > 4:
        raise ParseError("Explore supports up to 4 parameters")
    return Experiment(expr, params, {p: 1.0 for p in params})


def _num(v, digits=4):
    v = complex(v)
    scale = max(1.0, abs(v))
    v = complex(0 if abs(v.real) < 1e-12 * scale else v.real, 0 if abs(v.imag) < 1e-12 * scale else v.imag)
    if abs(v.imag) < 1e-12:
        r = v.real
        return str(int(round(r))) if abs(r - round(r)) < 1e-9 else f"{r:.{digits}g}"
    im = "" if abs(abs(v.imag) - 1) < 1e-12 else f"{abs(v.imag):.{digits}g}"
    if v.real == 0:
        return f"{'-' if v.imag < 0 else ''}{im}i"
    return f"{v.real:.{digits}g} {'+' if v.imag >= 0 else '-'} {im}i"


class Analyzer:
    name = ""

    def applies(self, exp):
        return False

    def analyze(self, exp):
        return Analysis()


class Quadratic(Analyzer):
    name = "Quadratic"

    def applies(self, exp):
        try:
            return sp.Poly(exp.expr, X).degree() == 2
        except sp.PolynomialError:
            return False

    def analyze(self, exp):
        a, b, c = (float(sp.N(k.subs(exp.values))) for k in sp.Poly(exp.expr, X).all_coeffs())
        out = Analysis()
        if abs(a) < 1e-12:
            out.facts.append(Fact("Shape", "a straight line", "With a = 0 the x² term vanishes, so this is not a quadratic."))
            if abs(b) > 1e-12:
                out.markers.append((-c / b, 0.0, f"x = {_num(-c / b)}", "root"))
            return out
        D = b * b - 4 * a * c
        h = -b / (2 * a)
        k = a * h * h + b * h + c
        out.facts.append(Fact("Discriminant", f"D = b² − 4ac = {_num(D)}",
                              "D > 0: two real roots (the curve crosses the x-axis twice)." if D > 1e-12 else
                              "D = 0: one repeated root (the vertex touches the x-axis)." if abs(D) <= 1e-12 else
                              "D < 0: no real roots (the curve never meets the x-axis); two complex roots."))
        if D > 1e-12:
            r1, r2 = sorted(((-b - D ** 0.5) / (2 * a), (-b + D ** 0.5) / (2 * a)))
            out.facts.append(Fact("Roots", f"x = {_num(r1)},  x = {_num(r2)}"))
            out.markers += [(r1, 0.0, f"x = {_num(r1)}", "root"), (r2, 0.0, f"x = {_num(r2)}", "root")]
        elif abs(D) <= 1e-12:
            out.facts.append(Fact("Root", f"x = {_num(h)} (repeated)"))
            out.markers.append((h, 0.0, f"x = {_num(h)}", "root"))
        else:
            sq = complex(D) ** 0.5
            out.facts.append(Fact("Roots", f"x = {_num((-b + sq) / (2 * a))},  x = {_num((-b - sq) / (2 * a))}"))
        out.facts.append(Fact("Vertex", f"({_num(h)}, {_num(k)})",
                              f"{'Minimum' if a > 0 else 'Maximum'} point, because a {'>' if a > 0 else '<'} 0 "
                              f"makes the parabola open {'upward' if a > 0 else 'downward'}."))
        out.facts.append(Fact("Axis of symmetry", f"x = −b / 2a = {_num(h)}"))
        out.markers.append((h, k, "vertex", "vertex"))
        out.vlines.append(h)
        return out


class Linear(Analyzer):
    name = "Linear"

    def applies(self, exp):
        try:
            return sp.Poly(exp.expr, X).degree() == 1
        except sp.PolynomialError:
            return False

    def analyze(self, exp):
        m, c = (float(sp.N(k.subs(exp.values))) for k in sp.Poly(exp.expr, X).all_coeffs())
        out = Analysis([Fact("Slope", _num(m), "The line rises by the slope for every 1 step right."),
                        Fact("y-intercept", _num(c))])
        if abs(m) > 1e-12:
            out.facts.append(Fact("Root", f"x = {_num(-c / m)}"))
            out.markers.append((-c / m, 0.0, f"x = {_num(-c / m)}", "root"))
        else:
            out.facts.append(Fact("Root", "none" if abs(c) > 1e-12 else "every x",
                                  "Slope 0 makes the line horizontal."))
        return out


class Sinusoid(Analyzer):
    """A·sin(B·x + C) + D  (or cos)."""
    name = "Sinusoid"
    W = {k: sp.Wild(k, exclude=[X]) for k in "ABCD"}

    def _match(self, expr):
        A, B, C, D = (self.W[k] for k in "ABCD")
        for f in (sp.sin, sp.cos):
            m = sp.expand(expr).match(A * f(B * X + C) + D)
            if m and m.get(B, 0) != 0 and m.get(A, 0) != 0:
                return f, m
        return None

    def applies(self, exp):
        return self._match(exp.expr) is not None

    def analyze(self, exp):
        f, m = self._match(exp.expr)
        A, B, C, D = (complex(sp.N(m.get(self.W[k], 0).subs(exp.values))).real for k in "ABCD")
        out = Analysis()
        if abs(B) < 1e-12:
            out.facts.append(Fact("Shape", "constant", "With B = 0 the wave is frozen."))
            return out
        period = 2 * np.pi / abs(B)
        out.facts += [Fact("Amplitude", _num(abs(A)), "Half the distance from trough to peak: |A|."),
                      Fact("Period", f"2π / |B| = {_num(period)}", "One full wave repeats every period."),
                      Fact("Phase shift", _num(-C / B), "The wave is slid sideways by −C / B."),
                      Fact("Midline", f"y = {_num(D)}")]
        return out


class Generic(Analyzer):
    """Applies to everything: y-intercept and real roots found numerically in the visible range."""
    name = "Any function"

    def applies(self, exp):
        return True

    def analyze(self, exp):
        out = Analysis()
        f = sp.lambdify(X, exp.current(), modules="numpy")
        try:
            y0 = complex(sp.N(exp.current().subs(X, 0)))
            if abs(y0.imag) < 1e-12 and np.isfinite(y0.real):
                out.facts.append(Fact("y-intercept", _num(y0.real)))
                out.markers.append((0.0, y0.real, "", "point"))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        roots = numeric_roots(f, *RANGE)
        if roots:
            shown = ",  ".join(f"x ≈ {_num(r)}" for r in roots[:6]) + ("  …" if len(roots) > 6 else "")
            out.facts.append(Fact(f"Real roots in [{RANGE[0]:g}, {RANGE[1]:g}]", shown,
                                  "Found numerically (sign changes, then refined)."))
            out.markers += [(r, 0.0, "", "root") for r in roots]
        else:
            out.facts.append(Fact(f"Real roots in [{RANGE[0]:g}, {RANGE[1]:g}]", "none found"))
        return out


def numeric_roots(f, lo, hi, n=4001):
    xs = np.linspace(lo, hi, n)
    with np.errstate(all="ignore"):
        ys = np.asarray(f(xs), dtype=complex) * np.ones_like(xs)
    ys = np.where(np.abs(ys.imag) < 1e-9, ys.real, np.nan).real
    roots = []
    for i in range(n - 1):
        a, b, fa, fb = xs[i], xs[i + 1], ys[i], ys[i + 1]
        if not (np.isfinite(fa) and np.isfinite(fb)):
            continue
        if fa == 0:
            roots.append(float(a))
        elif fa * fb < 0:
            for _ in range(50):                       # bisection
                mid = (a + b) / 2
                with np.errstate(all="ignore"):
                    fm = complex(f(mid)).real
                if fa * fm <= 0:
                    b = mid
                else:
                    a, fa = mid, fm
            r = (a + b) / 2
            with np.errstate(all="ignore"):
                if abs(complex(f(r))) < 1e-6:        # sign change at a pole is not a root
                    roots.append(float(r))
    return roots


SPECIFIC = [Quadratic(), Linear(), Sinusoid()]
GENERIC = Generic()


def analyze(exp):
    """The first specific analyzer that applies, plus the generic y-intercept.
    With no specific match, the generic analysis (numerical roots) is used."""
    generic = GENERIC.analyze(exp)
    specific = next((a for a in SPECIFIC if a.applies(exp)), None)
    if specific is None:
        generic.kind = GENERIC.name
        return generic
    result = specific.analyze(exp)
    have = {f.label for f in result.facts}
    result.facts += [f for f in generic.facts if f.label == "y-intercept" and f.label not in have]
    result.markers += [m for m in generic.markers if m[3] == "point"]
    result.kind = specific.name
    return result
