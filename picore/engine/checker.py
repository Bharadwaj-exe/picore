"""Mistake Detective: check a student's working step by step.

    check x^2 - 5x + 6 = 0 -> x^2 = 5x - 6 -> x = 5 ± √6
    check (x+1)^2 -> [expand] x^2 + 2x + 1 -> [d/dx] 2x + 2

Each step is judged against the one before it:
  * expressions: the equivalence engine (symbolic proof first, domains from the AST). A
    rewrite is valid if it equals the previous step wherever the previous step is
    defined; a result that is undefined somewhere the original was defined is wrong.
  * equations: proportional residuals (rearranged/scaled) first, then exact solution
    sets; if SymPy cannot produce finite sets, real solutions are compared numerically
    (evidence only, and only inside numeric.ROOT_RANGE).
  * labelled steps ``[rule]`` must be what that rule produces (see reasoning.derivation).
When a step is wrong, the mal-rule catalogue (reasoning.mistakes) tries to name the exact
misconception; if none reproduces the step, the evidence is shown without guessing why.
Answers rounded to the decimals shown are reported as "couldn't check", not as mistakes.
"""
import re
from dataclasses import dataclass

import sympy as sp

from ..lang import ast as A
from ..lang.printing import fmt
from ..lang.sympy_backend import to_sympy
from ..reasoning import derivation, numeric
from ..reasoning.equivalence import CONDITIONAL, EXACT, NOT, NUMERIC, compare
from ..reasoning.mistakes import Diagnosis, Step, run_rules
from ..reasoning.mistakes.core import proportional
from ..reasoning.mistakes.equations import (holds_at, is_finite, numeric_difference, show_approx,
                                            show_solutions, single_var, solutions)
from .parser import ParseError, parse_ast, split_top_level

SEPARATORS = ["->", "=>", "→", ";", "\n"]
OK, BAD, WARN, UNSURE = "correct", "mistake here", "check needed", "couldn't check"
SUPPORTED = "numerically supported"      # agrees at every test point, but not proved: neither correct nor wrong
MAX_STEPS = 12          # bounded work per 'check' (each step is also bounded by the lexer's MAX_LEN)


def split_steps(text):
    """'check a -> [rule] b -> c' -> [('', 'a'), ('rule', 'b'), ('', 'c')]"""
    text = re.sub(r"^\s*check\s+", "", text, flags=re.I)
    raw = split_top_level(text, SEPARATORS)
    if len(raw) < 2:
        raise ParseError("Give at least two steps, e.g.  check 2x+6=10 -> 2x=4 -> x=2")
    if len(raw) > MAX_STEPS:
        raise ParseError(f"Too many steps: check at most {MAX_STEPS} at a time")
    steps = []
    for r in raw:
        m = re.match(r"^\[([^\]]+)\]\s*(.*)$", r)
        steps.append((m.group(1).strip(), m.group(2).strip()) if m else ("", r))
    return steps


def parse_step(text, label=""):
    """Build a Step: an expression, an equation, a final answer ('x = 1 or x = 4', 'x = 2 ± √3'),
    or a disjunction of equations that still contain the variable ('x = ±√(2x + 8)')."""
    parts = [p for p in re.split(r"\s+or\s+", text.strip(), flags=re.I) if p]
    nodes = []
    for p in parts:
        nodes += A.branches(parse_ast(p))
    if len(nodes) > 1:
        if all(isinstance(n, A.Equation) and isinstance(n.lhs, A.Var) for n in nodes) \
                and len({n.lhs.name for n in nodes}) == 1:
            var = sp.Symbol(nodes[0].lhs.name)
            rhs = [to_sympy(n.rhs) for n in nodes]
            if not any(var in r.free_symbols for r in rhs):
                return Step(text, None, "solutions", sp.FiniteSet(*rhs), var, label)
        if all(isinstance(n, A.Equation) for n in nodes):
            eqs = [to_sympy(n) for n in nodes]
            product = sp.Mul(*[e.lhs - e.rhs for e in eqs])          # zero exactly where one branch holds
            syms = product.free_symbols
            return Step(text, None, "disjunction", sp.Eq(product, 0, evaluate=False),
                        next(iter(syms)) if len(syms) == 1 else None, label, tuple(nodes))
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
    rule: str = ""          # id of the rule that explains the step, if one does
    rule_kind: str = ""     # "misconception" | "descriptive"


