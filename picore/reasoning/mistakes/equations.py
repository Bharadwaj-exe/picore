"""Equation mal-rules: moving terms, dropped terms, dividing by zero, square roots, squaring."""
import sympy as sp

from ...lang import ast as A
from ...lang.sympy_backend import to_sympy
from .. import numeric
from ..equivalence import solution_set
from .core import Diagnosis, MalRule, fmt, proportional, register


def single_var(*steps):
    syms = set()
    for s in steps:
        if s.kind == "solutions":
            syms.add(s.var)
        else:
            syms |= s.value.free_symbols
    return next(iter(syms)) if len(syms) == 1 else None


def solutions(step, var):
    """Exact solution set of a step (domain-aware); may be infinite or unevaluated."""
    if step.kind == "solutions":
        return step.value
    if step.kind == "disjunction":
        out = sp.S.EmptySet
        for alt in step.alternatives:
            out = out.union(solution_set(alt, var))
        return out
    return solution_set(step.node, var)


def is_finite(sols):
    return isinstance(sols, sp.FiniteSet) or sols == sp.S.EmptySet


def _conditions(step):
    from ...lang.sympy_backend import domain_conditions
    nodes = step.alternatives if step.kind == "disjunction" else ([step.node] if step.node is not None else [])
    out = []
    for n in nodes:
        out += domain_conditions(n)
    return out


def defined_at(step, var, r):
    """False if the step's equation is undefined at r (e.g. tan at π/2, 1/(x-1) at 1)."""
    from ...lang.sympy_backend import holds
    return holds(_conditions(step), {var: r}) is not False


def holds_at(step, var, r):
    """Does the step's equation hold at the real number r? (None if it can't be evaluated)
    A point outside the step's domain never satisfies it."""
    if step.kind != "solutions" and not defined_at(step, var, r):
        return False
    if step.kind == "solutions":
        vals = [numeric._value(v, {}) for v in step.value]
        return any(v is not None and abs(v - r) <= 1e-7 * max(1.0, abs(r)) for v in vals)
    eqs = [to_sympy(a) for a in step.alternatives] if step.kind == "disjunction" else [step.value]
    seen = False
    for eq in eqs:
        residual = eq.lhs - eq.rhs
        v = numeric._value(residual, {var: r})
        if v is None or not numeric._is_real(v):
            continue
        seen = True
        terms = sp.Add.make_args(sp.expand(residual))
        scale = max([1.0] + [abs(t) for t in (numeric._value(t, {var: r}) for t in terms) if t is not None])
        if abs(v) <= 1e-8 * scale:
            return True
    return False if seen else None


def real_candidates(step, var):
    """Real numbers that solve the step: exact values for answers, numerical roots otherwise."""
    if step.kind == "solutions":
        out = []
        for v in step.value:
            z = numeric._value(v, {})
            if z is not None and numeric._is_real(z):
                out.append(z.real)
        return out
    eqs = [to_sympy(a) for a in step.alternatives] if step.kind == "disjunction" else [step.value]
    roots = []
    for eq in eqs:
        roots += numeric.real_roots(eq.lhs - eq.rhs, var)
    return [r for r in roots if defined_at(step, var, r)]


def numeric_difference(prev, cur, var):
    """Real solutions lost and gained between two steps, found numerically in numeric.ROOT_RANGE.

    Returns (lost, gained, any_found). Every reported value is a verified real solution of
    one step at which the other step's equation fails: concrete evidence, not a guess.
    The search is not exhaustive (see numeric.real_roots)."""
    r_prev, r_cur = real_candidates(prev, var), real_candidates(cur, var)
    lost = [r for r in r_prev if holds_at(prev, var, r) and holds_at(cur, var, r) is False]
    gained = [r for r in r_cur if holds_at(cur, var, r) and holds_at(prev, var, r) is False]
    return lost, gained, bool(r_prev or r_cur)


def show_approx(values, var):
    return " or ".join(f"{var} ≈ {v:.6g}" for v in values[:4]) + (" …" if len(values) > 4 else "")


