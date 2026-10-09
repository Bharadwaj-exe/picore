"""Algebra mal-rules: expansion, distribution, cancellation, exponents, logarithms, fractions."""
import sympy as sp

from ...lang import ast as A
from ...lang.sympy_backend import from_sympy, to_sympy
from .core import Diagnosis, MalRule, RewriteRule, fmt, proportional, register, same_value

Num, BinOp, Neg, Call = A.Num, A.BinOp, A.Neg, A.Call


def _is(node, op):
    return isinstance(node, BinOp) and node.op == op


def _terms(node):
    """Flatten a +/− chain into signed terms: a - b + c -> [a, -b, c]."""
    if _is(node, "+"):
        return _terms(node.left) + _terms(node.right)
    if _is(node, "-"):
        return _terms(node.left) + [Neg(t) for t in _terms(node.right)]
    return [node]


def _sum(terms):
    out = terms[0]
    for t in terms[1:]:
        out = BinOp("-", out, t.operand) if isinstance(t, Neg) else BinOp("+", out, t)
    return out


def _int(node):
    try:
        v = to_sympy(node)
        return int(v) if v.is_Integer else None
    except Exception:
        return None


@register
class SquareOfSum(RewriteRule):
    id = "algebra.square_of_sum"
    category = "Algebra · incorrect expansion"
    title = "A power of a sum is not the sum of the powers"
    explanation = ("(a + b)² ≠ a² + b². Expanding (a + b)² = (a + b)(a + b) gives a² + 2ab + b²: "
                   "the cross term 2ab is missing.")

    def buggy(self, node):
        if _is(node, "^") and (_is(node.left, "+") or _is(node.left, "-")):
            n = _int(node.right)
            if n and 2 <= n <= 6:
                terms = _terms(node.left)
                wrong = _sum([Neg(BinOp("^", t.operand, node.right)) if isinstance(t, Neg) and n % 2
                              else BinOp("^", t.operand if isinstance(t, Neg) else t, node.right) for t in terms])
                return [(wrong, sp.expand(to_sympy(node)))]
        return []


@register
class PartialDistribution(RewriteRule):
    id = "algebra.partial_distribution"
    category = "Algebra · incorrect distribution"
    title = "Multiply EVERY term inside the brackets"
    explanation = "k(a + b) = ka + kb. The factor outside the brackets was applied to only some of the terms."

    def buggy(self, node):
        out = []
        if _is(node, "*"):
            for k, group in ((node.left, node.right), (node.right, node.left)):
                if _is(group, "+") or _is(group, "-"):
                    terms = _terms(group)
                    for i in range(len(terms)):
                        changed = [BinOp("*", k, t) if j == i else t for j, t in enumerate(terms)]
                        out.append((_sum(changed), sp.expand(to_sympy(node))))
        return out


@register
class NegativeDistribution(RewriteRule):
    id = "algebra.sign_distribution"
    category = "Algebra · sign error"
    title = "A minus sign in front of brackets changes EVERY sign inside"
    explanation = "−(a + b) = −a − b and a − (b − c) = a − b + c. Only the first term's sign was changed."

    def buggy(self, node):
        group = None
        if isinstance(node, Neg) and (_is(node.operand, "+") or _is(node.operand, "-")):
            group, prefix = node.operand, None
        elif _is(node, "-") and (_is(node.right, "+") or _is(node.right, "-")):
            group, prefix = node.right, node.left
        if group is None:
            return []
        terms = _terms(group)
        first = terms[0]
        flipped = [first.operand if isinstance(first, Neg) else Neg(first)] + terms[1:]
        wrong = _sum(flipped) if prefix is None else _sum([prefix] + flipped)
        return [(wrong, sp.expand(to_sympy(node)))]