def _from(d, fallback_verdict=None):
    verdict = WARN if d.severity == "warning" else (fallback_verdict or BAD)
    return Judgement(verdict, d.text(), d.rule, d.kind)


def _diagnose(prev, cur, fallback):
    d = run_rules(prev, cur)
    if d:
        return _from(d)
    return Judgement(BAD, fallback)


# ---- rounding ----------------------------------------------------------------------------

def _decimals(text):
    """Number of decimals in a plain decimal literal like 0.739 (None if not one)."""
    m = re.fullmatch(r"\s*-?\d*\.(\d+)\s*", text)
    return len(m.group(1)) if m else None


def _rounds_to(exact, shown_text):
    d = _decimals(shown_text)
    z = numeric._value(sp.sympify(exact) if not isinstance(exact, sp.Basic) else exact, {})
    if d is None or z is None or not numeric._is_real(z):
        return False
    return abs(z.real - float(shown_text)) <= 0.5 * 10 ** -d + 1e-12


def _rounded_answer(prev, cur, var):
    """True if every value in the student's answer is a correct rounding of a real solution."""
    if cur.kind == "solutions":
        texts = [p.split("=", 1)[1] for p in re.split(r"\s+or\s+", cur.text) if "=" in p]
    elif cur.kind == "equation" and isinstance(cur.node.lhs, A.Var):
        texts = [cur.text.split("=", 1)[1]]
    else:
        return False
    if not texts or any(_decimals(t) is None for t in texts):
        return False
    try:
        sols = solutions(prev, var)
        roots = [s for s in sols] if is_finite(sols) else numeric.real_roots(prev.residual, var)
    except (NotImplementedError, ValueError, TypeError):
        return False
    return all(any(_rounds_to(r, t) for r in roots) for t in texts)


# ---- labelled steps ------------------------------------------------------------------------

def judge_labelled(prev, cur):
    try:
        transform, arg = derivation.parse_label(cur.label)
    except ValueError as exc:
        return Judgement(UNSURE, str(exc))
    if transform.name in ("expand", "factor", "simplify", "rearrange"):
        # equality-preserving: same judgement as an unlabelled step (domains, rounding, mal-rules)
        j = judge_plain(prev, cur)
        j.reason = f"[{cur.label}] " + j.reason
        return j
    if prev.kind != "expr" or cur.kind != "expr":
        return Judgement(UNSURE, f"[{cur.label}] applies to expressions, not equations.")
    v = transform.verify(prev.value, cur.value, arg)
    text = f"[{cur.label}] {derivation.STATUS_TEXT[v.status]}. {v.detail}"
    if v.status in (derivation.PROVED, derivation.CHECKED):
        return Judgement(OK, text)
    if v.status == derivation.RESTRICTED:
        return Judgement(WARN, text, "calculus.antiderivative_domain", "descriptive")
    if v.status == derivation.UNVERIFIED:
        return Judgement(UNSURE, text)
    if transform.name == "d/dx":
        var = arg or (sorted(prev.value.free_symbols, key=lambda s: s.name) or [sp.Symbol("x")])[0].name
        labelled = Step(prev.text, prev.node, "expr", prev.value, None, f"d/d{var}")
        return _diagnose(labelled, cur, text)
    if transform.name == "substitute":
        try:     # e.g. sin(x) + 1 -> [sub x=30] 3/2 : judge the substituted expression (degrees?)
            substituted = parse_step(fmt(transform.apply(prev.value, arg)).replace("·", "*"))
            d = run_rules(substituted, cur)
            if d:
                return _from(d)
        except (ParseError, ValueError, TypeError):
            pass
    return _diagnose(prev, cur, text)


