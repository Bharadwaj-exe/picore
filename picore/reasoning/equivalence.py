"""Expression equivalence with domain awareness.

``compare(a, b)`` answers "are these the same expression?" with one of five verdicts:

    EXACT        equal wherever either is defined, and defined in the same places
    CONDITIONAL  equal where both are defined, but their domains differ
                 e.g. (x² − 1)/(x − 1) and x + 1 agree except at x = 1
    NUMERIC      no symbolic proof found, but they agree at every test point
    NOT          a concrete counterexample exists
    UNKNOWN      nothing could be established

Symbolic simplification is tried first and is the only way to reach EXACT or
CONDITIONAL. Numerical sampling only ever supports NUMERIC or finds a
counterexample (NOT). Domains come from the AST (see lang.sympy_backend), because
SymPy forgets them: it turns x/x into 1.
"""
from dataclasses import dataclass, field

import sympy as sp

from ..lang import ast as A
from ..lang.sympy_backend import domain_conditions, excluded_points, to_sympy
from . import numeric

EXACT, CONDITIONAL, NUMERIC, NOT, UNKNOWN = "exact", "conditional", "numeric", "not", "unknown"

VERDICT_TEXT = {
    EXACT: "Equivalent",
    CONDITIONAL: "Equivalent, with a domain restriction",
    NUMERIC: "Probably equivalent (numerical evidence only)",
    NOT: "Not equivalent",
    UNKNOWN: "Unable to decide",
}


@dataclass
class EquivalenceResult:
    verdict: str
    reasons: list = field(default_factory=list)       # human-readable reasoning, in order
    restrictions: list = field(default_factory=list)  # e.g. ["x ≠ 1"]
    evidence: object = None                           # numeric.Evidence, if sampling was used

    @property
    def equivalent(self):
        return self.verdict in (EXACT, CONDITIONAL, NUMERIC)

    @property
    def title(self):
        return VERDICT_TEXT[self.verdict]


def _fmt(e):
    from ..engine.local import fmt
    return fmt(e)


def symbolic_zero(diff):
    """Try increasingly expensive simplifications; True only if one proves diff == 0."""
    if diff == 0:
        return True
    simplifiers = (sp.expand, sp.cancel, lambda d: sp.cancel(sp.together(d)), sp.trigsimp,
                   lambda d: sp.simplify(sp.expand_log(sp.powsimp(d))), sp.simplify)
    for simplifier in simplifiers:
        try:
            if simplifier(diff) == 0:
                return True
        except (TypeError, ValueError, NotImplementedError, RecursionError):
            continue
    return False


def _as_parts(item):
    """Accept an AST node, or text; return (sympy expr, domain conditions)."""
    if isinstance(item, str):
        from ..lang import parse
        item = parse(item)
    if isinstance(item, A.Node):
        return to_sympy(item), domain_conditions(item)
    return item, []


def _domain_set(conditions, var):
    dom = sp.S.Reals
    for c in conditions:
        try:
            dom = dom.intersect(sp.solveset(c.as_relational(), var, domain=sp.S.Reals))
        except (NotImplementedError, ValueError, TypeError):
            return None
    return dom


def compare(a, b):
    """Compare two expressions (AST nodes, text, or SymPy expressions)."""
    ea, conds_a = _as_parts(a)
    eb, conds_b = _as_parts(b)
    reasons = []
    symbols = ea.free_symbols | eb.free_symbols
    for c in conds_a + conds_b:          # x/x has no symbols left in SymPy, but its domain does
        symbols |= c.expr.free_symbols

    proved = symbolic_zero(ea - eb)
    assumed = ""
    if not proved and len(symbols) == 1:
        proved, assumed = _zero_on_common_domain(ea, eb, conds_a, conds_b, next(iter(symbols)))
    if proved:
        reasons.append(f"Symbolic: ({_fmt(ea)}) − ({_fmt(eb)}) simplifies to 0{assumed}.")
        restrictions = _domain_difference(conds_a, conds_b, symbols, reasons)
        if restrictions:
            return EquivalenceResult(CONDITIONAL, reasons, restrictions)
        if conds_a or conds_b:
            reasons.append("Both sides are defined in exactly the same places.")
        return EquivalenceResult(EXACT, reasons)

    relationals = [c.as_relational() for c in conds_a + conds_b]
    ev = numeric.agree(ea, eb, symbols, n=10, conditions=relationals,
                       method="Both sides evaluated at random points")
    if ev.status == "failed":
        reasons.append("Symbolic simplification did not show they are equal.")
        reasons.append(ev.summary() + ".")
        return EquivalenceResult(NOT, reasons, evidence=ev)
    if ev.status == "passed":
        reasons.append("Symbolic simplification could not prove they are equal.")
        reasons.append(ev.summary() + ".")
        return EquivalenceResult(NUMERIC, reasons, evidence=ev)
    reasons.append("Could not simplify the difference to 0 or find valid test points.")
    return EquivalenceResult(UNKNOWN, reasons, evidence=ev)