@register
class InvalidCancellation(RewriteRule):
    id = "algebra.invalid_cancellation"
    category = "Algebra · invalid cancellation"
    title = "You can only cancel FACTORS, not terms"
    explanation = ("In (a + b)/a, the a in the numerator is a term, not a factor, so it can't cancel. "
                   "(a + b)/a = 1 + b/a. Likewise (ka + b)/k = a + b/k: every term must be divided.")

    def buggy(self, node):
        if not _is(node, "/"):
            return []
        terms = _terms(node.left)
        if len(terms) < 2:
            return []
        den = to_sympy(node.right)
        correct = sp.expand(to_sympy(node))
        out = []
        for i, t in enumerate(terms):
            ts = to_sympy(t)
            rest = [u for j, u in enumerate(terms) if j != i]
            if sp.simplify(ts - den) == 0:                       # (a + b)/a -> b   and  -> 1 + b
                out.append((_sum(rest), correct))
                out.append((_sum([Num("1")] + rest), correct))
            q = sp.cancel(ts / den)
            divides_cleanly = sp.fraction(q)[1] == 1 and den != 1   # this term really is a multiple of den
            if divides_cleanly:                                      # (ka + b)/k -> a + b (only one term divided)
                pieces = list(terms)
                pieces[i] = from_sympy(q)
                out.append((_sum(pieces), correct))
        return out


@register
class FractionAddition(RewriteRule):
    id = "algebra.fraction_addition"
    category = "Algebra · fractions"
    TEXT = {
        "add": ("Fractions are not added by adding tops and bottoms",
                "a/b + c/d = (ad + bc)/(bd), not (a + c)/(b + d). Use a common denominator."),
        "split": ("A fraction does not split over a sum in its denominator",
                  "k/(a + b) ≠ k/a + k/b (try 1/(1 + 1) = 1/2, but 1/1 + 1/1 = 2). Only a sum on TOP splits: "
                  "(a + b)/k = a/k + b/k."),
    }

    def buggy(self, node):
        out = []
        if _is(node, "+") and _is(node.left, "/") and _is(node.right, "/"):
            wrong = BinOp("/", BinOp("+", node.left.left, node.right.left),
                          BinOp("+", node.left.right, node.right.right))
            out.append((wrong, ("add", sp.together(to_sympy(node)))))
        if _is(node, "/") and (_is(node.right, "+") or _is(node.right, "-")):      # 1/(x + y) -> 1/x + 1/y
            terms = _terms(node.right)
            wrong = _sum([Neg(BinOp("/", node.left, t.operand)) if isinstance(t, Neg) else BinOp("/", node.left, t)
                          for t in terms])
            out.append((wrong, ("split", f"{A.to_text(node)} cannot be split into separate fractions")))
        return out

    def describe(self, at, info):
        return self.TEXT[info[0]]

    def correct_for(self, at, info):
        return info[1]


@register
class ExponentRules(RewriteRule):
    id = "algebra.exponent_rules"
    category = "Algebra · exponent rules"
    title = "Exponent rule misapplied"

    RULES = {
        "mul": ("xᵃ · xᵇ = xᵃ⁺ᵇ: when multiplying powers of the same base, ADD the exponents.",),
        "pow": ("(xᵃ)ᵇ = xᵃᵇ: a power of a power MULTIPLIES the exponents.",),
        "div": ("xᵃ / xᵇ = xᵃ⁻ᵇ: when dividing powers of the same base, SUBTRACT the exponents.",),
        "neg": ("x⁻ⁿ = 1/xⁿ: a negative exponent means a reciprocal, not a negative number.",),
        "prod": ("(ab)ⁿ = aⁿbⁿ: the power applies to EVERY factor in the brackets.",),
        "sumexp": ("x^(a + b) = xᵃ · xᵇ: a sum in the exponent becomes a PRODUCT of powers, not a sum.",),
    }

    def buggy(self, node):
        out = []
        correct = None
        try:
            correct = sp.powsimp(sp.expand(to_sympy(node)))
        except Exception:
            pass
        if _is(node, "*") and _is(node.left, "^") and _is(node.right, "^") and node.left.left == node.right.left:
            out.append((BinOp("^", node.left.left, BinOp("*", node.left.right, node.right.right)), ("mul", correct)))
        if _is(node, "^") and _is(node.left, "^"):
            out.append((BinOp("^", node.left.left, BinOp("+", node.left.right, node.right)), ("pow", correct)))
        if _is(node, "/") and _is(node.left, "^") and _is(node.right, "^") and node.left.left == node.right.left:
            out.append((BinOp("^", node.left.left, BinOp("/", node.left.right, node.right.right)), ("div", correct)))
        if _is(node, "^") and isinstance(node.right, Neg):
            recip = f"{A.to_text(node)} = 1/{A.to_text(BinOp('^', node.left, node.right.operand))}"
            out.append((Neg(BinOp("^", node.left, node.right.operand)), ("neg", recip)))
        if _is(node, "^") and (_is(node.right, "+") or _is(node.right, "-")):
            terms = _terms(node.right)
            pieces = [BinOp("^", node.left, Neg(t.operand) if isinstance(t, Neg) else t) for t in terms]
            prod = f"{A.to_text(node)} = " + " · ".join(A.to_text(p) for p in pieces)
            out.append((_sum(pieces), ("sumexp", prod)))
        if _is(node, "^") and _is(node.left, "*"):
            out.append((BinOp("*", node.left.left, BinOp("^", node.left.right, node.right)), ("prod", correct)))
        return out

    def describe(self, at, info):
        return self.title, self.RULES[info[0]][0]

    def correct_for(self, at, info):
        return info[1]


