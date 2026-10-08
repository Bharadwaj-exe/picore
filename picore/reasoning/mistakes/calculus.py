"""Calculus mal-rules: power, product, quotient and chain rule errors, trig derivative signs.

``differentiate(node, var, bug)`` is a small differentiator that works on the AST, so
it knows where each product, quotient, power and function call is. With
``bug=(target_node, kind)`` it applies one specific *wrong* rule at one specific node
and the correct rules everywhere else. Enumerating every (node, kind) pair produces
every derivative a student could get by making exactly one of these mistakes.
"""
import sympy as sp

from ...lang import ast as A
from ...lang.sympy_backend import FUNCTIONS, to_sympy
from .core import Diagnosis, MalRule, fmt, register, same_value

BUGS = {
    "power_no_reduce": ("Calculus · power rule", "The power rule lowers the exponent by 1",
                        "d/dx xⁿ = n·xⁿ⁻¹. The exponent came down as a factor but wasn't reduced by 1."),
    "power_no_coeff": ("Calculus · power rule", "The exponent must come down as a factor",
                       "d/dx xⁿ = n·xⁿ⁻¹. The exponent was reduced, but n wasn't multiplied in front."),
    "product_naive": ("Calculus · product rule", "(uv)′ is not u′v′",
                      "The product rule is (uv)′ = u′v + uv′: differentiate one factor at a time and add."),
    "quotient_naive": ("Calculus · quotient rule", "(u/v)′ is not u′/v′",
                       "The quotient rule is (u/v)′ = (u′v − uv′)/v²."),
    "quotient_sign": ("Calculus · quotient rule", "Sign error in the quotient rule",
                      "The quotient rule has a MINUS: (u/v)′ = (u′v − uv′)/v²."),
    "quotient_order": ("Calculus · quotient rule", "Terms swapped in the quotient rule",
                       "Order matters: (u/v)′ = (u′v − uv′)/v², not (uv′ − u′v)/v²."),
    "chain_missing": ("Calculus · chain rule", "Missing the derivative of the inside",
                      "Chain rule: d/dx f(g(x)) = f′(g(x)) · g′(x). The factor g′(x) is missing."),
    "trig_sign": ("Calculus · trig derivatives", "Wrong sign on a trig derivative",
                  "d/dx sin x = cos x, but d/dx cos x = −sin x (note the minus)."),
    "exp_as_power": ("Calculus · exponentials", "aˣ is an exponential, not a power",
                     "The power rule needs a constant exponent. For a constant base, d/dx aˣ = aˣ·ln a."),
}


def differentiate(node, var, bug=None):
    """d(node)/d(var) as SymPy, optionally applying one mal-rule ``bug=(node, kind)``."""
    x = sp.Symbol(var)

    def has_var(n):
        return x in to_sympy(n).free_symbols

    def d(n):
        kind = bug[1] if bug and bug[0] is n else None
        if isinstance(n, (A.Num, A.Const)):
            return sp.Integer(0)
        if isinstance(n, A.Var):
            return sp.Integer(1 if n.name == var else 0)
        if isinstance(n, A.Neg):
            return -d(n.operand)
        if isinstance(n, A.BinOp):
            u, v = to_sympy(n.left), to_sympy(n.right)
            if n.op in "+-":
                return d(n.left) + d(n.right) if n.op == "+" else d(n.left) - d(n.right)
            du, dv = d(n.left), d(n.right)
            if n.op == "*":
                return du * dv if kind == "product_naive" else du * v + u * dv
            if n.op == "/":
                if kind == "quotient_naive":
                    return du / dv
                if kind == "quotient_sign":
                    return (du * v + u * dv) / v ** 2
                if kind == "quotient_order":
                    return (u * dv - du * v) / v ** 2
                return (du * v - u * dv) / v ** 2
            if n.op == "^":
                if x not in v.free_symbols:                      # u^n
                    inner = 1 if kind == "chain_missing" else du
                    if kind == "power_no_reduce":
                        return v * u ** v * inner
                    if kind == "power_no_coeff":
                        return u ** (v - 1) * inner
                    return v * u ** (v - 1) * inner
                if x not in u.free_symbols:                      # a^g(x)
                    if kind == "exp_as_power":
                        return v * u ** (v - 1) * dv
                    inner = 1 if kind == "chain_missing" else dv
                    return u ** v * sp.log(u) * inner
                return sp.diff(u ** v, x)
        if isinstance(n, A.Call) and len(n.args) == 1:
            t = sp.Symbol("_t")
            outer = sp.diff(FUNCTIONS[n.func](t), t)
            if kind == "trig_sign" and n.func in ("sin", "cos"):
                outer = -outer
            outer = outer.subs(t, to_sympy(n.args[0]))
            if kind == "chain_missing":
                return outer
            return outer * d(n.args[0])
        return sp.diff(to_sympy(n), x)

    return d(node)


