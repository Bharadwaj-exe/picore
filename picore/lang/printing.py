"""Human-readable rendering of SymPy values (shared by every layer above lang)."""
import re

import sympy as sp


def fmt(value):
    """Human-friendly one-line rendering of a SymPy object."""
    if isinstance(value, sp.Float) or (getattr(value, "is_number", False) and value.is_Float):
        return format(float(value), ".15g")
    text = sp.sstr(value)
    text = text.replace("**", "^")
    text = re.sub(r"\bpi\b", "π", text)
    text = re.sub(r"\boo\b", "∞", text)
    text = re.sub(r"\bI\b", "i", text)
    text = re.sub(r"\bE\b", "e", text)
    text = re.sub(r"\blog\(", "ln(", text)
    text = text.replace("sqrt", "√")
    text = re.sub(r"√\(([A-Za-z]|\d+)\)", r"√\g<1>", text)   # √(6) -> √6, √(x) -> √x
    text = re.sub(r"(?<![\w.^])(\d+)\*(?=[A-Za-zπ√(])", r"\g<1>", text)  # 2*x -> 2x, but not x^2*cos
    return text.replace("*", "·")


def needs_approx(v):
    if not getattr(v, "is_number", False):
        return False
    re_, im_ = v.as_real_imag()
    return not (re_.is_Rational and im_.is_Rational)


def approx(v, digits=10):
    re_, im_ = (sp.N(part, digits) for part in v.as_real_imag())
    if im_ == 0:
        return format(float(re_), f".{digits}g")
    sign = "+" if im_ >= 0 else "-"
    return f"{format(float(re_), f'.{digits}g')} {sign} {format(abs(float(im_)), f'.{digits}g')}i"