def _zero_on_common_domain(ea, eb, conds_a, conds_b, var):
    """Retry the symbolic proof assuming what both domains guarantee (e.g. x > 0 for logs).

    Identities like ln(x²) = 2·ln(x) only hold where the logs are defined; SymPy will
    only apply them when told the variable is positive.
    """
    common = _domain_set(conds_a + conds_b, var)
    if common is None or common == sp.S.Reals:
        return False, ""
    for assumption, region, words in (("positive", sp.Interval.open(0, sp.oo), "x > 0"),
                                      ("nonnegative", sp.Interval(0, sp.oo), "x ≥ 0")):
        if common.is_subset(region):
            assumed_var = sp.Symbol(var.name, **{assumption: True})
            diff = (ea - eb).subs(var, assumed_var)
            if symbolic_zero(diff):
                return True, f" when {words.replace('x', var.name)} (which both domains require)"
    return False, ""


def fmt_set(s):
    """Interval(-oo, 0) -> (-∞, 0); unions joined with ∪."""
    if isinstance(s, sp.Interval):
        left = "(" if s.left_open or s.start == -sp.oo else "["
        right = ")" if s.right_open or s.end == sp.oo else "]"
        return f"{left}{_fmt(s.start)}, {_fmt(s.end)}{right}"
    if isinstance(s, sp.Union):
        return " ∪ ".join(fmt_set(a) for a in s.args)
    if isinstance(s, sp.FiniteSet):
        return "{" + ", ".join(_fmt(a) for a in s) + "}"
    return _fmt(s)


def _domain_difference(conds_a, conds_b, symbols, reasons):
    """Describe where exactly one side is undefined. Returns restriction strings (empty if none)."""
    if not conds_a and not conds_b:
        return []
    if len(symbols) == 1:
        var = next(iter(symbols))
        da, db = _domain_set(conds_a, var), _domain_set(conds_b, var)
        if da is not None and db is not None:
            if da == db:
                return []
            restrictions = []
            only_b = sp.Complement(db, da)     # where b is defined but a isn't
            only_a = sp.Complement(da, db)
            for missing, side, other in ((only_b, "left", "right"), (only_a, "right", "left")):
                if missing == sp.S.EmptySet:
                    continue
                if isinstance(missing, sp.FiniteSet):
                    pts = ", ".join(f"{var} = {_fmt(p)}" for p in missing)
                    reasons.append(f"Domain: the {side} side is undefined at {pts}, but the {other} side is defined there.")
                    restrictions += [f"{var} ≠ {_fmt(p)}" for p in missing]
                else:
                    reasons.append(f"Domain: the {side} side is undefined on {fmt_set(missing)}, "
                                   f"but the {other} side is defined there.")
                    restrictions.append(f"{var} ∉ {fmt_set(missing)}")
            reasons.append("So they are equal only where both are defined: " + ", ".join(restrictions) + ".")
            return restrictions
    # several variables: compare the conditions themselves
    keys_a = {(sp.simplify(c.expr), c.kind) for c in conds_a}
    keys_b = {(sp.simplify(c.expr), c.kind) for c in conds_b}
    extra = [c for c in conds_a if (sp.simplify(c.expr), c.kind) not in keys_b] + \
            [c for c in conds_b if (sp.simplify(c.expr), c.kind) not in keys_a]
    if not extra:
        return []
    restrictions = [c.describe() for c in extra]
    reasons.append("Domain: only one side requires " + "; ".join(restrictions) + ".")
    return restrictions


def solution_set(node, var):
    """Solutions of an equation AST over ℂ, minus points where the equation is undefined."""
    expr = to_sympy(node)
    residual = expr.lhs - expr.rhs if isinstance(expr, sp.Equality) else expr
    sols = sp.solveset(sp.simplify(residual), var, domain=sp.S.Complexes)
    bad = excluded_points(domain_conditions(node), var)
    if bad and isinstance(sols, sp.FiniteSet):
        sols = sp.FiniteSet(*[s for s in sols if s not in bad])
    elif bad:
        sols = sp.Complement(sols, sp.FiniteSet(*bad))
    return sols
