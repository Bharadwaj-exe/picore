"""Abstract syntax tree for Pi Core's math language.

Nodes are immutable. Every node remembers ``span``, the (start, end) slice of
the original text it came from, so the UI can highlight it and errors can
point at it. Spans are ignored when comparing nodes, so two trees are equal
when their *mathematical structure* is equal.

Example: ``2x² + 3x + 1`` parses to

    BinOp('+')
    ├── BinOp('+')
    │   ├── BinOp('*', implicit)
    │   │   ├── Num('2')
    │   │   └── BinOp('^')
    │   │       ├── Var('x')
    │   │       └── Num('2')
    │   └── BinOp('*', implicit)
    │       ├── Num('3')
    │       └── Var('x')
    └── Num('1')
"""
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Node:
    span: tuple = field(default=(0, 0), compare=False, repr=False, kw_only=True)


@dataclass(frozen=True)
class Num(Node):
    value: str            # exact decimal text, e.g. "2", "0.1", "1e5"


@dataclass(frozen=True)
class Const(Node):
    name: str             # "pi" | "e" | "i" | "oo"


@dataclass(frozen=True)
class Var(Node):
    name: str


@dataclass(frozen=True)
class Neg(Node):
    operand: Node


@dataclass(frozen=True)
class BinOp(Node):
    op: str               # "+" "-" "*" "/" "^"
    left: Node
    right: Node
    implicit: bool = field(default=False, compare=False)   # 2x rather than 2*x


@dataclass(frozen=True)
class PlusMinus(Node):
    """``a ± b``: stands for two expressions. Only meaningful in answers like x = 2 ± √3."""
    left: Node
    right: Node


@dataclass(frozen=True)
class Call(Node):
    func: str
    args: tuple


@dataclass(frozen=True)
class Factorial(Node):
    operand: Node


@dataclass(frozen=True)
class Deriv(Node):
    """``d/dx f``"""
    var: str
    operand: Node


@dataclass(frozen=True)
class Equation(Node):
    lhs: Node
    rhs: Node


# ---- traversal ---------------------------------------------------------------

def children(node):
    if isinstance(node, (Neg, Factorial, Deriv)):
        return (node.operand,)
    if isinstance(node, (BinOp, PlusMinus)):
        return (node.left, node.right)
    if isinstance(node, Call):
        return tuple(node.args)
    if isinstance(node, Equation):
        return (node.lhs, node.rhs)
    return ()


def walk(node):
    """Pre-order traversal: the node, then each subtree left to right."""
    yield node
    for c in children(node):
        yield from walk(c)


def with_children(node, new):
    """Copy of ``node`` with its children replaced (same order as children())."""
    if isinstance(node, (Neg, Factorial, Deriv)):
        return replace(node, operand=new[0])
    if isinstance(node, (BinOp, PlusMinus)):
        return replace(node, left=new[0], right=new[1])
    if isinstance(node, Call):
        return replace(node, args=tuple(new))
    if isinstance(node, Equation):
        return replace(node, lhs=new[0], rhs=new[1])
    return node


def contains(node, kind):
    return any(isinstance(n, kind) for n in walk(node))


def branches(node, limit=8):
    """Expand every ``a ± b`` into the two trees ``a + b`` and ``a - b``.

    ``x = (5 ± √(25 - 24)) / 2`` gives two equations. Raises ValueError past ``limit``.
    """
    results = [node]
    while any(contains(n, PlusMinus) for n in results):
        nxt = []
        for n in results:
            nxt += _split_first(n)
        results = nxt
        if len(results) > limit:
            raise ValueError("Too many ± signs")
    return results


def _split_first(node):
    if isinstance(node, PlusMinus):
        return [BinOp("+", node.left, node.right, span=node.span),
                BinOp("-", node.left, node.right, span=node.span)]
    kids = children(node)
    for idx, c in enumerate(kids):
        if contains(c, PlusMinus):
            return [with_children(node, kids[:idx] + (alt,) + kids[idx + 1:]) for alt in _split_first(c)]
    return [node]


