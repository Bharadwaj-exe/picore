"""Mistake Detective core: steps, diagnoses, the rule registry, and matching helpers.

How diagnosis works
-------------------
A *mal-rule* is a rule students apply that is NOT valid, e.g. (a + b)² → a² + b².
Pi Core knows a catalogue of them. When a step is invalid, each mal-rule is applied
to the PREVIOUS step (at every place in its tree where it fits). If one of the
results matches what the student actually wrote, Pi Core knows exactly which
misconception produced the step, and can say which real rule was violated and what
the correct transformation is.

This is deterministic: a diagnosis is only reported when re-applying the mal-rule
reproduces the student's step. If nothing matches, Pi Core says the step is wrong
(with evidence) but does not guess why.

Adding a rule: subclass MalRule (or RewriteRule) in one of the rule modules and
decorate it with @register. Nothing else needs to change.
"""
from dataclasses import dataclass, field

import sympy as sp

from ...lang import ast as A
from ...lang.sympy_backend import to_sympy
from .. import numeric
from ..equivalence import symbolic_zero


@dataclass
class Step:
    text: str
    node: object                      # AST (Equation or expression); None for 'or' answers
    kind: str                         # "expr" | "equation" | "solutions"
    value: object                     # SymPy expr, Eq, or FiniteSet for solutions
    var: object = None                # solved-for variable (solutions / single-variable steps)
    label: str = ""                   # claimed justification, e.g. "expand" from "[expand]"

    @property
    def residual(self):
        """lhs − rhs for an equation; the expression itself otherwise."""
        if self.kind == "equation":
            return self.value.lhs - self.value.rhs
        return self.value


@dataclass
class Diagnosis:
    rule: str                          # stable id, e.g. "algebra.square_of_sum"
    category: str                      # "Algebra · incorrect expansion"
    title: str                         # one-line name of the violated rule
    explanation: str                   # why the step is invalid
    correct: str = ""                  # the correct transformation, when known
    severity: str = "error"            # "error" | "warning" (valid only with extra care)
    evidence: list = field(default_factory=list)

    def text(self):
        lines = [f"{self.category}: {self.title}", self.explanation]
        if self.correct:
            lines.append("Correct: " + self.correct)
        return "\n".join(lines)


class MalRule:
    """Base class. ``detect`` returns a Diagnosis if this misconception explains prev → cur."""
    id = ""
    category = ""
    applies_to = ("expr", "equation")  # step kinds this rule can explain

    def detect(self, prev, cur):
        raise NotImplementedError


RULES = []


def register(cls):
    RULES.append(cls())
    return cls


# ---- matching helpers ---------------------------------------------------------------

def fmt(e):
    from ...engine.local import fmt as _fmt
    return _fmt(e)


def same_value(a, b):
    """True if two SymPy expressions are equal (symbolically, or at every sample point)."""
    try:
        if symbolic_zero(sp.expand(a - b)):
            return True
    except (TypeError, ValueError):
        pass
    ev = numeric.agree(a, b, n=6)
    return ev.passed


def proportional(r1, r2):
    """True if residuals r1 = k·r2 for a non-zero constant k (same equation, rearranged/scaled)."""
    if r2 == 0 or r1 == 0:
        return r1 == r2
    try:
        ratio = sp.cancel(sp.together(r1 / r2))
        if ratio.is_number and ratio != 0 and ratio.is_finite:
            return True
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    # numeric fallback: ratio is the same constant at every sample point
    symbols = r1.free_symbols | r2.free_symbols
    ratios = []
    for point in numeric.sample_points(symbols, 8):
        a, b = numeric._value(r1, point), numeric._value(r2, point)
        if a is None or b is None or abs(b) < 1e-12:
            continue
        ratios.append(a / b)
    return len(ratios) >= 4 and abs(ratios[0]) > 1e-12 and all(numeric.close(r, ratios[0], 1e-7) for r in ratios)


def rewrite_each(node, fn):
    """Yield (whole_tree, info, subtree) with ``fn`` applied at exactly one place in the tree.

    ``fn(subtree)`` returns a list of (replacement, info) pairs.
    """
    for new, info in fn(node):
        yield new, info, node
    kids = A.children(node)
    for i, child in enumerate(kids):
        for new_child, info, at in rewrite_each(child, fn):
            yield A.with_children(node, kids[:i] + (new_child,) + kids[i + 1:]), info, at


def matches_step(candidate_tree, cur):
    """Does applying a mal-rule to the previous step reproduce the current step?"""
    try:
        cand = to_sympy(candidate_tree)
    except Exception:
        return False
    if cur.kind == "equation" and isinstance(cand, sp.Equality):
        return proportional(sp.expand(cand.lhs - cand.rhs), sp.expand(cur.residual))
    if cur.kind == "expr" and not isinstance(cand, sp.Equality):
        return same_value(cand, cur.value)
    if cur.kind == "solutions" and isinstance(cand, sp.Equality) and cur.var is not None:
        try:
            sols = sp.solveset(cand.lhs - cand.rhs, cur.var, domain=sp.S.Complexes)
        except (NotImplementedError, ValueError, TypeError):
            return False
        return sols == cur.value
    return False


class RewriteRule(MalRule):
    """A mal-rule expressed as an AST rewrite.

    Subclasses implement ``buggy(node)`` returning [(wrong_replacement, correct_sympy_or_None)]
    for any subtree the misconception applies to, and the ``title``/``explanation`` texts.
    """
    title = ""
    explanation = ""

    def buggy(self, node):
        return []

    def describe(self, at, info):
        """(title, explanation) for a match at subtree ``at``. Override to customise."""
        return self.title, self.explanation

    def correct_for(self, at, info):
        """The correct value of subtree ``at`` (SymPy), or None. Default: ``info`` itself."""
        return info if isinstance(info, sp.Basic) else None

    def detect(self, prev, cur):
        if prev.node is None:
            return None
        for tree, info, at in rewrite_each(prev.node, self.buggy):
            if matches_step(tree, cur):
                title, why = self.describe(at, info)
                correct = self.correct_for(at, info)
                if isinstance(correct, str):
                    fix = correct
                else:
                    fix = f"{A.to_text(at)} = {fmt(correct)}" if correct is not None else ""
                return Diagnosis(self.id, self.category, title, why, fix)
        return None


def run_rules(prev, cur):
    """First registered rule whose misconception reproduces ``cur`` from ``prev``."""
    for rule in RULES:
        if prev.kind not in rule.applies_to:
            continue
        try:
            found = rule.detect(prev, cur)
        except (NotImplementedError, ValueError, TypeError, ZeroDivisionError, RecursionError, AttributeError):
            continue
        if found:
            return found
    return None
