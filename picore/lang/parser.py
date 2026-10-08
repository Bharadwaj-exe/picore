"""Recursive-descent parser: tokens -> AST.

Grammar (EBNF). Each rule is one method below. Lower rules bind tighter.

    statement := side [ "=" side ] EOF
    side      := expr
    expr      := term { ("+" | "-" | "±") term }                 left-associative
    term      := unary { ("*" | "/") unary | <implicit> power }    left-associative
    unary     := ("-" | "+") unary | power
    power     := postfix [ "^" unary ]                            right-associative
    postfix   := primary { "!" }
    primary   := NUM | CONST | VAR
               | "(" expr ")"
               | FUNC [ "^" NUM ] ( "(" expr { "," expr } ")" | power )
               | "√" power
               | DERIV power                                      d/dx f

<implicit> multiplication happens when a term is followed directly by something
that can start a primary (number, name, function, "(", "√", d/dx): 2x, 3(x+1), x sin x.

Deliberate conventions (each has a test):
  * -2^2 = -(2^2) = -4         power binds tighter than negation
  * 2^3^2 = 2^(3^2) = 512      power is right-associative
  * 1/2x = (1/2)·x             implicit multiplication has the same precedence as '*'
  * sin x^2 = sin(x^2)         a function without parentheses takes a power-level argument
  * sin^2 x = (sin x)^2        a power on the function name applies to the result
  * √x^2 = √(x^2), √2x = √2·x  '√' takes a power-level argument, like a function
  * d/dx x^2 + 1 = (d/dx x^2) + 1
"""
from . import ast as A
from .errors import ParseError
from .lexer import tokenize

MAX_DEPTH = 60
_STARTS_PRIMARY = {"NUM", "CONST", "VAR", "FUNC", "LPAREN", "SQRT", "DERIV"}


