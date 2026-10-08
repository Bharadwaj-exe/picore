"""Offline computation with SymPy.

``compute(text)`` returns a list of (title, content) pods, mirroring the shape
of Wolfram|Alpha results, plus the expression that can be graphed (if any).
"""
import re

import sympy as sp

from ..reasoning import numeric
from .parser import ParseError, normalize_text, parse_expr, parse_relation, parse_system

X = sp.Symbol("x")


def fmt(value):
    """Human-friendly one-line rendering of a SymPy object."""
    if isinstance(value, sp.Float) or (getattr(value, "is_number", False) and value.is_Float):
        return format(float(value), ".15g")
    text = sp.sstr(value)
    text = text.replace("**", "^")
    text = re.sub(r"\bpi\b", "π", text)
    text = re.sub(r"\boo\b", "∞", text)
    text = re.sub(r"\bI\b", "i", text)
    text = re.sub(r"\bE\b", "e", text)
    text = re.sub(r"\blog\(", "ln(", text)
    text = text.replace("sqrt", "√")
    text = re.sub(r"(?<![\w.^])(\d+)\*(?=[A-Za-zπ√(])", r"\g<1>", text)  # 2*x -> 2x, but not x^2*cos
    return text.replace("*", "·")


def _needs_approx(v):
    if not getattr(v, "is_number", False):
        return False
    re_, im_ = v.as_real_imag()
    return not (re_.is_Rational and im_.is_Rational)


def _approx(v, digits=10):
    re_, im_ = (sp.N(part, digits) for part in v.as_real_imag())
    if im_ == 0:
        return format(float(re_), f".{digits}g")
    sign = "+" if im_ >= 0 else "-"
    return f"{format(float(re_), f'.{digits}g')} {sign} {format(abs(float(im_)), f'.{digits}g')}i"


def _factorization(n):
    return " × ".join(f"{p}^{k}" if k > 1 else str(p) for p, k in sp.factorint(n).items())


def _pretty_input(raw):
    return normalize_text(raw).replace("**", "^")


def _pick_var(expr, hint=None):
    if hint:
        return sp.Symbol(hint)
    free = sorted(expr.free_symbols, key=lambda s: s.name)
    if not free:
        return X
    return X if X in free else free[0]


def _solve(relations):
    eqs = [r if isinstance(r, sp.Equality) else sp.Eq(r, 0) for r in relations]
    syms = sorted(set().union(*(e.free_symbols for e in eqs)), key=lambda s: s.name)
    if not syms:
        truth = all(bool(sp.simplify(e.lhs - e.rhs) == 0) for e in eqs)
        return [("Input", ", ".join(fmt(e) for e in eqs)), ("Result", "True" if truth else "False")]
    pods = [("Input", "; ".join(f"{fmt(e.lhs)} = {fmt(e.rhs)}" for e in eqs))]
    if len(eqs) == 1 and len(syms) > 1:
        syms = [_pick_var(eqs[0])]
    try:
        sols = sp.solve(eqs, syms, dict=True)
    except NotImplementedError:
        if len(eqs) == 1 and len(syms) == 1:
            return pods + _numeric_scan(eqs[0].lhs - eqs[0].rhs, syms[0])
        raise
    if not sols:
        pods += _no_closed_form(eqs, syms)
        return pods
    lines = []
    for sol in sols:
        parts = [f"{fmt(k)} = {fmt(v)}" for k, v in sol.items()]
        approx = [f"{fmt(k)} ≈ {_approx(v, 8)}" for k, v in sol.items() if _needs_approx(v)]
        line = ",  ".join(parts)
        if approx:
            line += "   (" + ", ".join(approx) + ")"
        lines.append(line)
    pods.append(("Solutions" if len(lines) > 1 else "Solution", "\n".join(lines)))
    pods.append(_verify_solutions(eqs, sols))
    return pods


def _no_closed_form(eqs, syms):
    """solve() found nothing. Never claim 'no solutions' unless that is actually proved."""
    if len(eqs) == 1 and len(syms) == 1:
        var, residual = syms[0], eqs[0].lhs - eqs[0].rhs
        try:
            if sp.solveset(residual, var, domain=sp.S.Complexes) == sp.S.EmptySet:
                return [("Solutions", "None: the equation has no solutions (proved).")]
        except (NotImplementedError, ValueError, TypeError):
            pass
        if residual.is_polynomial(var):
            roots = sp.Poly(residual, var).nroots(n=12)
            lines = [f"{var} ≈ {_approx(r, 10)}" for r in roots]
            ev = numeric.check_roots(residual, var, roots)
            return [("Solutions (numerical)", "\n".join(lines)),
                    ("Why numerical?", "No exact formula for these roots was found. Polynomials of degree 5 and "
                                       "higher generally have no formula in radicals (Abel–Ruffini theorem), so "
                                       "the roots are computed numerically."),
                    ("Verification", ev.summary().replace("disagree", "residual not ~0") + ".")]
    return [("Solutions", "No closed-form solution found. This does not mean there are none.")]


