"""Commands backed by the reasoning layer: equivalence questions and verified derivations.

    equiv (x^2-1)/(x-1) ; x+1          (also: compare A with B, is A = B, why A = B, A ≡ B)
    derive (x+1)^2 : expand, d/dx, sub x=1
"""
import re

import sympy as sp

from ..lang import parse
from ..reasoning.derivation import STATUS_TEXT, derive
from ..reasoning.equivalence import compare
from .parser import ParseError, split_top_level

_RE_EQUIV = re.compile(r"^(?:equiv(?:alent)?|compare|is|why(?:\s+is)?)\s+(.+?)\??$", re.I)
_RE_DERIVE = re.compile(r"^derive\s+(.+?)\s*:\s*(.+)$", re.I)


def _fmt(e):
    from .local import fmt
    return fmt(e)


def match(text):
    """Return pods if ``text`` is a reasoning command, else None."""
    m = _RE_DERIVE.match(text)
    if m:
        return derivation_pods(m.group(1), [r for r in split_top_level(m.group(2), [",", "->", ";"])])
    m = _RE_EQUIV.match(text)
    body = m.group(1) if m else (text if "≡" in text else None)
    if body is not None:
        for seps in (["≡", "=="], [";"], [" with ", " and ", " vs "], ["="], [","]):
            parts = split_top_level(body, seps)
            if len(parts) == 2:
                return equivalence_pods(parts[0], parts[1])
        if m and m.group(0).split()[0].lower() in ("equiv", "equivalent", "compare"):
            raise ParseError("Compare two expressions like:  equiv (x+1)^2 ; x^2+2x+1")
        # 'is …' / 'why …' without two expressions is probably an English question: not ours
    return None


def equivalence_pods(a_text, b_text):
    a, b = parse(a_text), parse(b_text)
    r = compare(a, b)
    pods = [("Question", f"Is {a_text.strip()} the same as {b_text.strip()}?"),
            ("Verdict", r.title + (f" ({', '.join(r.restrictions)})" if r.restrictions else ""))]
    pods.append(("Why", "\n".join(r.reasons)))
    if r.evidence is not None and r.evidence.status == "passed":
        pods.append(("Note", "Numerical agreement at sample points is evidence, not a proof."))
    return pods


def derivation_pods(start, rules):
    steps = derive(start, rules)
    pods = [("Start", start.strip())]
    C = sp.Symbol("C")
    for i, s in enumerate(steps, 1):
        shown = f"{_fmt(s.value - C)} + C" if s.value.has(C) else _fmt(s.value)
        rule = s.rule.replace("d/dx ", "d/d") if s.rule.startswith("d/dx ") else s.rule
        pods.append((f"Step {i} · [{rule}]  ({STATUS_TEXT[s.verification.status]})",
                     f"{shown}\n{s.verification.detail}"))
    return pods
