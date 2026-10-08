import random
import time

import pytest
import sympy as sp

from picore.lang import ParseError, parse, tokenize
from picore.lang import ast as A
from picore.lang.sympy_backend import domain_conditions, excluded_points, to_sympy

x, y = sp.symbols("x y")


def val(text):
    return to_sympy(parse(text))


# ---- lexer ---------------------------------------------------------------------

def kinds(text):
    return [(t.kind, t.value) for t in tokenize(text)][:-1]


def test_lexer_identifier_rules():
    assert kinds("sinx") == [("FUNC", "sin"), ("VAR", "x")]
    assert kinds("xy") == [("VAR", "x"), ("VAR", "y")]
    assert kinds("pi e i") == [("CONST", "pi"), ("CONST", "e"), ("CONST", "i")]
    assert kinds("theta") == [("VAR", "theta")]
    assert kinds("log10(x)")[0] == ("FUNC", "log10")


def test_lexer_unicode_and_superscripts():
    assert kinds("x²") == [("VAR", "x"), ("OP", "^"), ("NUM", "2")]
    assert kinds("2×π") == [("NUM", "2"), ("OP", "*"), ("CONST", "pi")]
    assert kinds("√x") == [("SQRT", "√"), ("VAR", "x")]
    assert kinds("5 ± 2") == [("NUM", "5"), ("PM", "±"), ("NUM", "2")]
    assert kinds("5 +/- 2") == [("NUM", "5"), ("PM", "±"), ("NUM", "2")]
    assert kinds("d/dx x") == [("DERIV", "x"), ("VAR", "x")]


def test_lexer_numbers():
    assert kinds("1e5 2.5 .5 2e") == [("NUM", "1e5"), ("NUM", "2.5"), ("NUM", ".5"), ("NUM", "2"), ("CONST", "e")]


def test_lexer_positions():
    toks = tokenize("12 + sin x")
    assert [(t.pos, t.end) for t in toks[:-1]] == [(0, 2), (3, 4), (5, 8), (9, 10)]


# ---- precedence & associativity conventions (see parser docstring) -------------

@pytest.mark.parametrize("text, expected", [
    ("-2^2", -4),
    ("2^3^2", 512),
    ("1/2x", x / 2),
    ("2x^2", 2 * x ** 2),
    ("x^2y", x ** 2 * y),
    ("sin x^2", sp.sin(x ** 2)),
    ("sin^2 x", sp.sin(x) ** 2),
    ("sin²(x)", sp.sin(x) ** 2),
    ("2sin x cos x", 2 * sp.sin(x) * sp.cos(x)),
    ("√x^2", sp.sqrt(x ** 2)),
    ("√2x", sp.sqrt(2) * x),
    ("2^-1", sp.Rational(1, 2)),
    ("(-2)^2", 4),
    ("3(2+1)!", 18),
    ("x(x+1)", x * (x + 1)),
    ("d/dx x^3", 3 * x ** 2),
    ("d/dx x^2 + 1", 2 * x + 1),
    ("e^(i pi)", -1),
    ("10 - 4 - 3", 3),
    ("12 / 3 / 2", 2),
])
def test_conventions(text, expected):
    assert sp.simplify(val(text) - expected) == 0


def test_ast_shape_matches_docs_example():
    tree = parse("2x² + 3x + 1")
    assert tree == A.BinOp("+",
                           A.BinOp("+",
                                   A.BinOp("*", A.Num("2"), A.BinOp("^", A.Var("x"), A.Num("2"))),
                                   A.BinOp("*", A.Num("3"), A.Var("x"))),
                           A.Num("1"))
    assert tree.left.left.implicit


def test_spans_point_into_source():
    text = "2sin(x)^2 + 3x"
    tree = parse(text)
    pow_node = tree.left.right
    assert isinstance(pow_node, A.BinOp) and pow_node.op == "^"
    assert text[slice(*pow_node.span)] == "sin(x)^2"
    assert text[slice(*tree.right.span)] == "3x"
    assert text[slice(*tree.span)] == text


def test_parenthesized_span_includes_parens():
    text = "2(x+1)"
    assert text[slice(*parse(text).right.span)] == "(x+1)"


def test_equation_and_plus_minus():
    eq = parse("x = 5 ± √6")
    assert isinstance(eq, A.Equation) and isinstance(eq.rhs, A.PlusMinus)
    left, right = A.branches(eq)
    assert to_sympy(left).rhs == 5 + sp.sqrt(6) and to_sympy(right).rhs == 5 - sp.sqrt(6)
    neg = parse("x = ±3")
    assert sorted(to_sympy(b).rhs for b in A.branches(neg)) == [-3, 3]
    quad = parse("x = (5 ± √(25 - 24)) / 2")
    assert sorted(to_sympy(b).rhs for b in A.branches(quad)) == [2, 3]
    with pytest.raises(ParseError):
        to_sympy(eq)   # ± must be expanded first


@pytest.mark.parametrize("text", ["2x² + 3x + 1", "-(x+1)^2", "(x^2)^3", "2^(3^2)", "a - (b - c)",
                                  "a / (b * c)", "sin(x)^2 + cos(x)^2", "(x+1)!", "x = 2 ± √3", "-2^2"])
def test_to_text_round_trips(text):
    tree = parse(text)
    assert parse(A.to_text(tree)) == tree


# ---- errors ------------------------------------------------------------------

@pytest.mark.parametrize("text, pos", [
    ("2 + * 3", 4), ("(x + 1", 6), ("x + 1)", 5), ("sin()", 4), ("x @ 2", 2), ("what is x", 0),
    ("2 +", 2), ("x = = 2", 4), ("()", 1),
])
def test_errors_have_positions(text, pos):
    with pytest.raises(ParseError) as info:
        parse(text)
    assert info.value.pos == pos


def test_deep_nesting_is_rejected_not_crashing():
    with pytest.raises(ParseError, match="nested too deeply"):
        parse("(" * 120 + "x" + ")" * 120)
    with pytest.raises(ParseError):
        parse("-" * 250 + "x")


def test_fuzz_only_parse_errors_and_fast():
    alphabet = list("x y 2 3 + - * / ^ ( ) ! = . , ± √ ² sin cos pi e d/dx".split(" ")) + [" "]
    rng = random.Random(1234)
    start = time.monotonic()
    for _ in range(3000):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 25)))
        try:
            tree = parse(text)
            for b in A.branches(tree):
                to_sympy(b)
        except (ParseError, ValueError):
            pass
    assert time.monotonic() - start < 30


# ---- domain analysis ---------------------------------------------------------

def test_domain_of_rational_expression():
    conds = domain_conditions(parse("(x^2 - 1)/(x - 1)"))
    assert [(c.expr, c.kind) for c in conds] == [(x - 1, "nonzero")]
    assert excluded_points(conds, x) == {1}


def test_domain_survives_sympy_simplification():
    # SymPy turns x/x into 1, but the AST still knows x must be non-zero
    assert sp.simplify(val("x/x")) == 1
    assert excluded_points(domain_conditions(parse("x/x")), x) == {0}


def test_domain_log_and_sqrt():
    kinds_ = {c.kind for c in domain_conditions(parse("ln(x) + √(x - 2)"))}
    assert kinds_ == {"positive", "nonnegative"}
