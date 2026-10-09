"""Offline computation with SymPy.

``compute(text)`` returns a list of (title, content) pods, mirroring the shape
of Wolfram|Alpha results, plus the expression that can be graphed (if any).
"""
import logging
import re

import sympy as sp

from ..reasoning import numeric
from ..lang.printing import approx as _approx
from ..lang.printing import fmt
from ..lang.printing import needs_approx as _needs_approx
from .parser import ParseError, normalize_text, parse_expr, parse_relation, parse_system

X = sp.Symbol("x")
log = logging.getLogger(__name__)


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
    if len(eqs) == 1 and sp.simplify(eqs[0].lhs - eqs[0].rhs) == 0:
        return pods + [("Solutions", f"Every value of {', '.join(map(str, syms))} is a solution: the equation is an "
                                     f"identity (both sides are always equal where they are defined).")]
    if len(eqs) == 1 and len(syms) == 1 and _periodic(eqs[0].lhs - eqs[0].rhs, syms[0]):
        general = _general_solutions(eqs[0].lhs - eqs[0].rhs, syms[0])
        if general is not None:
            lines, empty = general
            if empty:
                return pods + [("Real solutions", "None: there are no real solutions (proved).")]
            return pods + [("All real solutions", "\n".join(lines) + "\n(n is any integer)"),
                           ("Why a formula?", "The equation repeats periodically, so it has infinitely many "
                                              "solutions; each line describes a whole family.")]
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
    if len(eqs) > 1 and all((e.lhs - e.rhs).is_polynomial(*syms) for e in eqs):
        try:
            if sp.nonlinsolve([e.lhs - e.rhs for e in eqs], syms) == sp.S.EmptySet:
                return [("Solutions", "None: the equations contradict each other (proved).")]
        except (NotImplementedError, ValueError, TypeError):
            pass
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


def _numeric_scan(residual, var):
    """Real roots found numerically (numeric.real_roots). Honest about being incomplete."""
    lo, hi = numeric.ROOT_RANGE
    roots = numeric.real_roots(residual, var)
    if not roots:
        return [("Solutions", f"None found. No exact solution was found, and this numerical method found no "
                              f"real roots in [{lo:g}, {hi:g}]. That is not a proof that none exist: there may be "
                              f"roots outside that range, roots it cannot resolve, or complex ones.")]
    lines = [f"{var} ≈ {_approx(sp.Float(r, 15), 10)}" for r in roots]
    return [("Solutions (numerical)", "\n".join(lines)),
            ("Why numerical?", f"No closed-form solution was found, so real roots were located numerically in "
                               f"[{lo:g}, {hi:g}]: sign changes refined by bisection, plus touching (double) roots "
                               f"found as minima of |f|. Roots outside that range are not listed, and roots closer "
                               f"together than the 0.01 search grid can be missed."),
            _verify(lambda: numeric.check_roots(residual, var, roots))]


def _verification(evidence):
    return ("Verification", "\n".join(e.summary() + "." for e in evidence))


def real_diff(expr, var):
    """Differentiate treating var as REAL: d/dx |x| = sign(x), not a complex-analysis Piecewise."""
    xr = sp.Symbol(var.name, real=True)
    return sp.diff(expr.subs(var, xr), xr).subs(xr, var)


def _verify(check):
    """Run one numerical check; if it cannot run, say so instead of failing the whole answer."""
    try:
        return _verification([check()])
    except Exception:
        log.debug("verification failed", exc_info=True)
        return ("Verification", "Could not be run for this result (not verified).")


def _undefined(value):
    """Human description if a value is undefined / infinite, else None."""
    if value is sp.zoo or value.has(sp.zoo):
        return "Undefined: it hits a singularity (division by zero, ln 0, tan(π/2), a negative-integer factorial, …)."
    if value is sp.nan or value.has(sp.nan):
        return "Undefined: an indeterminate form (such as 0/0 or ∞ − ∞)."
    if value in (sp.oo, -sp.oo):
        return f"{fmt(value)} (unbounded, not a real number)"
    return None


def _periodic(residual, var):
    """True if the equation repeats periodically in var (so a finite list of roots can't be complete)."""
    try:
        return residual.has(sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc) and \
            sp.periodicity(residual, var) is not None
    except (NotImplementedError, ValueError, TypeError):
        return False