SCAN = (-20, 20)


def _numeric_scan(residual, var, steps=4000):
    """Real roots in SCAN by sign changes + refinement. Honest about being incomplete."""
    import numpy as np
    f = sp.lambdify(var, residual, modules="mpmath")
    xs = np.linspace(*SCAN, steps)
    vals = []
    for xv in xs:
        try:
            v = complex(f(float(xv)))
            vals.append(v.real if abs(v.imag) < 1e-12 else float("nan"))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            vals.append(float("nan"))
    roots = []
    for a, b, fa, fb in zip(xs, xs[1:], vals, vals[1:]):
        if fa == 0:
            roots.append(sp.Float(a))
        elif fa * fb < 0:
            try:
                r = sp.nsolve(residual, var, (float(a), float(b)), solver="bisect")
            except (ValueError, ZeroDivisionError, TypeError):
                continue
            if abs(complex(residual.subs(var, r).evalf())) < 1e-8:      # a root, not a pole
                roots.append(r)
    if not roots:
        return [("Solutions", f"No exact solution found, and no real roots in [{SCAN[0]}, {SCAN[1]}]. "
                              f"There may still be solutions outside that range or complex ones.")]
    lines = [f"{var} ≈ {_approx(r, 10)}" for r in roots]
    return [("Solutions (numerical)", "\n".join(lines)),
            ("Why numerical?", f"This equation mixes kinds of functions, so it has no closed-form solution "
                               f"SymPy can find. Real roots were located numerically in [{SCAN[0]}, {SCAN[1]}] by "
                               f"looking for sign changes; roots outside that range are not listed."),
            _verification([numeric.check_roots(residual, var, roots)])]


def _verification(evidence):
    return ("Verification", "\n".join(e.summary() + "." for e in evidence))


def _verify_solutions(eqs, sols):
    """Substitute every solution back: exact zero is a proof, otherwise fall back to numerics."""
    proved = all(sp.simplify((e.lhs - e.rhs).subs(sol)) == 0 for sol in sols for e in eqs)
    if proved:
        return ("Verification", "Proved: substituting each solution into the equation gives exactly 0.")
    if len(eqs) == 1 and all(len(s) == 1 for s in sols):
        var = next(iter(sols[0]))
        return _verification([numeric.check_roots(eqs[0].lhs - eqs[0].rhs, var, [s[var] for s in sols])])
    return ("Verification", "Could not confirm every solution by substitution.")


def _expression_pods(expr, raw):
    pods = [("Input", _pretty_input(raw))]
    if not expr.free_symbols:
        exact = sp.simplify(expr)
        pods.append(("Result", fmt(exact)))
        if _needs_approx(exact) or (exact.is_Rational and not exact.is_Integer):
            pods.append(("Decimal approximation", _approx(exact, 15)))
        if exact.is_Integer and 1 < abs(exact) < 10**12 and not sp.isprime(abs(exact)):
            pods.append(("Prime factorization", _factorization(abs(exact))))
        elif exact.is_Integer and 1 < abs(exact) < 10**12:
            pods.append(("Prime factorization", f"{abs(exact)} is prime"))
        return pods
    simple = sp.simplify(expr)
    if simple != expr:
        pods.append(("Simplified", fmt(simple)))
    factored = sp.factor(simple)
    if factored != simple:
        pods.append(("Factored form", fmt(factored)))
    expanded = sp.expand(simple)
    if expanded != simple and expanded != factored:
        pods.append(("Expanded form", fmt(expanded)))
    if len(expr.free_symbols) == 1:
        var = _pick_var(expr)
        pods.append((f"Derivative d/d{var}", fmt(sp.simplify(sp.diff(expr, var)))))
        try:
            roots = sp.solve(sp.Eq(simple, 0), var)
            if roots:
                pods.append(("Roots", ",  ".join(f"{var} = {fmt(r)}" for r in roots[:8])))
        except (NotImplementedError, ValueError):
            pass
    return pods


# ---- command patterns -------------------------------------------------------
_RE_CHECK = re.compile(r"^check\s+", re.I)
_RE_SOLVE = re.compile(r"^solve\s+(.+?)(?:\s+for\s+([a-z]))?$", re.I)
_RE_DDX = re.compile(r"^d/d([a-z])\s*(.+)$", re.I)
_RE_DIFF = re.compile(r"^(?:diff|differentiate|derivative(?:\s+of)?)\s+(.+?)"
                      r"(?:\s+(?:wrt|with respect to)\s+([a-z]))?$", re.I)
_RE_INT = re.compile(r"^(?:integrate|integral(?:\s+of)?|∫)\s*(.+?)"
                     r"(?:\s*d([a-z]))?(?:\s+from\s+(.+?)\s+to\s+(.+))?$", re.I)
