"""AST -> SymPy conversion, with guards against runaway computation.

Also home of *domain analysis*: the conditions under which an expression is
defined (denominators ≠ 0, log arguments > 0, ...). That has to be read from the
AST, because SymPy simplifies on construction (``x/x`` becomes ``1`` and the
fact that it is undefined at x = 0 is lost).
"""
from dataclasses import dataclass

import sympy as sp

from . import ast as A
from .errors import ParseError

MAX_EXPONENT = 5000
MAX_SYMBOLIC_EXPONENT = 200   # x^n with symbolic x: beyond this, expansion/solving explodes in size
MAX_INT_DIGITS = 100
MAX_FACTORIAL = 1000

CONSTANTS = {"pi": sp.pi, "e": sp.E, "i": sp.I, "oo": sp.oo}

FUNCTIONS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "exp": sp.exp, "ln": sp.log, "log": sp.log,
    "log10": lambda x: sp.log(x, 10), "log2": lambda x: sp.log(x, 2),
    "sqrt": sp.sqrt, "cbrt": lambda x: sp.root(x, 3),
    "abs": sp.Abs, "floor": sp.floor, "ceil": sp.ceiling, "ceiling": sp.ceiling,
    "factorial": sp.factorial,
}


def to_sympy(node):
    """Convert an AST into a SymPy expression (or ``Eq`` for an equation)."""
    if isinstance(node, A.Num):
        digits = node.value.split(".")[0].split("e")[0].split("E")[0]
        if len(digits) > MAX_INT_DIGITS:
            raise ParseError("Number too large", node.span[0])
        if node.value.isdigit():
            return sp.Integer(node.value)
        try:
            return sp.Rational(node.value)
        except (ValueError, TypeError):
            raise ParseError(f"Bad number '{node.value}'", node.span[0]) from None
    if isinstance(node, A.Const):
        return CONSTANTS[node.name]
    if isinstance(node, A.Var):
        return sp.Symbol(node.name)
    if isinstance(node, A.Neg):
        return -to_sympy(node.operand)
    if isinstance(node, A.BinOp):
        a, b = to_sympy(node.left), to_sympy(node.right)
        if node.op == "+":
            return a + b
        if node.op == "-":
            return a - b
        if node.op == "*":
            return a * b
        if node.op == "/":
            return a / b
        if b.is_Number and abs(b) > MAX_EXPONENT and a.is_Number and abs(a) not in (0, 1):
            raise ParseError("Number too large", node.span[0])
        if b.is_Number and abs(b) > MAX_SYMBOLIC_EXPONENT and a.free_symbols:
            raise ParseError(f"Exponent too large for symbolic work (the limit is {MAX_SYMBOLIC_EXPONENT})", node.span[0])
        return a ** b
    if isinstance(node, A.Factorial):
        arg = to_sympy(node.operand)
        if arg.is_Number and arg > MAX_FACTORIAL:
            raise ParseError("Number too large", node.span[0])
        return sp.factorial(arg)
    if isinstance(node, A.Call):
        args = [to_sympy(a) for a in node.args]
        if node.func == "factorial" and args and args[0].is_Number and args[0] > MAX_FACTORIAL:
            raise ParseError("Number too large", node.span[0])
        try:
            return FUNCTIONS[node.func](*args)
        except TypeError:
            raise ParseError(f"Wrong number of arguments for {node.func}", node.span[0]) from None
    if isinstance(node, A.Deriv):
        return sp.diff(to_sympy(node.operand), sp.Symbol(node.var))
    if isinstance(node, A.Equation):
        return sp.Eq(to_sympy(node.lhs), to_sympy(node.rhs), evaluate=False)
    if isinstance(node, A.PlusMinus):
        raise ParseError("'±' can only be used in answers, like x = 2 ± √3", node.span[0])
    raise ParseError("Unsupported syntax")


def from_sympy(expr):
    """SymPy expression -> AST, by printing in Pi Core syntax and parsing it back."""
    import re
    from .parser import parse
    text = sp.sstr(expr).replace("**", "^")
    text = re.sub(r"\bI\b", "i", text)
    text = re.sub(r"\bE\b", "e", text)
    return parse(text)


