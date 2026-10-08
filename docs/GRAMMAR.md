# Pi Core math language

Pi Core reads maths in three stages, implemented in [`picore/lang/`](../picore/lang):

```
raw text ──lexer──▶ tokens ──recursive-descent parser──▶ AST ──backend──▶ SymPy
                                                          │
                                                          └──▶ domain analysis, AST viewer,
                                                               mistake rules, printing
```

Nothing in this pipeline calls Python's `eval` or `exec`. Input that is not in the grammar is a
`ParseError` with the character position of the problem.

## Tokens (`lexer.py`)

| Kind | Examples | Notes |
|---|---|---|
| `NUM` | `2` `0.5` `.5` `1e5` `2.5E-3` | `2e` is `2·e`; an exponent needs digits |
| `VAR` | `x` `y` `theta` `θ` | single letters and Greek letter names |
| `CONST` | `pi` `π` `e` `i` `oo` `∞` `inf` | |
| `FUNC` | `sin` `cos` `tan` `asin` `ln` `log` `log10` `log2` `sqrt` `cbrt` `abs` `floor` `ceil` `exp` `factorial` … | |
| `OP` | `+` `-` `*` `/` `^` | `**` `×` `·` `÷` `−` are accepted spellings |
| `PM` | `±` `+/-` | plus-or-minus, for answers |
| `SQRT` | `√` | |
| `DERIV` | `d/dx` | `d/d` followed by one letter |
| `BANG` `EQ` `LPAREN` `RPAREN` `COMMA` | `!` `=` `(` `)` `,` | |

Superscript digits are rewritten as powers: `x²` lexes as `x ^ 2`.

**Identifiers.** Letters run together in maths, so a run of letters is resolved by these rules, in order:

1. a function name (`sin`) → `FUNC`
2. a constant (`pi`, `e`, `i`) → `CONST`
3. a Greek letter name or a single letter → `VAR`
4. a function name followed by one variable (`sinx`, `cost`) → `FUNC VAR`
5. exactly two letters (`xy`) → `VAR VAR`
6. anything else (`what`) → error. Pi Core treats it as a word question and may send it to Wolfram|Alpha.

## Grammar (`parser.py`)

```ebnf
statement := side [ "=" side ] EOF
side      := expr
expr      := term { ("+" | "-" | "±") term }                  (* left-associative *)
term      := unary { ("*" | "/") unary | IMPLICIT power }      (* left-associative *)
unary     := ("-" | "+" | "±") unary | power
power     := postfix [ "^" unary ]                             (* right-associative *)
postfix   := primary { "!" }
primary   := NUM | CONST | VAR
           | "(" expr ")"
           | FUNC [ "^" NUM ] ( "(" expr { "," expr } ")" | power )
           | "√" power
           | DERIV power
```

`IMPLICIT` multiplication applies when a term is followed directly by something that can start a
`primary`: a number, name, function, `(`, `√` or `d/dx`. Examples: `2x`, `3(x+1)`, `x sin x`, `(x+1)(x-1)`.

### Precedence, lowest to highest

| Level | Operators | Associativity |
|---|---|---|
| 0 | `=` | none (only one per statement) |
| 1 | `+` `-` `±` | left |
| 2 | `*` `/` and implicit multiplication | left |
| 3 | unary `-` | prefix |
| 4 | `^` | **right** |
| 5 | `!` | postfix |
| 6 | numbers, names, calls, parentheses | |

### Conventions where notation is ambiguous

Each of these has a test in `tests/test_lang.py`.

| Input | Means | Why |
|---|---|---|
| `-2^2` | `-(2^2) = -4` | power binds tighter than negation (standard) |
| `2^3^2` | `2^(3^2) = 512` | power is right-associative (standard) |
| `1/2x` | `(1/2)·x` | implicit and explicit multiplication have the same precedence (Wolfram's choice too) |
| `sin x^2` | `sin(x^2)` | a function without parentheses takes a power-level argument |
| `sin^2 x`, `sin²x` | `(sin x)^2` | a power on the function name applies to the result |
| `√x^2` | `√(x^2)` | `√` behaves like a function |
| `√2x` | `√2 · x` | |
| `d/dx x^2 + 1` | `(d/dx x^2) + 1` | `d/dx` behaves like a function |
| `x = ±3` | `x = 0 ± 3` | |

## AST (`ast.py`)

Immutable nodes: `Num`, `Const`, `Var`, `Neg`, `BinOp(op, left, right, implicit)`, `PlusMinus`, `Call(func, args)`,
`Factorial`, `Deriv(var, operand)`, `Equation(lhs, rhs)`.

Every node has a `span`: the `(start, end)` slice of the input it came from. Spans are **not** part
of equality, so two trees are equal when their mathematical structure is equal. The helpers are:

| Helper | What it does |
|---|---|
| `walk`, `children`, `with_children` | traversal |
| `to_text` | prints with the minimum parentheses; `parse(to_text(t)) == t` |
| `branches` | expands `±` into separate trees |
| `precedence`, `label`, `kind` | used by the AST viewer |

## Backend (`sympy_backend.py`)

`to_sympy` converts a tree to SymPy, refusing numbers that would hang the machine:

| Limit | Value |
|---|---|
| Exponent on a numeric base | at most 5000 |
| Integer literal length | at most 100 digits |
| Factorial argument | at most 1000 |
| Input length | at most 300 characters |
| Nesting depth | at most 60 |

`domain_conditions` reads the **AST** to find where an expression is defined: denominators ≠ 0,
negative powers, log arguments > 0, square-root arguments ≥ 0, and tan/sec/cot/csc poles. This must
happen before SymPy runs, because SymPy simplifies `x/x` to `1` and forgets that x = 0 is excluded.
