"""Parser properties, adversarial input, and resource bounds."""
import os
import random
import time

import pytest

from picore.engine import evaluate
from picore.lang import ParseError, parse
from picore.lang import ast as A

# ---- property: printing and parsing are inverse, spans nest ------------------------------

LEAVES = [lambda r: A.Num(str(r.randint(0, 99))), lambda r: A.Var(r.choice("xyzt")),
          lambda r: A.Const(r.choice(["pi", "e"]))]
FUNCS = ["sin", "cos", "ln", "sqrt", "exp", "abs"]


def random_tree(r, depth):
    if depth == 0 or r.random() < 0.25:
        return r.choice(LEAVES)(r)
    kind = r.random()
    if kind < 0.55:
        return A.BinOp(r.choice("+-*/^"), random_tree(r, depth - 1), random_tree(r, depth - 1))
    if kind < 0.7:
        return A.Neg(random_tree(r, depth - 1))
    if kind < 0.85:
        return A.Call(r.choice(FUNCS), (random_tree(r, depth - 1),))
    if kind < 0.92:
        return A.Factorial(random_tree(r, 0))
    return A.Deriv("x", random_tree(r, depth - 1))


def test_print_parse_round_trip_on_random_trees():
    r = random.Random(2026)
    checked = 0
    for _ in range(1500):
        tree = random_tree(r, 4)
        text = A.to_text(tree)
        if len(text) > 300:
            continue
        assert parse(text) == tree, text
        checked += 1
    assert checked > 1000


def test_spans_are_inside_the_text_and_nested():
    r = random.Random(7)
    for _ in range(400):
        text = A.to_text(random_tree(r, 4))
        if len(text) > 300:
            continue
        root = parse(text)

        def check(node, outer):
            a, b = node.span
            assert outer[0] <= a <= b <= outer[1], (text, node)
            for c in A.children(node):
                check(c, node.span)
        check(root, (0, len(text)))


# ---- adversarial / pathological input --------------------------------------------------

PATHOLOGICAL = [
    "2^(2^20)", "10^10^10", "(10^100)!", "9^(9^9)", "x^(2^30)", "(x+1)^5000", "x^5000 = 1",
    "expand (x+1)^5000", "(" * 120 + "x" + ")" * 120, "-" * 250 + "x", "√" * 80 + "x",
    "sin(" * 70 + "x" + ")" * 70, "1" * 101, "x" * 400, "check " + " -> ".join(["x"] * 30),
    "\x00\x01\x02", "🙂", "ｘ＋１", "1e400", "1e-400", "2e3e", "((((", "))))", "= =", "x =", "± ±",
]


@pytest.mark.parametrize("text", PATHOLOGICAL)
def test_pathological_input_is_bounded(text):
    start = time.monotonic()
    r = evaluate(text)                       # must return, not raise
    assert time.monotonic() - start < 10, text
    assert r.pods


def test_huge_inputs_are_rejected_cheaply():
    r = evaluate("x+" * 5000 + "1")
    assert r.source == "error" and "too long" in r.pods[0][0].lower()


@pytest.mark.parametrize("payload", [
    "__import__('os').system('echo pwned')", "open('picore_pwned.txt','w').write('x')",
    "exec('print(1)')", "eval('1+1')", "x.__class__.__mro__", "().__class__", "lambda: 0",
    "globals()", "import os", "${PATH}", "$(touch picore_pwned.txt)", "`touch picore_pwned.txt`",
])
def test_code_never_runs(payload, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = evaluate(payload)
    assert not (tmp_path / "picore_pwned.txt").exists()
    assert r.source == "error"


def test_parse_errors_point_at_the_problem():
    with pytest.raises(ParseError) as info:
        parse("2 + (3 * x")
    assert info.value.pos is not None and "Missing ')'" in str(info.value)


def test_unicode_math_is_understood():
    assert parse("x² + 2·x − 1") == parse("x^2 + 2*x - 1")
    assert parse("π × r²") == parse("pi * r^2")
