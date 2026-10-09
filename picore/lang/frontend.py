"""Text-level parsing API used by every layer (built on the lexer/parser/AST).

Thin layer over ``picore.lang`` (lexer -> recursive-descent parser -> AST ->
SymPy). Nothing here uses ``eval``: only the grammar in docs/GRAMMAR.md is
accepted, and runaway numbers (e.g. 9^9^9) are rejected before SymPy builds them.
"""
from . import ast as A
from .errors import ParseError
from .lexer import MAX_LEN  # noqa: F401  (re-exported for callers)
from .parser import parse
from .sympy_backend import to_sympy

UNICODE = {
    "π": "pi", "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-",
    "√": "sqrt", "²": "^2", "³": "^3", "∞": "oo", "θ": "theta",
}


def normalize_text(text):
    """ASCII-fy common math symbols so command patterns ('d/dx', 'from .. to ..') match."""
    for k, v in UNICODE.items():
        text = text.replace(k, v)
    return text.strip()


def parse_ast(text):
    """Parse text into an AST (expression or equation)."""
    return parse(text)


def parse_expr(text):
    """Parse one expression (no '=') into a SymPy expression."""
    node = parse(text)
    if isinstance(node, A.Equation):
        raise ParseError("Expected an expression, not an equation", node.rhs.span[0])
    return to_sympy(node)


def parse_relation(text):
    """Parse 'lhs = rhs' into ``Eq``, or a bare expression."""
    return to_sympy(parse(text))


def split_top_level(text, seps):
    """Split on any separator in ``seps`` that is outside parentheses."""
    parts, depth, cur, i = [], 0, "", 0
    while i < len(text):
        ch = text[i]
        depth += ch == "("
        depth -= ch == ")"
        hit = next((s for s in seps if depth == 0 and text.startswith(s, i)), None)
        if hit:
            parts.append(cur)
            cur = ""
            i += len(hit)
            continue
        cur += ch
        i += 1
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def parse_system(text):
    """'x+y=3 and x-y=1' / 'x+y=3, x-y=1' -> list of relations."""
    return [parse_relation(p) for p in split_top_level(normalize_text(text), [" and ", ";", ","])]