# ---- plain steps ---------------------------------------------------------------------------

def _domain_lost(prev, cur, r):
    restriction = ", ".join(r.restrictions)
    return Diagnosis(
        "domain.lost_domain", "Domain · part of the domain lost",
        "The new expression is undefined where the previous one was defined",
        f"The two agree only where both are defined ({restriction}), but the previous step was also "
        f"defined outside that set and this one is not, so the rewrite is not valid there.",
        "", kind="descriptive")


def _same_domain(prev, cur):
    """Proportional residuals only prove equivalence if neither equation excludes extra points:
    (x²−1)/(x−1) = 2 and x + 1 = 2 are proportional, but x = 1 is excluded from the first."""
    from ..lang.sympy_backend import domain_conditions
    cp, cc = domain_conditions(prev.node), domain_conditions(cur.node)
    return {(c.expr, c.kind) for c in cp} == {(c.expr, c.kind) for c in cc}


def judge_plain(prev, cur):
    if prev.kind == "expr" and cur.kind == "expr":
        r = compare(prev.node, cur.node)
        if r.verdict == EXACT:
            return Judgement(OK, "Equivalent to the previous step (verified symbolically).")
        if r.verdict == CONDITIONAL:
            if r.right_undefined_more:
                d = run_rules(prev, cur) or _domain_lost(prev, cur, r)
                return Judgement(BAD, d.text() + "\n" + r.reasons[-1], d.rule, d.kind)
            return Judgement(OK, "Equivalent wherever the previous step is defined (verified symbolically): "
                             + ", ".join(r.restrictions) + ". " + r.reasons[-1])
        if r.verdict == NUMERIC:
            if r.right_undefined_more:
                d = run_rules(prev, cur) or _domain_lost(prev, cur, r)
                return Judgement(BAD, d.text() + "\n" + r.reasons[-1], d.rule, d.kind)
            return Judgement(SUPPORTED, "Agrees with the previous step at every test point, but this was not "
                                        "verified symbolically. " + r.reasons[-1])
        if r.verdict == NOT:
            if not prev.value.free_symbols and _rounds_to(prev.value, cur.text):
                return Judgement(UNSURE, f"{cur.text.strip()} is {fmt(prev.value)} rounded to "
                                         f"{_decimals(cur.text)} decimal places (≈ {numeric._short(numeric._value(prev.value, {}))}), "
                                         f"not an exact equality.")
            return _diagnose(prev, cur, "Not equal to the previous step. " + r.reasons[-1])
        return Judgement(UNSURE, "Couldn't decide whether this equals the previous step (not verified).")

    if prev.kind == "expr" or cur.kind == "expr":
        return Judgement(UNSURE, "Can't compare an equation with a plain expression. Keep every step the same kind.")

    if prev.kind == cur.kind == "equation" and _same_domain(prev, cur)             and proportional(sp.expand(prev.residual), sp.expand(cur.residual)):
        return Judgement(OK, "Equivalent equation (rearranged or scaled by a non-zero constant).")

    var = single_var(prev, cur)
    if var is None:
        d = run_rules(prev, cur)
        if d:
            return _from(d)
        return Judgement(UNSURE, "Couldn't verify this step automatically (several variables, "
                                 "and not a simple rearrangement).")
    try:
        s1, s2 = solutions(prev, var), solutions(cur, var)
    except (NotImplementedError, ValueError, TypeError):
        s1 = s2 = None
    if s1 is not None and is_finite(s1) and is_finite(s2):
        if s1 == s2:
            return Judgement(OK, "Same solutions as the previous step: " + show_solutions(s1, var) + ".")
        if _rounded_answer(prev, cur, var):
            return Judgement(UNSURE, "These are the solutions rounded to the decimals shown, not exact values.")
        lost, gained = s1 - s2, s2 - s1
        parts = []
        if lost:
            parts.append("lost " + show_solutions(lost, var))
        if gained:
            parts.append("gained " + show_solutions(gained, var) + ", which is not a solution")
        return _diagnose(prev, cur, f"This step {' and '.join(parts)}. The previous step's solutions are "
                                    f"{show_solutions(s1, var)}.")
    if s1 is not None and s1 == s2:
        return Judgement(OK, "Same solutions as the previous step (verified symbolically).")
    if s1 is not None:      # infinite sets whose DIFFERENCE is finite can still be compared exactly
        try:
            lost, gained = s1 - s2, s2 - s1
        except (TypeError, ValueError):
            lost = gained = None
        if lost is not None and is_finite(lost) and is_finite(gained):
            parts = (["lost " + show_solutions(lost, var)] if lost else []) +                     (["gained " + show_solutions(gained, var) + ", which is not a solution of the previous step"]
                     if gained else [])
            return _diagnose(prev, cur, f"This step {' and '.join(parts)}.")
    return _judge_numerically(prev, cur, var)


