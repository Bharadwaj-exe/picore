"""Pi Core's math language: lexer -> recursive-descent parser -> AST.

The lexer, parser and AST have no SymPy dependency; ``picore.lang.sympy_backend``
converts ASTs to SymPy for computation and analyses their domains.
"""
from . import ast
from .errors import ParseError
from .lexer import tokenize
from .parser import parse

__all__ = ["ast", "parse", "tokenize", "ParseError"]