def show_solutions(sols, var):
    if isinstance(sols, sp.FiniteSet):
        if not sols:
            return "no solutions"
        return " or ".join(f"{var} = {fmt(s)}" for s in sols)
    return f"{var} ∈ {fmt(sols)}"


def _terms(expr):
    return sp.Add.make_args(sp.expand(expr))


def _written_terms(node):
    """Top-level terms of one side AS WRITTEN: 3(x + 1) - 2 -> [3(x + 1), -2]."""
    from .algebra import _terms as ast_terms
    out = []
    for t in ast_terms(node):
        out.append(-to_sympy(t.operand) if isinstance(t, A.Neg) else to_sympy(t))
    return out


def _side_terms(step):
    """(side, term) pairs: the terms as written, then any extra terms of the expanded sides."""
    seen = set()
    for side, ast_side, value in (("left", getattr(step.node, "lhs", None), step.value.lhs),
                                  ("right", getattr(step.node, "rhs", None), step.value.rhs)):
        written = _written_terms(ast_side) if ast_side is not None else []
        for t in written + list(_terms(value)):
            if (side, t) not in seen and t != 0:
                seen.add((side, t))
                yield side, t


def _fixed(cur, wrong, P):
    """The student's equation with the error undone: same left side, corrected right side."""
    k = sp.cancel(sp.expand(cur.residual) / wrong)
    return f"{fmt(cur.value.lhs)} = {fmt(sp.expand(cur.value.rhs + cur.residual - k * P))}"


@register
class SignErrorMovingTerm(MalRule):
    id = "equations.sign_error_moving_term"
    category = "Equations · sign error"
    applies_to = ("equation",)

    def detect(self, prev, cur):
        if cur.kind != "equation":
            return None
        P, C = sp.expand(prev.residual), sp.expand(cur.residual)
        for side, t in _side_terms(prev):
            # moving t correctly keeps the residual; moving it without changing sign is off by 2t
            wrong = sp.expand(P - 2 * t if side == "left" else P + 2 * t)
            if wrong != 0 and proportional(wrong, C):
                return Diagnosis(
                    self.id, self.category, "A term that changes sides must change sign",
                    f"'{fmt(t)}' moved from the {side} side to the other side without changing its sign. "
                    f"Moving a term across '=' means subtracting it from both sides, so +a becomes −a.",
                    _fixed(cur, wrong, P))
        return None


@register
class OneSideOnly(MalRule):
    id = "equations.one_side_only"
    category = "Equations · unbalanced operation"
    applies_to = ("equation",)

    def detect(self, prev, cur):
        if cur.kind != "equation":
            return None
        L, R = sp.expand(prev.value.lhs), sp.expand(prev.value.rhs)
        P, C = L - R, sp.expand(cur.residual)
        for _side, t in _side_terms(prev):
            for wrong, verb in ((P - t, "taken away from"), (P + t, "added to")):
                wrong = sp.expand(wrong)
                if wrong != 0 and proportional(wrong, C):
                    return Diagnosis(
                        self.id, self.category, "Do the same thing to both sides",
                        f"'{fmt(t)}' was {verb} one side of the equation but not the other, so the two sides "
                        f"are no longer equal. An equation stays true only if both sides change the same way.",
                        _fixed(cur, wrong, P))
        for side, this, other in (("left", L, R), ("right", R, L)):      # 4(p - 1) = 2p + 6 -> p - 1 = 2p + 6
            k = sp.primitive(this)[0] if this.free_symbols and this.is_polynomial() else 1
            if k in (0, 1):
                continue
            wrong = sp.expand(this / k - other) if side == "left" else sp.expand(other - this / k)
            if wrong != 0 and proportional(wrong, C):
                fixed_l, fixed_r = (this / k, other / k) if side == "left" else (other / k, this / k)
                return Diagnosis(
                    self.id, self.category, "Do the same thing to both sides",
                    f"The {side} side was divided by {fmt(k)} but the other side was not. Dividing an equation "
                    f"by {fmt(k)} means dividing EVERY term on BOTH sides.",
                    f"{fmt(sp.expand(fixed_l))} = {fmt(sp.expand(fixed_r))}")
        return None


