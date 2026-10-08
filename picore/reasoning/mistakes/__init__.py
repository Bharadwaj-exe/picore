"""Mistake Detective 2.0: explain WHY a step is wrong, not just THAT it is.

Rule modules register themselves on import; the order below is the order rules
are tried: specific misconceptions first, then verification-based diagnoses.
"""
from . import algebra, calculus, trig, equations, checks  # noqa: F401  (registration order)
from .core import RULES, Diagnosis, MalRule, Step, register, run_rules

__all__ = ["RULES", "Diagnosis", "MalRule", "Step", "register", "run_rules"]