def bug_sites(node, var):
    """Every (subtree, bug kind) where that mistake could plausibly be made."""
    x = sp.Symbol(var)
    for n in A.walk(node):
        try:
            s = to_sympy(n)
        except Exception:
            continue
        if x not in s.free_symbols:
            continue
        if isinstance(n, A.BinOp) and n.op == "*":
            if all(x in to_sympy(c).free_symbols for c in (n.left, n.right)):
                yield n, "product_naive"
        elif isinstance(n, A.BinOp) and n.op == "/" and x in to_sympy(n.right).free_symbols:
            yield n, "quotient_naive"
            yield n, "quotient_sign"
            yield n, "quotient_order"
        elif isinstance(n, A.BinOp) and n.op == "^":
            base, exp = to_sympy(n.left), to_sympy(n.right)
            if x not in exp.free_symbols:
                yield n, "power_no_reduce"
                yield n, "power_no_coeff"
                if not isinstance(n.left, A.Var):
                    yield n, "chain_missing"
            elif x not in base.free_symbols:
                yield n, "exp_as_power"
                if not isinstance(n.right, A.Var):
                    yield n, "chain_missing"
        elif isinstance(n, A.Call) and len(n.args) == 1:
            if not isinstance(n.args[0], A.Var):
                yield n, "chain_missing"
            if n.func in ("sin", "cos"):
                yield n, "trig_sign"


def diagnose_derivative(f_node, var, claimed):
    """Which single calculus mistake turns f′ into ``claimed``? Returns Diagnosis or None."""
    correct = sp.simplify(differentiate(f_node, var))
    if same_value(correct, claimed):
        return None
    for site, kind in bug_sites(f_node, var):
        try:
            wrong = differentiate(f_node, var, bug=(site, kind))
        except Exception:
            continue
        if same_value(wrong, correct):
            continue                       # this "mistake" happens to give the right answer here
        if same_value(wrong, claimed):
            category, title, why = BUGS[kind]
            where = f" (in {A.to_text(site)})" if site is not f_node else ""
            shown = min((sp.expand(correct), correct), key=lambda e: len(fmt(e)))   # expanded wins ties
            return Diagnosis(f"calculus.{kind}", category, title, why + where,
                             f"d/d{var}({A.to_text(f_node)}) = {fmt(shown)}")
    return None


@register
class DerivativeMistake(MalRule):
    id = "calculus.derivative"
    category = "Calculus"
    applies_to = ("expr",)

    def detect(self, prev, cur):
        if cur.kind != "expr":
            return None
        if isinstance(prev.node, A.Deriv):
            return diagnose_derivative(prev.node.operand, prev.node.var, cur.value)
        if prev.label.startswith("d/d") and len(prev.label) == 4:    # set by the checker for [d/dx] steps
            return diagnose_derivative(prev.node, prev.label[3], cur.value)
        return None