@register
class DroppedTerm(MalRule):
    """Expressions only; in equations a vanished term is OneSideOnly."""
    id = "algebra.dropped_term"
    category = "Algebra · dropped term"
    applies_to = ("expr",)

    def detect(self, prev, cur):
        if prev.kind == "expr" and cur.kind == "expr":
            for t in _terms(prev.value):
                if len(_terms(prev.value)) > 1 and sp.expand(prev.value - t - cur.value) == 0:
                    return Diagnosis(self.id, self.category, "A term went missing",
                                     f"The term '{fmt(t)}' disappeared between these steps. Every term has to be carried along.",
                                     f"{fmt(prev.value)} (nothing removed)", kind="descriptive")
        return None


def _numeric_lost(prev, cur, var, q):
    """Real roots of q (in the search range) that solve prev but not cur."""
    return [r for r in numeric.real_roots(q, var) if holds_at(prev, var, r) and holds_at(cur, var, r) is False]


@register
class DividedByZeroRisk(MalRule):
    id = "equations.division_by_expression"
    category = "Equations · missed roots"
    applies_to = ("equation",)

    def detect(self, prev, cur):
        var = single_var(prev, cur)
        if var is None or cur.kind not in ("equation", "solutions"):
            return None
        C = cur.residual if cur.kind == "equation" else sp.Mul(*[var - s for s in cur.value])
        if C == 0:
            return None
        q = sp.factor(sp.cancel(sp.together(prev.residual / C)))
        if q.is_number or var not in q.free_symbols or sp.fraction(q)[1].has(var):
            return None
        # Only a real division if q was a common factor of BOTH sides (x² = 3x → x = 3 divides by x;
        # x² = 4 → x = 2 does not divide by anything, it drops the negative root instead).
        common = sp.gcd(sp.expand(prev.value.lhs), sp.expand(prev.value.rhs))
        if sp.fraction(sp.cancel(common / q))[1].has(var):
            return None
        s_prev, s_cur = solutions(prev, var), solutions(cur, var)
        if is_finite(s_prev) and is_finite(s_cur):
            lost = s_prev - s_cur
            if not lost or not all(sp.simplify(q.subs(var, r)) == 0 for r in lost):
                return None
            where, correct = show_solutions(lost, var), show_solutions(s_prev, var)
        else:
            lost = _numeric_lost(prev, cur, var, q)
            if not lost:
                return None
            where, correct = show_approx(lost, var) + " (found numerically)", f"{fmt(q)} = 0 or {fmt(C)} = 0"
        return Diagnosis(
            self.id, self.category, "Dividing by something that can be zero loses solutions",
            f"Both sides were divided by {fmt(q)}, which equals 0 when {where}. Division by zero isn't "
            f"allowed, so that case has to be handled separately, and here it was lost.",
            f"factor instead: {fmt(sp.factor(prev.residual))} = 0, so {correct}")


def _has_even_power(node):
    for n in A.walk(node):
        if isinstance(n, A.BinOp) and n.op == "^" and isinstance(n.right, A.Num) and n.right.value.isdigit() \
                and int(n.right.value) % 2 == 0 and any(isinstance(m, A.Var) for m in A.walk(n.left)):
            return n
    return None


def _has_sqrt(node):
    return any(isinstance(n, A.Call) and n.func == "sqrt" for n in A.walk(node)) if node is not None else False


