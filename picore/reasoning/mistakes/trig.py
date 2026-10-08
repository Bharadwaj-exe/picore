"""Trigonometry mal-rules. (Identity misuse like sin(2x) → 2 sin x lives in algebra.FunctionTreatedAsLinear.)"""
import sympy as sp

from ...lang import ast as A
from ...lang.sympy_backend import to_sympy
from .core import Diagnosis, MalRule, fmt, register, same_value

TRIG = {"sin", "cos", "tan", "cot", "sec", "csc"}


def _in_degrees(node):
    """Same tree, but every trig argument converted from degrees to radians."""
    if isinstance(node, A.Call) and node.func in TRIG:
        arg = A.BinOp("/", A.BinOp("*", node.args[0], A.Const("pi")), A.Num("180"))
        return A.Call(node.func, (arg,))
    kids = A.children(node)
    return A.with_children(node, tuple(_in_degrees(k) for k in kids)) if kids else node


@register
class DegreesVsRadians(MalRule):
    id = "trig.degrees_radians"
    category = "Trigonometry · degrees vs radians"
    applies_to = ("expr",)

    def detect(self, prev, cur):
        if cur.kind != "expr" or prev.node is None:
            return None
        has_trig = any(isinstance(n, A.Call) and n.func in TRIG for n in A.walk(prev.node))
        if not has_trig or prev.value.free_symbols:
            return None
        as_degrees = sp.nsimplify(sp.simplify(to_sympy(_in_degrees(prev.node))))
        if same_value(as_degrees, cur.value) and not same_value(prev.value, cur.value):
            return Diagnosis(
                self.id, self.category, "Angles are in radians",
                f"This step treats the angle as degrees. In Pi Core (and in calculus) trig functions take radians: "
                f"{A.to_text(prev.node)} ≈ {fmt(sp.N(prev.value, 6))}. For degrees, multiply by π/180.",
                f"{A.to_text(prev.node)} ≈ {fmt(sp.N(prev.value, 6))} in radians; "
                f"{A.to_text(prev.node)}° = {fmt(as_degrees)} only if the angle is in degrees")
        return None