# ---- domain analysis -----------------------------------------------------------

@dataclass(frozen=True)
class Condition:
    """One requirement for an expression to be defined (over the reals)."""
    expr: object        # SymPy expression the condition is about
    kind: str           # "nonzero" | "positive" | "nonnegative"
    reason: str         # e.g. "denominator of 1/(x - 1)"

    def as_relational(self):
        return {"nonzero": sp.Ne(self.expr, 0), "positive": self.expr > 0,
                "nonnegative": self.expr >= 0}[self.kind]

    def describe(self):
        sym = {"nonzero": "≠ 0", "positive": "> 0", "nonnegative": "≥ 0"}[self.kind]
        from .printing import fmt
        return f"{fmt(self.expr)} {sym}  ({self.reason})"


def domain_conditions(node):
    """All definedness conditions found in the AST (duplicates removed, constants skipped).

    A derivative d/dx f is defined where its RESULT is defined, not where f is
    (√x is defined at 0, its derivative 1/(2√x) is not), so for Deriv nodes the
    conditions are read from the computed derivative instead of the operand."""
    found = []

    def visit(n):
        try:
            if isinstance(n, A.Deriv):
                try:
                    found.extend(domain_conditions(from_sympy(to_sympy(n))))
                except Exception:          # result not expressible in Pi Core syntax: no conditions recorded
                    pass
                return
            if isinstance(n, A.BinOp) and n.op == "/":
                found.append(Condition(to_sympy(n.right), "nonzero", f"denominator in {A.to_text(n)}"))
            elif isinstance(n, A.BinOp) and n.op == "^":
                exp = to_sympy(n.right)
                if exp.is_number and exp.is_negative:
                    found.append(Condition(to_sympy(n.left), "nonzero", f"negative power in {A.to_text(n)}"))
            elif isinstance(n, A.Call) and n.func in ("log", "ln", "log10", "log2") and n.args:
                found.append(Condition(to_sympy(n.args[0]), "positive", f"logarithm argument in {A.to_text(n)}"))
            elif isinstance(n, A.Call) and n.func == "sqrt":
                found.append(Condition(to_sympy(n.args[0]), "nonnegative", f"square root in {A.to_text(n)}"))
            elif isinstance(n, A.Call) and n.func in ("tan", "sec"):
                found.append(Condition(sp.cos(to_sympy(n.args[0])), "nonzero", f"{n.func} is undefined where cos = 0"))
            elif isinstance(n, A.Call) and n.func in ("cot", "csc"):
                found.append(Condition(sp.sin(to_sympy(n.args[0])), "nonzero", f"{n.func} is undefined where sin = 0"))
        except ParseError:
            pass
        for c in A.children(n):
            visit(c)

    visit(node)
    unique, seen = [], set()
    for c in found:
        if c.expr.free_symbols and (c.expr, c.kind) not in seen:
            seen.add((c.expr, c.kind))
            unique.append(c)
    return unique


def holds(conditions, point):
    """True/False whether every condition holds at a numeric point; None if it can't be evaluated."""
    for c in conditions:
        try:
            v = complex(sp.N(c.expr.subs(point), 30))
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        if abs(v.imag) > 1e-12 * max(1.0, abs(v.real)):
            return False
        r = v.real
        ok = {"nonzero": abs(r) > 1e-9, "positive": r > 1e-12, "nonnegative": r >= -1e-12}[c.kind]
        if not ok:
            return False
    return True


def excluded_points(conditions, var):
    """Finite set of real points where a 'nonzero' condition fails (e.g. x = 1 for 1/(x-1))."""
    points = set()
    for c in conditions:
        if c.kind != "nonzero" or c.expr.free_symbols != {var}:
            continue
        try:
            sols = sp.solveset(c.expr, var, domain=sp.S.Reals)
        except (NotImplementedError, ValueError, TypeError):
            continue
        if isinstance(sols, sp.FiniteSet):
            points |= set(sols)
    return points