@register
class SquareRootWithVariableOnOtherSide(MalRule):
    """x² = 5x − 6  →  x = 5 ± √6: values produced by 'square-rooting' while x is still on the other side."""
    id = "equations.sqrt_with_variable"
    category = "Equations · incorrect rearrangement"
    applies_to = ("equation",)

    def detect(self, prev, cur):
        var = single_var(prev, cur)
        if var is None or prev.node is None or not isinstance(prev.node, A.Equation) or cur.kind != "solutions":
            return None
        if not sp.expand(prev.residual).is_polynomial(var):
            return None            # e.g. 2^x = x^2: the advice below (collect and factor) would not apply
        s_prev = solutions(prev, var)
        if not is_finite(s_prev) or all(v in s_prev for v in cur.value):
            return None            # the student's values are genuine solutions: not this mistake
        for side, other in ((prev.node.lhs, prev.value.rhs), (prev.node.rhs, prev.value.lhs)):
            if isinstance(side, A.BinOp) and side.op == "^" and _has_even_power(side) is side and var in other.free_symbols:
                P = sp.expand(prev.residual)
                return Diagnosis(
                    self.id, self.category, "Square-rooting doesn't solve this: the other side still contains the variable",
                    f"Square-rooting {A.to_text(side)} = {fmt(other)} only gives {var} = ±√({fmt(other)}), which still "
                    f"contains {var}, so it is not yet an answer, and the values in this step do not satisfy the "
                    f"equation. Collect everything on one side and factor or use the quadratic formula.",
                    f"{fmt(P)} = 0  →  {fmt(sp.factor(P))} = 0  →  {show_solutions(s_prev, var)}")
        return None


@register
class PositiveRootOnly(MalRule):
    id = "equations.positive_root_only"
    category = "Equations · missed roots"
    applies_to = ("equation",)

    def detect(self, prev, cur):
        var = single_var(prev, cur)
        if var is None or prev.node is None or _has_even_power(prev.node) is None:
            return None
        s_prev, s_cur = solutions(prev, var), solutions(cur, var)
        if not (is_finite(s_prev) and is_finite(s_cur)):
            return None
        lost, gained = s_prev - s_cur, s_cur - s_prev
        if lost and not gained and s_cur:
            power = _has_even_power(prev.node)
            return Diagnosis(
                self.id, self.category, "A square root has two signs: ±",
                f"If {A.to_text(power)} equals something positive, the base can be the positive OR the negative "
                f"square root. Only the positive one was kept, so {show_solutions(lost, var)} was lost.",
                show_solutions(s_prev, var))
        return None


@register
class SquaringBothSides(MalRule):
    id = "equations.squaring"
    category = "Equations · extraneous roots"
    applies_to = ("equation",)

    def detect(self, prev, cur):
        var = single_var(prev, cur)
        if var is None or prev.kind != "equation" or cur.kind != "equation":
            return None
        L, R = prev.value.lhs, prev.value.rhs
        sq, cr = sp.expand(L ** 2 - R ** 2), sp.expand(cur.residual)
        squared = sq != 0 and cr != 0 and proportional(sq, cr)
        if not squared and not _has_sqrt(prev.node):
            return None
        s_prev, s_cur = solutions(prev, var), solutions(cur, var)
        if is_finite(s_prev) and is_finite(s_cur):
            gained, lost = s_cur - s_prev, s_prev - s_cur
            if not gained or lost:
                return None
            checks = [f"at {var} = {fmt(r)} the left side is {fmt(sp.simplify(L.subs(var, r)))} "
                      f"but the right side is {fmt(sp.simplify(R.subs(var, r)))}" for r in gained]
            what, keep = show_solutions(gained, var) + " is extraneous: " + "; ".join(checks), show_solutions(s_prev, var)
        else:
            if not squared:
                return None
            lost, gained, _ = numeric_difference(prev, cur, var)
            if not gained or lost:
                return None
            what = show_approx(gained, var) + " solve the squared equation but not the original (found numerically)"
            keep = "the solutions of the original equation"
        return Diagnosis(
            self.id, self.category, "Squaring both sides can add solutions that don't work",
            f"Squaring is allowed, but it also accepts solutions of −(left) = right. {what}.",
            f"keep only answers that satisfy the original equation: {keep}",
            severity="warning")
