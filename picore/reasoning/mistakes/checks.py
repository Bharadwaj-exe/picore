"""Verification-based diagnoses, tried after the specific mal-rules.

When no known misconception reproduces the step, but the step is recognisably an
expansion or a factorisation, compare coefficients and point at the wrong term.
"""
import sympy as sp

from ...lang import ast as A
from .core import Diagnosis, MalRule, fmt, register


def coefficient_differences(expected, got):
    """['the x term should be 6x, not 5x', ...] for two polynomials."""
    syms = sorted(expected.free_symbols | got.free_symbols, key=lambda s: s.name)
    if not syms:
        return []
    try:
        pe, pg = sp.Poly(sp.expand(expected), *syms), sp.Poly(sp.expand(got), *syms)
    except (sp.PolynomialError, sp.GeneratorsNeeded):
        return []
    ce, cg = dict(pe.terms()), dict(pg.terms())
    out = []
    for monom in sorted(set(ce) | set(cg), reverse=True):
        a, b = ce.get(monom, 0), cg.get(monom, 0)
        if a == b:
            continue
        mono = sp.Mul(*[s ** k for s, k in zip(syms, monom)])
        name = "constant term" if mono == 1 else f"{fmt(mono)} term"
        out.append(f"the {name} should be {fmt(a * mono)}, not {fmt(b * mono) if b else 'missing'}")
    return out


def _factors(node):
    if isinstance(node, A.BinOp) and node.op == "*":
        return _factors(node.left) + _factors(node.right)
    return [node]


def _is_product_of_sums(node):
    fs = _factors(node)
    return len(fs) >= 2 and sum(1 for f in fs if isinstance(f, A.BinOp) and f.op in "+-") >= 1


@register
class IncorrectFactorisation(MalRule):
    id = "algebra.incorrect_factorisation"
    category = "Algebra · incorrect factorisation"

    def detect(self, prev, cur):
        if cur.node is None:
            return None
        if prev.kind == "expr" and cur.kind == "expr":
            target, mine = prev.value, cur.node
        elif prev.kind == "equation" and cur.kind == "equation" and cur.value.rhs == 0:
            target, mine = prev.residual, cur.node.lhs
        else:
            return None
        if not _is_product_of_sums(mine) or not target.is_polynomial():
            return None
        from ...lang.sympy_backend import to_sympy
        expanded = sp.expand(to_sympy(mine))
        diffs = coefficient_differences(target, expanded)
        if not diffs:
            return None
        return Diagnosis(self.id, self.category, "These factors don't multiply back to the original",
                         f"Expanding {A.to_text(mine)} gives {fmt(expanded)}: " + "; ".join(diffs) + ".",
                         f"{fmt(sp.expand(target))} = {fmt(sp.factor(target))}", kind="descriptive")


@register
class IncorrectExpansion(MalRule):
    id = "algebra.incorrect_expansion"
    category = "Algebra · incorrect expansion"
    applies_to = ("expr",)

    def detect(self, prev, cur):
        if cur.kind != "expr" or prev.node is None:
            return None
        has_product = any((isinstance(n, A.BinOp) and n.op == "^" and isinstance(n.left, A.BinOp) and n.left.op in "+-")
                          or (isinstance(n, A.BinOp) and n.op == "*" and _is_product_of_sums(n))
                          for n in A.walk(prev.node))
        if not has_product or not cur.value.is_polynomial() or not prev.value.is_polynomial():
            return None
        diffs = coefficient_differences(prev.value, cur.value)
        if not diffs:
            return None
        return Diagnosis(self.id, self.category, "The expansion has a wrong coefficient",
                         "Comparing term by term with the correct expansion: " + "; ".join(diffs) + ".",
                         f"{A.to_text(prev.node)} = {fmt(sp.expand(prev.value))}", kind="descriptive")
