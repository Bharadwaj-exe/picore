"""Equation mal-rules: moving terms, dropped terms, dividing by zero, square roots, squaring."""
import sympy as sp

from ...lang import ast as A
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
    if step.kind == "solutions":
        return step.value
    return solution_set(step.node, var)


def show_solutions(sols, var):
    if isinstance(sols, sp.FiniteSet):
        if not sols:
            return "no solutions"
        return " or ".join(f"{var} = {fmt(s)}" for s in sols)
    return f"{var} ∈ {fmt(sols)}"


def _terms(expr):
    return sp.Add.make_args(sp.expand(expr))


def _side_terms(step):
    for t in _terms(step.value.lhs):
        yield "left", t
    for t in _terms(step.value.rhs):
        yield "right", t


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
            wrong = P - 2 * t if side == "left" else P + 2 * t
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
        P, C = sp.expand(prev.residual), sp.expand(cur.residual)
        for _side, t in _side_terms(prev):
            for wrong, verb in ((P - t, "taken away from"), (P + t, "added to")):
                if wrong != 0 and proportional(wrong, C):
                    return Diagnosis(
                        self.id, self.category, "Do the same thing to both sides",
                        f"'{fmt(t)}' was {verb} one side of the equation but not the other, so the two sides "
                        f"are no longer equal. An equation stays true only if both sides change the same way.",
                        _fixed(cur, wrong, P))
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
                                     f"{fmt(prev.value)} (nothing removed)")
            return None
        return None


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
        lost = solutions(prev, var) - solutions(cur, var)
        if not (isinstance(lost, sp.FiniteSet) and lost) or not all(sp.simplify(q.subs(var, r)) == 0 for r in lost):
            return None
        return Diagnosis(
            self.id, self.category, "Dividing by something that can be zero loses solutions",
            f"Both sides were divided by {fmt(q)}, which equals 0 when {show_solutions(lost, var)}. "
            f"Division by zero isn't allowed, so that case has to be handled separately and was lost.",
            f"factor instead: {fmt(sp.factor(prev.residual))} = 0, so {show_solutions(solutions(prev, var), var)}")


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
    """x² = 5x − 6  →  x = 5 ± √6: 'square-rooting' while x is still on the other side."""
    id = "equations.sqrt_with_variable"
    category = "Equations · incorrect rearrangement"
    applies_to = ("equation",)

    def detect(self, prev, cur):
        var = single_var(prev, cur)
        if var is None or prev.node is None or not isinstance(prev.node, A.Equation):
            return None
        for side, other in ((prev.node.lhs, prev.value.rhs), (prev.node.rhs, prev.value.lhs)):
            if isinstance(side, A.BinOp) and side.op == "^" and _has_even_power(side) is side and var in other.free_symbols:
                if cur.kind == "solutions" or (cur.kind == "equation" and cur.value.lhs == var
                                               and var not in cur.value.rhs.free_symbols):
                    P = sp.expand(prev.residual)
                    return Diagnosis(
                        self.id, self.category, "You can't square-root while the other side still contains the variable",
                        f"Square-rooting {A.to_text(side)} only isolates {var} if the other side is free of {var}, "
                        f"but {fmt(other)} still contains it. This is a quadratic: collect everything on one side "
                        f"and factor or use the quadratic formula.",
                        f"{fmt(P)} = 0  →  {fmt(sp.factor(P))} = 0  →  {show_solutions(solutions(prev, var), var)}")
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
        if not (isinstance(s_prev, sp.FiniteSet) and isinstance(s_cur, sp.FiniteSet)):
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
        if var is None or not _has_sqrt(prev.node) or prev.kind != "equation":
            return None
        s_prev, s_cur = solutions(prev, var), solutions(cur, var)
        if not (isinstance(s_prev, sp.FiniteSet) and isinstance(s_cur, sp.FiniteSet)):
            return None
        gained = s_cur - s_prev
        if not gained or (s_prev - s_cur):
            return None
        L, R = prev.value.lhs, prev.value.rhs
        checks = []
        for r in gained:
            checks.append(f"at {var} = {fmt(r)} the left side is {fmt(sp.simplify(L.subs(var, r)))} "
                          f"but the right side is {fmt(sp.simplify(R.subs(var, r)))}")
        return Diagnosis(
            self.id, self.category, "Squaring both sides can add solutions that don't work",
            "Squaring is allowed, but it also accepts solutions of −(left) = right. "
            f"{show_solutions(gained, var)} is extraneous: " + "; ".join(checks) + ".",
            f"keep only answers that satisfy the original equation: {show_solutions(s_prev, var)}",
            severity="warning")