def _naive_root(piece):
    """√(u²) -> u, √9 -> 3 (what a student writes when splitting a root)."""
    neg = isinstance(piece, Neg)
    call = piece.operand if neg else piece
    arg = call.args[0]
    out = call
    try:   # take the root as if every variable were positive: √(9y²) -> 3y, √9 -> 3
        value = to_sympy(arg)
        pos = {s: sp.Symbol(s.name, positive=True) for s in value.free_symbols}
        root = sp.sqrt(value.subs(pos)).subs({v: k for k, v in pos.items()})
        if not root.has(sp.sqrt(sp.Symbol("_")).func) and not any(p.exp.is_Rational and not p.exp.is_Integer
                                                                 for p in root.atoms(sp.Pow)):
            out = from_sympy(root)
    except Exception:
        pass
    return Neg(out) if neg else out


LINEAR_FUNCS = {"sin", "cos", "tan", "sqrt", "ln", "log", "exp", "log10"}


@register
class FunctionTreatedAsLinear(RewriteRule):
    """sin(a + b) → sin a + sin b, √(a + b) → √a + √b, ln(2x) → 2 ln x, ..."""
    id = "algebra.function_not_linear"
    category = "Algebra · function rules"

    TEXT = {
        "sin": ("sin is not linear", "sin(a + b) = sin a·cos b + cos a·sin b, and sin(2x) = 2 sin x cos x, not 2 sin x."),
        "cos": ("cos is not linear", "cos(a + b) = cos a·cos b − sin a·sin b, and cos(2x) = cos²x − sin²x, not 2 cos x."),
        "tan": ("tan is not linear", "tan(a + b) = (tan a + tan b)/(1 − tan a·tan b)."),
        "sqrt": ("A square root does not split over a sum", "√(a + b) ≠ √a + √b (try a = 9, b = 16: √25 = 5, but 3 + 4 = 7). "
                 "Only products split: √(ab) = √a·√b for a, b ≥ 0."),
        "ln": ("Logarithm rules misapplied", "ln(a + b) has no simple split. The real rules are ln(ab) = ln a + ln b and ln(aⁿ) = n·ln a; "
               "ln(kx) = ln k + ln x, not k·ln x."),
        "exp": ("eˣ does not split over a sum", "e^(a + b) = eᵃ · eᵇ, a product, not eᵃ + eᵇ."),
    }

    def buggy(self, node):
        if not (isinstance(node, Call) and node.func in LINEAR_FUNCS and len(node.args) == 1):
            return []
        arg = node.args[0]
        out = []
        correct = sp.expand_trig(sp.expand_log(to_sympy(node), force=True)) if node.func != "sqrt" else None
        if _is(arg, "+") or _is(arg, "-"):
            terms = _terms(arg)
            pieces = [Neg(Call(node.func, (t.operand,))) if isinstance(t, Neg) else Call(node.func, (t,)) for t in terms]
            out.append((_sum(pieces), correct))
            if node.func == "sqrt":         # students usually also take √(x²) = x and √9 = 3
                out.append((_sum([_naive_root(p) for p in pieces]), correct))
        if _is(arg, "*") and isinstance(arg.left, Num):
            out.append((BinOp("*", arg.left, Call(node.func, (arg.right,))), correct))
        if _is(arg, "/") and isinstance(arg.right, Num):                 # sin(θ/2) -> sin(θ)/2
            out.append((BinOp("/", Call(node.func, (arg.left,)), arg.right), correct))
        return out

    def describe(self, at, info):
        key = "ln" if at.func in ("ln", "log", "log10") else at.func
        return self.TEXT[key]


