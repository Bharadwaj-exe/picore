"""Safe math-expression parser.

User text is tokenized, implicit multiplication is made explicit, and the
result is parsed with ``ast`` and converted node-by-node into SymPy objects.
Nothing is ever passed to ``eval``; only whitelisted names and operators are
accepted, and runaway numbers (e.g. 9^9^9) are rejected before SymPy tries to
build them.
"""
import ast
import re

import sympy as sp

MAX_LEN = 300
MAX_EXPONENT = 5000
MAX_INT_DIGITS = 100


class ParseError(ValueError):
    """Input is not a math expression we understand."""


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

CONSTANTS = {
    "pi": sp.pi, "e": sp.E, "i": sp.I,
    "oo": sp.oo, "inf": sp.oo, "infinity": sp.oo,
}

GREEK = {
    "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda",
    "mu", "sigma", "phi", "omega", "tau", "rho",
}

UNICODE = {
    "π": "pi", "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-",
    "√": "sqrt", "²": "^2", "³": "^3", "∞": "oo", "θ": "theta",
}

_FUNC_SUFFIX_VARS = {"x", "y", "z", "t", "u", "v", "w", "n", "theta"}

_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d*)?[eE][-+]?\d+|\d+\.\d*|\.\d+|\d+)|(log10|log2|[A-Za-z_]+)|(\*\*|[-+*/^(),!]))")


def _tokenize(text):
    tokens, pos = [], 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ParseError(f"Unexpected character '{text[pos].strip() or text[pos]}'")
        num, name, op = m.groups()
        if num:
            tokens.append(("num", num))
        elif name:
            tokens.extend(_split_name(name))
        else:
            tokens.append(("op", "**" if op == "^" else op))
        pos = m.end()
    return tokens


def _split_name(name):
    """'sinx' -> sin x, 'xy' -> x y, '2' already handled; known names kept."""
    low = name.lower()
    if low in FUNCTIONS:
        return [("func", low)]
    if low in CONSTANTS or low in GREEK or len(name) == 1:
        return [("name", name if len(name) == 1 else low)]
    for f in sorted(FUNCTIONS, key=len, reverse=True):
        if low.startswith(f) and low[len(f):] in _FUNC_SUFFIX_VARS:
            return [("func", f), ("name", name[len(f):])]
    # "xy" -> x*y; longer unknown words are treated as natural language
    if name.isalpha() and len(name) == 2:
        return [("name", ch) for ch in name]
    raise ParseError(f"Unknown name '{name}'")


def _implicit(tokens):
    """Insert '*' for juxtaposition and wrap 'sin x' as 'sin(x)'."""
    out = []
    i = 0
    while i < len(tokens):
        kind, val = tokens[i]
        if out:
            pk, pv = out[-1]
            prev_ends_value = pk in ("num", "name") or pv in (")", "!")
            starts_value = kind in ("num", "name", "func") or val == "("
            if prev_ends_value and starts_value:
                out.append(("op", "*"))
        if kind == "func" and i + 1 < len(tokens) and tokens[i + 1][1] != "(":
            nxt = tokens[i + 1]
            if nxt[0] not in ("num", "name"):
                raise ParseError(f"'{val}' needs an argument")
            out += [("func", val), ("op", "("), nxt, ("op", ")")]
            i += 2
            continue
        out.append((kind, val))
        i += 1
    return out


def _to_source(tokens):
    parts = []
    for kind, val in tokens:
        if val == "!":
            parts.append(" !")  # handled below
        else:
            parts.append(f" {val} ")
    src = "".join(parts)
    # postfix factorial: "5 !" or "( ... ) !" -> factorial(...)
    while "!" in src:
        idx = src.index("!")
        left = src[:idx].rstrip()
        if left.endswith(")"):
            depth, j = 0, len(left) - 1
            while j >= 0:
                depth += left[j] == ")"
                depth -= left[j] == "("
                if depth == 0:
                    break
                j -= 1
            start = j
        else:
            m = re.search(r"[\w.]+$", left)
            if not m:
                raise ParseError("Misplaced '!'")
            start = m.start()
        src = f"{left[:start]} factorial({left[start:]}) {src[idx + 1:]}"
    return src


def _convert(node):
    if isinstance(node, ast.Expression):
        return _convert(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        text = repr(node.value)
        if isinstance(node.value, int) and len(text) > MAX_INT_DIGITS:
            raise ParseError("Number too large")
        return sp.Integer(node.value) if isinstance(node.value, int) else sp.Rational(text)
    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        if len(node.id) == 1 or node.id in GREEK:
            return sp.Symbol(node.id)
        raise ParseError(f"Unknown name '{node.id}'")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        val = _convert(node.operand)
        return -val if isinstance(node.op, ast.USub) else val
    if isinstance(node, ast.BinOp):
        a, b = _convert(node.left), _convert(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return a + b
        if isinstance(op, ast.Sub):
            return a - b
        if isinstance(op, ast.Mult):
            return a * b
        if isinstance(op, ast.Div):
            return a / b
        if isinstance(op, ast.Pow):
            if b.is_Number and abs(b) > MAX_EXPONENT and a.is_Number and abs(a) not in (0, 1):
                raise ParseError("Number too large")
            return a ** b
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        fn = FUNCTIONS.get(node.func.id)
        if fn is None:
            raise ParseError(f"Unknown function '{node.func.id}'")
        args = [_convert(a) for a in node.args]
        if node.func.id == "factorial" and args and args[0].is_Number and args[0] > 1000:
            raise ParseError("Number too large")
        try:
            return fn(*args)
        except TypeError:
            raise ParseError(f"Wrong number of arguments for {node.func.id}") from None
    raise ParseError("Unsupported syntax")


def normalize_text(text):
    for k, v in UNICODE.items():
        text = text.replace(k, v)
    return text.strip()


def parse_expr(text):
    """Parse one expression (no '=') into a SymPy expression."""
    text = normalize_text(text)
    if not text:
        raise ParseError("Empty expression")
    if len(text) > MAX_LEN:
        raise ParseError("Expression too long")
    src = _to_source(_implicit(_tokenize(text)))
    try:
        tree = ast.parse(src.strip(), mode="eval")
    except SyntaxError:
        raise ParseError("Couldn't read that expression") from None
    return _convert(tree)


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


def parse_relation(text):
    """Parse 'lhs = rhs' into Eq, or a bare expression."""
    sides = text.split("=")
    if len(sides) == 1:
        return parse_expr(text)
    if len(sides) != 2:
        raise ParseError("Use a single '=' per equation")
    return sp.Eq(parse_expr(sides[0]), parse_expr(sides[1]), evaluate=False)


def parse_system(text):
    """'x+y=3 and x-y=1' / 'x+y=3, x-y=1' -> list of relations."""
    return [parse_relation(p) for p in split_top_level(normalize_text(text), [" and ", ";", ","])]