def _general_solutions(residual, var):
    """All real solutions of a periodic equation as general formulas, e.g. x = 2nπ + π/6 (n ∈ ℤ).
    Returns (lines, proved_empty) or None if SymPy can't express them."""
    try:
        sols = sp.solveset(residual, var, domain=sp.S.Reals)
    except (NotImplementedError, ValueError, TypeError):
        return None
    if sols == sp.S.EmptySet:
        return [], True
    parts = sols.args if isinstance(sols, sp.Union) else (sols,)
    lines = []
    for part in parts:
        if isinstance(part, sp.ImageSet) and len(part.lamda.variables) == 1:
            n = part.lamda.variables[0]
            lines.append(f"{var} = {fmt(part.lamda.expr.subs(n, sp.Symbol('n')))}")
        elif isinstance(part, sp.FiniteSet):
            lines += [f"{var} = {fmt(v)}" for v in part]
        else:
            return None
    return lines, False


def _verify_solutions(eqs, sols):
    """Substitute every solution back: exact zero is a proof, otherwise fall back to numerics."""
    proved = all(sp.simplify((e.lhs - e.rhs).subs(sol)) == 0 for sol in sols for e in eqs)
    if proved:
        return ("Verification", "Proved: substituting each solution into the equation gives exactly 0.")
    if len(eqs) == 1 and all(len(s) == 1 for s in sols):
        var = next(iter(sols[0]))
        return _verify(lambda: numeric.check_roots(eqs[0].lhs - eqs[0].rhs, var, [s[var] for s in sols]))
    return ("Verification", "Could not confirm every solution by substitution.")


def _expression_pods(expr, raw):
    pods = [("Input", _pretty_input(raw))]
    if not expr.free_symbols:
        exact = sp.simplify(expr)
        undefined = _undefined(exact)
        if undefined:
            return pods + [("Result", undefined)]
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
            general = _general_solutions(simple, var) if _periodic(simple, var) else None
            if general is not None and general[0]:
                pods.append(("Real roots", "\n".join(general[0]) + "\n(n is any integer)"))
            elif general is None:
                roots = sp.solve(sp.Eq(simple, 0), var)
                if roots:
                    pods.append(("Roots", ",  ".join(f"{var} = {fmt(r)}" for r in roots[:8])))
        except (NotImplementedError, ValueError, TypeError):
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
        d = real_diff(expr, var)
        pods = [("Input", f"d/d{var} [{fmt(expr)}]"), ("Derivative", fmt(sp.simplify(d)))]
        d2 = sp.simplify(real_diff(d, var))
        if d2.has(sp.DiracDelta):     # a corner (like |x| at 0): no classical second derivative there
            d2_text = fmt(d2.replace(sp.DiracDelta, lambda *args: 0)) + "  (undefined where the first derivative jumps)"
        else:
            d2_text = fmt(d2)
        pods.append(("Second derivative", d2_text))
        pods.append(_verify(lambda: numeric.check_derivative(expr, d, var)))
        return pods, expr

    m = _RE_INT.match(text)
    if m:
        body, var_name, lo, hi = m.groups()
        expr = parse_expr(body)
        var = _pick_var(expr, var_name)
        if lo is not None:
            a, b = parse_expr(lo), parse_expr(hi)
            val = sp.integrate(expr, (var, a, b))
            pods = [("Input", f"∫ {fmt(expr)} d{var}  from {fmt(a)} to {fmt(b)}")]
            if val.has(sp.zoo, sp.nan) or val in (sp.oo, -sp.oo):
                return pods + [("Definite integral", "Does not converge: the integrand is unbounded on the interval "
                                                     "(or the area is infinite).")], expr
            pods.append(("Definite integral", fmt(val)))
            if _needs_approx(val):
                pods.append(("Decimal approximation", _approx(val, 12)))
            if not val.free_symbols:
                pods.append(_verify(lambda: numeric.check_definite_integral(expr, var, a, b, val)))
            return pods, expr
        val = sp.integrate(expr, var)
        if val.has(sp.Integral):
            return [("Input", f"∫ {fmt(expr)} d{var}"), ("Indefinite integral", "No closed form found")], expr
        pods = [("Input", f"∫ {fmt(expr)} d{var}"), ("Indefinite integral", fmt(val) + " + C"),
                _verify(lambda: numeric.check_antiderivative(val, expr, var))]
        from ..reasoning.derivation import _domain_shrinks
        lost = _domain_shrinks(expr, val, var)
        if lost:
            pods.append(("Domain note", f"This antiderivative is only valid where it is defined: it is undefined on "
                                        f"{lost}, where the integrand is defined. Replacing ln(u) by ln|u| gives one "
                                        f"valid on both sides."))
        return pods, expr

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
