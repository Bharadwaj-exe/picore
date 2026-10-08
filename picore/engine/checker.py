"""Mistake Detective: check a student's working step by step.

    check x^2 - 5x + 6 = 0 -> x^2 = 5x - 6 -> x = 5 ± √6
    check (x+1)^2 -> [expand] x^2 + 2x + 1 -> [d/dx] 2x + 2

Each step is judged against the one before it:
  * plain steps must be equivalent (expressions: equivalence engine, with domains;
    equations: same solution set)
  * labelled steps ``[rule]`` must be what that rule produces (see reasoning.derivation)
When a step is wrong, the mal-rule catalogue (reasoning.mistakes) tries to name the exact
misconception; if none reproduces the step, the evidence is shown without guessing why.
"""
import re
from dataclasses import dataclass

import sympy as sp

from ..lang import ast as A
from ..lang.sympy_backend import to_sympy
from ..reasoning import derivation
from ..reasoning.equivalence import CONDITIONAL, EXACT, NOT, NUMERIC, compare, solution_set
from ..reasoning.mistakes import Step, run_rules
from ..reasoning.mistakes.core import proportional
from ..reasoning.mistakes.equations import show_solutions, single_var
from .parser import ParseError, parse_ast, split_top_level

SEPARATORS = ["->", "=>", "→", ";", "\n"]
OK, BAD, WARN, UNSURE = "correct", "mistake here", "check needed", "couldn't check"


def split_steps(text):
    """'check a -> [rule] b -> c' -> [('', 'a'), ('rule', 'b'), ('', 'c')]"""
    text = re.sub(r"^\s*check\s+", "", text, flags=re.I)
    raw = split_top_level(text, SEPARATORS)
    if len(raw) < 2:
        raise ParseError("Give at least two steps, e.g.  check 2x+6=10 -> 2x=4 -> x=2")
    steps = []
    for r in raw:
        m = re.match(r"^\[([^\]]+)\]\s*(.*)$", r)
        steps.append((m.group(1).strip(), m.group(2).strip()) if m else ("", r))
    return steps


def parse_step(text, label=""):
    """Build a Step: an expression, an equation, or a final answer ('x = 1 or x = 4', 'x = 2 ± √3')."""
    parts = [p for p in re.split(r"\s+or\s+", text.strip(), flags=re.I) if p]
    nodes = []
    for p in parts:
        nodes += A.branches(parse_ast(p))
    if len(nodes) > 1:
        if all(isinstance(n, A.Equation) and isinstance(n.lhs, A.Var) for n in nodes) \
                and len({n.lhs.name for n in nodes}) == 1:
            var = sp.Symbol(nodes[0].lhs.name)
            return Step(text, None, "solutions", sp.FiniteSet(*[to_sympy(n.rhs) for n in nodes]), var, label)
        raise ParseError("Write alternatives as  x = 1 or x = 4")
    node = nodes[0]
    value = to_sympy(node)
    if isinstance(node, A.Equation):
        syms = value.free_symbols
        return Step(text, node, "equation", value, next(iter(syms)) if len(syms) == 1 else None, label)
    return Step(text, node, "expr", value, None, label)


@dataclass
class Judgement:
    verdict: str
    reason: str


def _solutions(step, var):
    return step.value if step.kind == "solutions" else solution_set(step.node, var)


def _diagnose(prev, cur, fallback):
    d = run_rules(prev, cur)
    if d:
        return Judgement(WARN if d.severity == "warning" else BAD, d.text())
    return Judgement(BAD, fallback)


def judge_labelled(prev, cur):
    try:
        transform, arg = derivation.parse_label(cur.label)
    except ValueError as exc:
        return Judgement(UNSURE, str(exc))
    if prev.kind != "expr" or cur.kind != "expr":
        if transform.name in ("expand", "factor", "simplify", "rearrange"):
            return judge_plain(prev, cur)
        return Judgement(UNSURE, f"[{cur.label}] applies to expressions, not equations.")
    v = transform.verify(prev.value, cur.value, arg)
    text = f"[{transform.name}] {derivation.STATUS_TEXT[v.status]}. {v.detail}"
    if v.status in (derivation.PROVED, derivation.CHECKED):
        return Judgement(OK, text)
    if v.status == derivation.UNVERIFIED:
        return Judgement(UNSURE, text)
    if transform.name == "d/dx":
        var = arg or (sorted(prev.value.free_symbols, key=lambda s: s.name) or [sp.Symbol("x")])[0].name
        labelled = Step(prev.text, prev.node, "expr", prev.value, None, f"d/d{var}")
        return _diagnose(labelled, cur, text)
    return _diagnose(prev, cur, text)