@register
class LogProductRules(RewriteRule):
    id = "algebra.log_rules"
    category = "Algebra · logarithm rules"
    title = "Logarithm rule misapplied"
    TEXT = {
        "prod": "ln(ab) = ln a + ln b, a SUM, not ln a · ln b.",
        "quot": "ln(a/b) = ln a − ln b, a DIFFERENCE, not ln a / ln b.",
        "pow": "ln(aⁿ) = n·ln a: the exponent comes down as a factor; it is not (ln a)ⁿ.",
        "sum": "ln a + ln b = ln(ab), not ln(a + b).",
    }

    def buggy(self, node):
        logs = ("ln", "log")
        out = []
        if isinstance(node, Call) and node.func in logs and len(node.args) == 1:
            arg, f = node.args[0], node.func
            if _is(arg, "*"):
                out.append((BinOp("*", Call(f, (arg.left,)), Call(f, (arg.right,))), "prod"))
            if _is(arg, "/"):
                out.append((BinOp("/", Call(f, (arg.left,)), Call(f, (arg.right,))), "quot"))
            if _is(arg, "^"):
                out.append((BinOp("^", Call(f, (arg.left,)), arg.right), "pow"))
        if (_is(node, "+") and isinstance(node.left, Call) and isinstance(node.right, Call)
                and node.left.func in logs and node.left.func == node.right.func):
            out.append((Call(node.left.func, (BinOp("+", node.left.args[0], node.right.args[0]),)), "sum"))
        return out

    def describe(self, at, info):
        return self.title, self.TEXT[info]

    def correct_for(self, at, info):
        if info == "sum":
            return sp.logcombine(to_sympy(at), force=True)
        return sp.expand_log(to_sympy(at), force=True)


def _as_log10(node):
    if isinstance(node, Call) and node.func == "log" and len(node.args) == 1:
        return Call("log10", (_as_log10(node.args[0]),))
    kids = A.children(node)
    return A.with_children(node, tuple(_as_log10(k) for k in kids)) if kids else node


@register
class LogBase(MalRule):
    """log(1000x) -> 3 + log(x): the student reads log as base 10. In Pi Core log means ln.
    Detected by re-reading BOTH steps with log = log10: if the step is then valid, that was the cause."""
    id = "algebra.log_base"
    category = "Algebra · logarithm base"
    applies_to = ("expr", "equation")

    def detect(self, prev, cur):
        if prev.node is None or cur.node is None:
            return None
        if not any(isinstance(n, Call) and n.func == "log" for n in A.walk(prev.node)):
            return None
        try:
            p10, c10 = to_sympy(_as_log10(prev.node)), to_sympy(_as_log10(cur.node))
        except Exception:
            return None
        if isinstance(p10, sp.Equality) or isinstance(c10, sp.Equality):
            ok = isinstance(p10, sp.Equality) and isinstance(c10, sp.Equality) and                 proportional(sp.expand(p10.lhs - p10.rhs), sp.expand(c10.lhs - c10.rhs))
        else:
            ok = same_value(p10, c10)
        if not ok:
            return None
        return Diagnosis(self.id, self.category, "log here means the natural logarithm ln",
                         "This step is right if log means log base 10, but in Pi Core (as in most of calculus) "
                         "log x means ln x. Write log10(x) for a base-10 logarithm.",
                         f"with ln: {A.to_text(prev.node)} = {fmt(sp.expand_log(prev.value, force=True))}")