def _judge_numerically(prev, cur, var):
    """Solution sets SymPy can't list exactly: compare real solutions numerically (evidence only)."""
    lo, hi = numeric.ROOT_RANGE
    lost, gained, found = numeric_difference(prev, cur, var)
    if not lost and not gained:
        if not found:
            return Judgement(UNSURE, f"Couldn't compare the solutions: none found numerically in [{lo:g}, {hi:g}] "
                                     f"for either equation (not verified).")
        return Judgement(SUPPORTED, f"Both equations have the same real solutions found numerically in "
                                    f"[{lo:g}, {hi:g}] (evidence, not proof; outside that range not checked).")
    if _rounded_answer(prev, cur, var):
        return Judgement(UNSURE, "These are the solutions rounded to the decimals shown, not exact values.")
    parts = []
    if lost:
        parts.append(f"lost {show_approx(lost, var)}, which solves the previous step but not this one")
    if gained:
        parts.append(f"gained {show_approx(gained, var)}, which solves this step but not the previous one")
    return _diagnose(prev, cur, "This step " + " and ".join(parts) + " (found numerically).")


def judge(prev, cur):
    """Judge one step (two Step objects)."""
    return judge_labelled(prev, cur) if cur.label else judge_plain(prev, cur)


def judge_step(prev_text, cur_text, label=""):
    """Judge one step from text: the structured entry point used by the evaluation benchmark."""
    return judge(parse_step(prev_text), parse_step(cur_text, label))


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
        j = judge(prev, cur)
        if j.verdict == BAD and first_bad is None:
            first_bad = i + 1
        if j.verdict == WARN and first_warn is None:
            first_warn = i + 1
        unsure += j.verdict in (UNSURE, SUPPORTED)
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
        lines.append(f"No mistakes found, but {unsure} step(s) couldn't be verified symbolically "
                     f"(see 'numerically supported' / 'couldn't check').")
    else:
        lines.append(f"All {len(steps)} steps check out. Nice work!")
    # Compare the final answer with the original problem: errors can cancel, and
    # warnings (like squaring) only matter if the final answer is affected.
    first, last = steps[0], steps[-1]
    if first.kind == "equation" and last.kind in ("equation", "solutions", "disjunction"):
        var = single_var(first, last)
        if var is not None:
            try:
                want, got = solutions(first, var), solutions(last, var)
                if is_finite(want) and is_finite(got):
                    if want == got:
                        if first_bad or first_warn:
                            lines.append(f"Your final answer is still right: {show_solutions(want, var)}.")
                    else:
                        lines.append(f"Final answer: you have {show_solutions(got, var)}, "
                                     f"but the original equation's solutions are {show_solutions(want, var)}.")
                elif last.kind == "solutions":
                    bad = [s for s in last.value if holds_at(first, var, complex(sp.N(s)).real) is False]
                    if bad:
                        lines.append(f"Final answer: {show_solutions(sp.FiniteSet(*bad), var)} does not satisfy "
                                     f"the original equation.")
            except (NotImplementedError, ValueError, TypeError):
                pass
    return " ".join(lines)