_RE_LIMIT = re.compile(r"^lim(?:it)?(?:\s+of)?\s+(.+?)\s+as\s+([a-z])\s*(?:->|→|to|approaches)\s*(.+)$", re.I)
_RE_TRANSFORM = re.compile(r"^(factor|expand|simplify)\s+(.+)$", re.I)


def compute(text):
    """Return (pods, plot_expr). Raises ParseError if the input isn't math."""
    text = normalize_text(text)

    if _RE_CHECK.match(text):
        from .checker import check
        return check(text), None

    from . import reasoning_commands
    pods = reasoning_commands.match(text)
    if pods is not None:
        return pods, None

    m = _RE_SOLVE.match(text)
    if m:
        relations = parse_system(m.group(1))
        if m.group(2) and len(relations) == 1:
            r = relations[0]
            eq = r if isinstance(r, sp.Equality) else sp.Eq(r, 0)
            sym = sp.Symbol(m.group(2))
            sols = sp.solve(eq, sym)
            return [("Input", f"{fmt(eq.lhs)} = {fmt(eq.rhs)}"),
                    ("Solution", "\n".join(f"{sym} = {fmt(s)}" for s in sols) or "No solutions found")], None
        return _solve(relations), None

    m = _RE_DDX.match(text) or _RE_DIFF.match(text)
    if m:
        if m.re is _RE_DDX:
            var_name, body = m.group(1), m.group(2)
        else:
            body, var_name = m.group(1), m.group(2)
        expr = parse_expr(body)
        var = _pick_var(expr, var_name)
        d = sp.diff(expr, var)
        pods = [("Input", f"d/d{var} [{fmt(expr)}]"), ("Derivative", fmt(sp.simplify(d)))]
        d2 = sp.simplify(sp.diff(d, var))
        pods.append(("Second derivative", fmt(d2)))
        pods.append(_verification([numeric.check_derivative(expr, d, var)]))
        return pods, expr

    m = _RE_INT.match(text)
    if m:
        body, var_name, lo, hi = m.groups()
        expr = parse_expr(body)
        var = _pick_var(expr, var_name)
        if lo is not None:
            a, b = parse_expr(lo), parse_expr(hi)
            val = sp.integrate(expr, (var, a, b))
            pods = [("Input", f"∫ {fmt(expr)} d{var}  from {fmt(a)} to {fmt(b)}"),
                    ("Definite integral", fmt(val))]
            if _needs_approx(val):
                pods.append(("Decimal approximation", _approx(val, 12)))
            if not val.free_symbols:
                pods.append(_verification([numeric.check_definite_integral(expr, var, a, b, val)]))
            return pods, expr
        val = sp.integrate(expr, var)
        if val.has(sp.Integral):
            return [("Input", f"∫ {fmt(expr)} d{var}"), ("Indefinite integral", "No closed form found")], expr
        return [("Input", f"∫ {fmt(expr)} d{var}"), ("Indefinite integral", fmt(val) + " + C"),
                _verification([numeric.check_antiderivative(val, expr, var)])], expr

    m = _RE_LIMIT.match(text)
    if m:
        expr, var = parse_expr(m.group(1)), sp.Symbol(m.group(2))
        point = parse_expr(m.group(3))
        val = sp.limit(expr, var, point)
        return [("Input", f"lim {var}→{fmt(point)}  {fmt(expr)}"), ("Limit", fmt(val))], expr

    m = _RE_TRANSFORM.match(text)
    if m:
        op = m.group(1).lower()
        expr = parse_expr(m.group(2))
        out = {"factor": sp.factor, "expand": sp.expand, "simplify": sp.simplify}[op](expr)
        return [("Input", fmt(expr)), (op.capitalize() + "ed" if op != "simplify" else "Simplified", fmt(out))], expr

    if "=" in text or " and " in text.lower():
        relations = parse_system(text)
        plot = None
        if len(relations) == 1 and isinstance(relations[0], sp.Equality):
            r = relations[0]
            if r.lhs == sp.Symbol("y") and sp.Symbol("y") not in r.rhs.free_symbols:
                return _expression_pods(r.rhs, text), r.rhs
            if len(r.free_symbols) == 1:
                plot = r.lhs - r.rhs
        return _solve(relations), plot

    expr = parse_relation(text)
    plot = expr if len(expr.free_symbols) == 1 else None
    return _expression_pods(expr, text), plot


def plot_target(text):
    """Best-effort: the single-variable expression to graph for ``text``."""
    try:
        _, plot = compute(text)
    except (ParseError, ValueError, NotImplementedError, TypeError):
        return None
    if plot is None or len(plot.free_symbols) != 1:
        return None
    return plot


__all__ = ["compute", "plot_target", "fmt", "ParseError"]
