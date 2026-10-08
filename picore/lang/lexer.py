"""Lexer: raw text -> list of Tokens (with source positions).

The lexer also resolves *identifiers*, because in maths notation letters run
together: ``sinx`` is ``sin x`` and ``xy`` is ``x y``. The rules are:

  1. exact function name (``sin``, ``log10``)           -> FUNC
  2. exact constant (``pi``, ``e``, ``i``, ``inf``)      -> CONST
  3. exact Greek letter name (``theta``) or one letter   -> VAR
  4. function name + one variable (``sinx``, ``cost``)  -> FUNC VAR
  5. two letters (``xy``)                               -> VAR VAR
  6. anything else (``what``)                           -> error: probably a word question

See docs/GRAMMAR.md for the full token list.
"""
import re
from dataclasses import dataclass

from .errors import ParseError

MAX_LEN = 300

FUNCTION_NAMES = {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh",
    "exp", "ln", "log", "log10", "log2",
    "sqrt", "cbrt", "abs", "floor", "ceil", "ceiling", "factorial",
}
CONSTANT_NAMES = {"pi": "pi", "e": "e", "i": "i", "oo": "oo", "inf": "oo", "infinity": "oo"}
GREEK_NAMES = {
    "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda",
    "mu", "sigma", "phi", "omega", "tau", "rho",
}
_FUNC_SUFFIX_VARS = {"x", "y", "z", "t", "u", "v", "w", "n", "theta"}

# Unicode symbols mapped to their ASCII spelling before lexing.
UNICODE = {
    "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-",
    "π": "pi", "∞": "oo", "θ": "theta", "α": "alpha", "β": "beta", "λ": "lambda",
    "μ": "mu", "σ": "sigma", "φ": "phi", "ω": "omega",
}
SUPERSCRIPTS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
                "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}


@dataclass(frozen=True)
class Token:
    kind: str      # NUM VAR CONST FUNC OP LPAREN RPAREN COMMA BANG EQ PM SQRT DERIV EOF
    value: str
    pos: int       # index in the original text
    end: int = 0   # index just past the token

    def __repr__(self):
        return f"{self.kind}({self.value!r}@{self.pos})"


_NUMBER = re.compile(r"\d+(?:\.\d*)?(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?")
_NAME = re.compile(r"log10|log2|[A-Za-z]+")
_DERIV = re.compile(r"d/d([A-Za-z])(?![A-Za-z])")
_SINGLE = {"+": "OP", "-": "OP", "*": "OP", "/": "OP", "^": "OP",
           "(": "LPAREN", ")": "RPAREN", ",": "COMMA", "!": "BANG", "=": "EQ",
           "±": "PM", "√": "SQRT"}


def _name_tokens(name, pos):
    """Resolve one run of letters into FUNC / CONST / VAR tokens (rules in module docstring)."""
    low = name.lower()
    end = pos + len(name)
    if low in FUNCTION_NAMES:
        return [Token("FUNC", low, pos, end)]
    if low in CONSTANT_NAMES:
        return [Token("CONST", CONSTANT_NAMES[low], pos, end)]
    if low in GREEK_NAMES:
        return [Token("VAR", low, pos, end)]
    if len(name) == 1:
        return [Token("VAR", name, pos, end)]
    for f in sorted(FUNCTION_NAMES, key=len, reverse=True):
        rest = low[len(f):]
        if low.startswith(f) and rest in _FUNC_SUFFIX_VARS:
            split = pos + len(f)
            return [Token("FUNC", f, pos, split), Token("VAR", name[len(f):], split, end)]
    if len(name) == 2:
        return _name_tokens(name[0], pos) + _name_tokens(name[1], pos + 1)
    raise ParseError(f"Unknown name '{name}'", pos)


def tokenize(text):
    """Turn ``text`` into tokens. Raises ParseError with the position of anything unknown."""
    if len(text) > MAX_LEN:
        raise ParseError("Expression too long")
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in SUPERSCRIPTS:                      # x² -> x ^ 2
            j = i
            while j < len(text) and text[j] in SUPERSCRIPTS:
                j += 1
            digits = "".join(SUPERSCRIPTS[c] for c in text[i:j])
            tokens += [Token("OP", "^", i, i), Token("NUM", digits, i, j)]
            i = j
            continue
        if ch in UNICODE:
            mapped = UNICODE[ch]
            if mapped in _SINGLE:
                tokens.append(Token(_SINGLE[mapped], mapped, i, i + 1))
            else:
                tokens += [Token(t.kind, t.value, i, i + 1) for t in _name_tokens(mapped, i)]
            i += 1
            continue
        if text.startswith("+/-", i):
            tokens.append(Token("PM", "±", i, i + 3))
            i += 3
            continue
        if text.startswith("**", i):
            tokens.append(Token("OP", "^", i, i + 2))
            i += 2
            continue
        m = _DERIV.match(text, i)
        if m:
            tokens.append(Token("DERIV", m.group(1), i, m.end()))
            i = m.end()
            continue
        m = _NUMBER.match(text, i)
        if m:
            tokens.append(Token("NUM", m.group(), i, m.end()))
            i = m.end()
            continue
        m = _NAME.match(text, i)
        if m:
            tokens += _name_tokens(m.group(), i)
            i = m.end()
            continue
        if ch in _SINGLE:
            tokens.append(Token(_SINGLE[ch], ch, i, i + 1))
            i += 1
            continue
        raise ParseError(f"Unexpected character '{ch}'", i)
    tokens.append(Token("EOF", "", len(text), len(text)))
    return tokens