# ---- precedence & printing ---------------------------------------------------

PRECEDENCE = {"=": 0, "+": 1, "-": 1, "±": 1, "*": 2, "/": 2, "neg": 3, "^": 4, "!": 5, "atom": 6}
PRECEDENCE_NAMES = {0: "equation", 1: "addition / subtraction", 2: "multiplication / division",
                    3: "prefix operator (negation, d/dx)", 4: "power (right-associative)", 5: "factorial", 6: "atom"}


def precedence(node):
    if isinstance(node, Equation):
        return 0
    if isinstance(node, PlusMinus):
        return 1
    if isinstance(node, BinOp):
        return PRECEDENCE[node.op]
    if isinstance(node, (Neg, Deriv)):     # d/dx is a prefix operator: d/dx(f)^2 would mean d/dx(f^2)
        return 3
    if isinstance(node, Factorial):
        return 5
    return 6


def label(node):
    """Short label for a tree diagram."""
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Const):
        return {"pi": "π", "oo": "∞"}.get(node.name, node.name)
    if isinstance(node, Var):
        return node.name
    if isinstance(node, Neg):
        return "−"
    if isinstance(node, BinOp):
        return {"*": "×", "/": "÷", "-": "−"}.get(node.op, node.op)
    if isinstance(node, PlusMinus):
        return "±"
    if isinstance(node, Call):
        return node.func
    if isinstance(node, Factorial):
        return "!"
    if isinstance(node, Deriv):
        return f"d/d{node.var}"
    if isinstance(node, Equation):
        return "="
    return "?"


def kind(node):
    """Human name of the node type, e.g. 'power', 'function call'."""
    if isinstance(node, BinOp):
        return {"+": "addition", "-": "subtraction", "*": "multiplication",
                "/": "division", "^": "power"}[node.op]
    return {Num: "number", Const: "constant", Var: "variable", Neg: "negation",
            PlusMinus: "plus-or-minus", Call: "function call", Factorial: "factorial",
            Deriv: "derivative", Equation: "equation"}[type(node)]


def to_text(node):
    """Print the tree back as math text, with only the parentheses that are needed."""
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Const):
        return {"pi": "π", "oo": "∞"}.get(node.name, node.name)
    if isinstance(node, Var):
        return node.name
    if isinstance(node, Equation):
        return f"{to_text(node.lhs)} = {to_text(node.rhs)}"
    if isinstance(node, Call):
        return f"{node.func}({', '.join(to_text(a) for a in node.args)})"
    if isinstance(node, Deriv):
        return f"d/d{node.var}({to_text(node.operand)})"
    if isinstance(node, Neg):
        return "-" + _wrap(node.operand, precedence(node.operand) <= 3 and not _is_atomic(node.operand))
    if isinstance(node, Factorial):
        return _wrap(node.operand, precedence(node.operand) < 6) + "!"
    if isinstance(node, PlusMinus):
        return f"{to_text(node.left)} ± {_wrap(node.right, precedence(node.right) <= 1)}"
    if isinstance(node, BinOp):
        p = PRECEDENCE[node.op]
        if node.op == "^":     # right-associative: parenthesize a power on the left
            left = _wrap(node.left, precedence(node.left) <= p)
            right = _wrap(node.right, precedence(node.right) < p)
            return f"{left}^{right}"
        left = _wrap(node.left, precedence(node.left) < p)
        # left-associative: an equal-precedence operator on the RIGHT needs parentheses (a·(b/c), a − (b − c))
        right = _wrap(node.right, precedence(node.right) <= p)
        if node.op == "*":
            if isinstance(node.left, Num) and not isinstance(node.right, Num) and not right.startswith("-"):
                return f"{left}{right}"          # 2x, 3(x+1), 2sin(x)
            return f"{left}·{right}"
        return f"{left} {node.op} {right}"
    return "?"


def _is_atomic(node):
    return isinstance(node, (Num, Const, Var, Call))


def _wrap(node, needed):
    text = to_text(node)
    return f"({text})" if needed else text