class Parser:
    def __init__(self, text):
        self.text = text
        self.tokens = tokenize(text)
        self.i = 0
        self.depth = 0

    # ---- helpers ---------------------------------------------------------------
    @property
    def tok(self):
        return self.tokens[self.i]

    def advance(self):
        t = self.tokens[self.i]
        self.i += 1
        return t

    def at(self, kind, value=None):
        t = self.tok
        return t.kind == kind and (value is None or t.value == value)

    def expect(self, kind, value, message):
        if not self.at(kind, value):
            raise self.error(message)
        return self.advance()

    def error(self, message=None):
        t = self.tok
        if message is None:
            message = "Unexpected end of input" if t.kind == "EOF" else f"Unexpected '{self.text[t.pos:t.end]}'"
        return ParseError(message, t.pos)

    def span(self, start_tok):
        prev = self.tokens[self.i - 1]
        return (start_tok.pos, max(prev.end, start_tok.end))

    def enter(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ParseError("Expression is nested too deeply", self.tok.pos)

    def leave(self):
        self.depth -= 1

    # ---- grammar rules ---------------------------------------------------------
    def statement(self):
        if self.at("EOF"):
            raise ParseError("Empty expression")
        start = self.tok
        lhs = self.expr()
        if self.at("EQ"):
            self.advance()
            if self.at("EQ"):
                raise self.error("Use a single '=' per equation")
            rhs = self.expr()
            if self.at("EQ"):
                raise self.error("Use a single '=' per equation")
            node = A.Equation(lhs, rhs, span=self.span(start))
        else:
            node = lhs
        if not self.at("EOF"):
            raise self.error()
        return node

    def expr(self):
        self.enter()
        start = self.tok
        node = self.term()
        while self.at("OP", "+") or self.at("OP", "-") or self.at("PM"):
            op = self.advance()
            if self.at("EOF"):
                raise ParseError(f"Expected something after '{op.value}'", op.pos)
            right = self.term()
            if op.kind == "PM":
                node = A.PlusMinus(node, right, span=self.span(start))
            else:
                node = A.BinOp(op.value, node, right, span=self.span(start))
        self.leave()
        return node

    def term(self):
        start = self.tok
        node = self.unary()
        while True:
            if self.at("OP", "*") or self.at("OP", "/"):
                op = self.advance()
                if self.at("EOF"):
                    raise ParseError(f"Expected something after '{op.value}'", op.pos)
                node = A.BinOp(op.value, node, self.unary(), span=self.span(start))
            elif self.tok.kind in _STARTS_PRIMARY:
                node = A.BinOp("*", node, self.power(), implicit=True, span=self.span(start))
            else:
                return node

    def unary(self):
        if self.at("PM"):                                # x = ±3  means  x = 0 ± 3
            start = self.advance()
            self.enter()
            operand = self.unary()
            self.leave()
            return A.PlusMinus(A.Num("0", span=(start.pos, start.pos)), operand, span=self.span(start))
        if self.at("OP", "-") or self.at("OP", "+"):
            start = self.advance()
            self.enter()
            operand = self.unary()
            self.leave()
            if start.value == "+":
                return operand
            return A.Neg(operand, span=self.span(start))
        return self.power()

    def power(self):
        start = self.tok
        base = self.postfix()
        if self.at("OP", "^"):
            caret = self.advance()
            if self.at("EOF"):
                raise ParseError("Expected an exponent after '^'", caret.pos)
            self.enter()
            exponent = self.unary()
            self.leave()
            return A.BinOp("^", base, exponent, span=self.span(start))
        return base

    def postfix(self):
        start = self.tok
        node = self.primary()
        while self.at("BANG"):
            self.advance()
            node = A.Factorial(node, span=self.span(start))
        return node

    def primary(self):
        t = self.tok
        if t.kind == "NUM":
            self.advance()
            return A.Num(t.value, span=(t.pos, t.end))
        if t.kind == "CONST":
            self.advance()
            return A.Const(t.value, span=(t.pos, t.end))
        if t.kind == "VAR":
            self.advance()
            return A.Var(t.value, span=(t.pos, t.end))
        if t.kind == "LPAREN":
            self.advance()
            if self.at("RPAREN"):
                raise self.error("Empty parentheses")
            inner = self.expr()
            self.expect("RPAREN", None, "Missing ')'")
            return _respan(inner, self.span(t))
        if t.kind == "FUNC":
            return self.function()
        if t.kind == "SQRT":
            self.advance()
            self.enter()
            arg = self.power()
            self.leave()
            return A.Call("sqrt", (arg,), span=self.span(t))
        if t.kind == "DERIV":
            self.advance()
            self.enter()
            arg = self.power()
            self.leave()
            return A.Deriv(t.value, arg, span=self.span(t))
        raise self.error("Expected a number, variable or '('" if t.kind != "EOF" else "Unexpected end of input")

    def function(self):
        start = self.advance()
        name = start.value
        outer_power = None
        if self.at("OP", "^"):                       # sin^2 x
            self.advance()
            if not self.at("NUM"):
                raise self.error(f"Expected a number after '{name}^'")
            n = self.advance()
            outer_power = A.Num(n.value, span=(n.pos, n.end))
        self.enter()
        if self.at("LPAREN"):
            self.advance()
            if self.at("RPAREN"):
                raise self.error(f"'{name}' needs an argument")
            args = [self.expr()]
            while self.at("COMMA"):
                self.advance()
                args.append(self.expr())
            self.expect("RPAREN", None, "Missing ')'")
        elif self.tok.kind in _STARTS_PRIMARY or self.at("OP", "-"):
            args = [self.unary() if self.at("OP", "-") else self.power()]
        else:
            raise self.error(f"'{name}' needs an argument")
        self.leave()
        node = A.Call(name, tuple(args), span=self.span(start))
        if outer_power is not None:
            node = A.BinOp("^", node, outer_power, span=self.span(start))
        return node


def _respan(node, span):
    """Parenthesized subexpressions keep the span including their parentheses."""
    from dataclasses import replace
    return replace(node, span=span)


def parse(text):
    """Parse a full statement (expression or equation) into an AST."""
    return Parser(text).statement()