def judge_plain(prev, cur):
    if prev.kind == "expr" and cur.kind == "expr":
        r = compare(prev.node, cur.node)
        if r.verdict == EXACT:
            return Judgement(OK, "Equivalent to the previous step (proved symbolically).")
        if r.verdict == CONDITIONAL:
            return Judgement(OK, "Equivalent where both are defined: " + ", ".join(r.restrictions)
                             + ". " + r.reasons[-1])
        if r.verdict == NUMERIC:
            return Judgement(OK, "Agrees with the previous step numerically; not proved symbolically. "
                             + r.reasons[-1])
        if r.verdict == NOT:
            return _diagnose(prev, cur, "Not equal to the previous step. " + r.reasons[-1])
        return Judgement(UNSURE, "Couldn't decide whether this equals the previous step.")

    if prev.kind == "expr" or cur.kind == "expr":
        return Judgement(UNSURE, "Can't compare an equation with a plain expression. Keep every step the same kind.")

    var = single_var(prev, cur)
    if var is None:
        if prev.kind == cur.kind == "equation" and proportional(sp.expand(prev.residual), sp.expand(cur.residual)):
            return Judgement(OK, "Equivalent equation (rearranged or scaled).")
        d = run_rules(prev, cur)
        if d:
            return Judgement(WARN if d.severity == "warning" else BAD, d.text())
        return Judgement(UNSURE, "Couldn't verify this step automatically (several variables, "
                                 "and not a simple rearrangement).")
    try:
        s1, s2 = _solutions(prev, var), _solutions(cur, var)
    except (NotImplementedError, ValueError, TypeError):
        return Judgement(UNSURE, "Couldn't solve these equations to compare them.")
    if s1 == s2:
        if prev.kind == cur.kind == "equation" and proportional(sp.expand(prev.residual), sp.expand(cur.residual)):
            return Judgement(OK, "Equivalent equation (rearranged or scaled).")
        return Judgement(OK, "Same solutions as the previous step: " + show_solutions(s1, var) + ".")
    if isinstance(s1, sp.FiniteSet) and isinstance(s2, sp.FiniteSet):
        lost, gained = s1 - s2, s2 - s1
        parts = []
        if lost:
            parts.append("lost " + show_solutions(lost, var))
        if gained:
            parts.append("gained " + show_solutions(gained, var) + ", which is not a solution")
        fallback = (f"This step {' and '.join(parts)}. The previous step's solutions are "
                    f"{show_solutions(s1, var)}.")
    else:
        fallback = "This equation doesn't have the same solutions as the previous step."
    return _diagnose(prev, cur, fallback)


def check(text):
    """Return result pods: a verdict, then one card per step."""
    raw = split_steps(text)
    steps = []
    for i, (label, body) in enumerate(raw, 1):
        try:
            steps.append(parse_step(body, label))
        except ParseError as exc:
            raise ParseError(f"Step {i} ('{body}'): {exc.message}") from None

    pods = [("Step 1 · starting point", raw[0][1].replace("**", "^"))]
    first_bad = first_warn = None
    unsure = 0
    for i in range(1, len(steps)):
        prev, cur = steps[i - 1], steps[i]
        j = judge_labelled(prev, cur) if cur.label else judge_plain(prev, cur)
        if j.verdict == BAD and first_bad is None:
            first_bad = i + 1
        if j.verdict == WARN and first_warn is None:
            first_warn = i + 1
        unsure += j.verdict == UNSURE
        shown = (f"[{cur.label}] " if cur.label else "") + raw[i][1].replace("**", "^")
        pods.append((f"Step {i + 1} · {j.verdict}", f"{shown}\n{j.reason}"))

    summary = _summary(steps, first_bad, first_warn, unsure)
    return [("Verdict", summary)] + pods


def _summary(steps, first_bad, first_warn, unsure):
    lines = []
    if first_bad:
        lines.append(f"First mistake is in step {first_bad}. Later steps are checked against the step just before them.")
    elif first_warn:
        lines.append(f"No outright errors, but step {first_warn} needs care (see below).")
    elif unsure:
        lines.append(f"No mistakes found, but {unsure} step(s) couldn't be verified automatically.")
    else:
        lines.append(f"All {len(steps)} steps check out. Nice work!")
    # Compare the final answer with the original problem: errors can cancel, and
    # warnings (like squaring) only matter if the final answer is affected.
    first, last = steps[0], steps[-1]
    if first.kind == "equation" and last.kind in ("equation", "solutions"):
        var = single_var(first, last)
        if var is not None:
            try:
                want, got = _solutions(first, var), _solutions(last, var)
                if want == got:
                    if first_bad or first_warn:
                        lines.append(f"Your final answer is still right: {show_solutions(want, var)}.")
                else:
                    lines.append(f"Final answer: you have {show_solutions(got, var)}, "
                                 f"but the original equation's solutions are {show_solutions(want, var)}.")
            except (NotImplementedError, ValueError, TypeError):
                pass
    return " ".join(lines)
