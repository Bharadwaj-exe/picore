"""Mistake detective: check a student's working step by step.

    check 2(x+3) = 10 -> 2x + 6 = 10 -> 2x = 4 -> x = 3

Each step is compared with the one before it:
  * expressions must be equal (symbolically, or at least at random sample points)
  * equations must have the same solutions (dropping or inventing a root is a mistake)
"""
import random
import re

import sympy as sp

from .parser import ParseError, parse_relation, split_top_level

SEPARATORS = ["->", "=>", "→", ";", "\n"]
OK, BAD, UNSURE = "correct", "mistake", "unsure"


def split_steps(text):
    text = re.sub(r"^\s*check\s+", "", text, flags=re.I)
    steps = split_top_level(text, SEPARATORS)
    if len(steps) < 2:
        raise ParseError("Give at least two steps, e.g.  check 2x+6=10 -> 2x=4 -> x=2")
    return steps


class Solutions:
    """A final answer like 'x = 1 or x = 4'."""

    def __init__(self, var, values):
        self.var, self.values = var, sp.FiniteSet(*values)


def parse_step(text):
    parts = [p for p in re.split(r"\s+or\s+", text.strip(), flags=re.I) if p]
    if len(parts) == 1:
        return parse_relation(text)
    rels = [parse_relation(p) for p in parts]
    if all(isinstance(r, sp.Equality) and r.lhs.is_Symbol for r in rels) and len({r.lhs for r in rels}) == 1:
        return Solutions(rels[0].lhs, [r.rhs for r in rels])
    raise ParseError("Write alternatives as  x = 1 or x = 4")


def _residual(rel):
    return rel.lhs - rel.rhs if isinstance(rel, sp.Equality) else rel


def _numeric_counterexample(a, b, syms, tries=12):
    """Find a point where a and b clearly differ, or None if they agree everywhere we look."""
    rng = random.Random(7)
    for _ in range(tries):
        point = {s: sp.Rational(rng.randint(-50, 50), rng.randint(1, 7)) for s in syms}
        try:
            va, vb = complex(a.subs(point).evalf()), complex(b.subs(point).evalf())
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(va - vb) > 1e-7 * max(1.0, abs(va), abs(vb)):
            return point, va, vb
    return None


def _fmt_num(z):
    if abs(z.imag) < 1e-12:
        return format(z.real, ".6g")
    return f"{z.real:.4g} + {z.imag:.4g}i"


def compare_expressions(a, b):
    try:
        if sp.simplify(a - b) == 0:
            return OK, "Same value: this rewrite is valid."
    except (TypeError, ValueError, NotImplementedError):
        pass
    syms = sorted(a.free_symbols | b.free_symbols, key=lambda s: s.name)
    hit = _numeric_counterexample(a, b, syms)
    if hit:
        point, va, vb = hit
        where = ", ".join(f"{s} = {v}" for s, v in point.items()) or "these values"
        return BAD, f"Not equal to the previous step. At {where} the previous step gives " \
                    f"{_fmt_num(va)} but this one gives {_fmt_num(vb)}."
    return OK, "Agrees with the previous step at every point tested."


def _solution_set(expr, var):
    return sp.solveset(sp.simplify(expr), var, domain=sp.S.Complexes)


def _as_solutions(rel, var):
    if isinstance(rel, Solutions):
        return rel.values
    return _solution_set(_residual(rel), var)


def compare_equations(e1, e2):
    if isinstance(e1, Solutions) or isinstance(e2, Solutions):
        var = e1.var if isinstance(e1, Solutions) else e2.var
        try:
            return _compare_sets(_as_solutions(e1, var), _as_solutions(e2, var), var)
        except (NotImplementedError, ValueError, TypeError):
            return UNSURE, "Couldn't verify this step automatically."
    f1, f2 = _residual(e1), _residual(e2)
    # Same equation scaled or rearranged: f1 = k * f2 for a non-zero constant k.
    try:
        ratio = sp.simplify(f1 / f2)
        if ratio.is_number and ratio != 0 and ratio.is_finite:
            return OK, "Equivalent equation (rearranged or scaled)."
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    syms = sorted(f1.free_symbols | f2.free_symbols, key=lambda s: s.name)
    if len(syms) != 1:
        return UNSURE, "Couldn't verify this step automatically (several variables, not a simple rearrangement)."
    var = syms[0]
    try:
        s1, s2 = _solution_set(f1, var), _solution_set(f2, var)
    except (NotImplementedError, ValueError, TypeError):
        return UNSURE, "Couldn't verify this step automatically."
    return _compare_sets(s1, s2, var)


def _compare_sets(s1, s2, var):
    if s1 == s2:
        return OK, "Same solutions as the previous step."
    if isinstance(s1, sp.FiniteSet) and isinstance(s2, sp.FiniteSet):
        from .local import fmt
        lost, gained = s1 - s2, s2 - s1
        parts = []
        if lost:
            parts.append("lost the solution" + ("s " if len(lost) > 1 else " ")
                         + ", ".join(f"{var} = {fmt(v)}" for v in lost))
        if gained:
            parts.append("added the wrong solution" + ("s " if len(gained) > 1 else " ")
                         + ", ".join(f"{var} = {fmt(v)}" for v in gained))
        hint = ""
        if lost and not gained:
            hint = "  (Dividing by something that can be zero, or taking only the + square root, does this.)"
        if gained and not lost:
            hint = "  (Squaring both sides can add solutions that don't work, so check each answer in the original.)"
        return BAD, "This step " + " and ".join(parts) + "." + hint
    return BAD, "This equation doesn't have the same solutions as the previous step."


def check(text):
    """Return result pods: one per step plus a summary."""
    steps = split_steps(text)
    rels = []
    for i, s in enumerate(steps, 1):
        try:
            rels.append(parse_step(s))
        except ParseError as exc:
            raise ParseError(f"Step {i} ('{s}'): {exc}") from None

    shown = [s.replace("**", "^") for s in steps]   # show the working exactly as typed
    pods = [("Step 1 · starting point", shown[0])]
    first_bad = None
    unsure = 0
    for i in range(1, len(rels)):
        prev, cur = rels[i - 1], rels[i]
        prev_eq = isinstance(prev, (sp.Equality, Solutions))
        cur_eq = isinstance(cur, (sp.Equality, Solutions))
        if prev_eq and cur_eq:
            verdict, why = compare_equations(prev, cur)
        elif not prev_eq and not cur_eq:
            verdict, why = compare_expressions(prev, cur)
        else:
            verdict, why = UNSURE, "Can't compare an equation with a plain expression. Keep every step the same kind."
        if verdict == BAD and first_bad is None:
            first_bad = i + 1
        unsure += verdict == UNSURE
        label = {OK: "correct", BAD: "mistake here", UNSURE: "couldn't check"}[verdict]
        pods.append((f"Step {i + 1} · {label}", f"{shown[i]}\n{why}"))

    if first_bad:
        summary = f"First mistake is in step {first_bad}. Later steps are checked against the step just before them."
    elif unsure:
        summary = f"No mistakes found, but {unsure} step(s) couldn't be verified automatically."
    else:
        summary = f"All {len(rels)} steps check out. Nice work!"
    return [("Verdict", summary)] + pods
