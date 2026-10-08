# Changelog

## 0.4.0: reasoning environment

πCore now reasons about maths instead of only computing it.

**New**
- **Native math language.** Lexer, recursive-descent parser and AST with source spans. The
  grammar and ambiguous-notation conventions are documented in `docs/GRAMMAR.md`. Errors report
  the exact character. New syntax: `±` / `+/-`, `x²`, `sin²x`, `d/dx f`, `x = ±3`.
- **Equivalence engine** with domain awareness. It distinguishes exact, conditional
  (`(x²−1)/(x−1) = x+1` only for x ≠ 1), numeric-only, not-equivalent and unknown. Commands:
  `equiv A ; B`, `is A = B`, `compare A with B`.
- **Numerical verification layer.** Finite-difference derivatives, antiderivatives, quadrature,
  and substituting roots back in. Results are always labelled as evidence, not proof.
- **Mistake Detective 2.0.** A catalogue of mal-rules covering algebra, equations, calculus and
  trigonometry (`docs/MISTAKES.md`). It names the violated rule and gives the correct
  transformation. It compares the final answer with the original problem. Warnings cover steps
  that are valid only with care, such as squaring.
- **Justified steps and derivations.** `-> [expand] …`, `[factor]`, `[d/dx]`, `[integrate]`
  (detects a missing `+ C`) and `[sub x=2]` are verified. `derive E : rule, rule, …` builds a
  verified chain.
- **Expression tree viewer.** `tree …` / TREE / Ctrl+T: highlight subtrees and the matching
  source text, inspect operator, precedence, operands and domain, and simplify a subtree with
  verification.
- **Parameter explorer.** `explore …` / EXPLORE / Ctrl+E: sliders and a live graph, with
  analyzers for quadratics (discriminant, roots, vertex, axis, with explanations), lines,
  sinusoids and any function.
- **Verification cards** on derivatives, integrals and solutions. Card borders show the verdict.

**Fixed**
- Equations without a closed-form solution reported "No solutions found". They now get
  numerical roots with an explanation, and "no solutions" appears only when proved.
- Cached fonts used after `pygame.quit()` crashed the interpreter.
- Some products printed as `x^2cos(x)`. They now print as `x^2·cos(x)`.

**Quality**
- Over 200 tests (up from 58), with line coverage at 86% (up from 44%).
- New tests include a parser fuzz test, headless tests for every screen, worker concurrency
  guarantees, and a performance budget.
- Mistake diagnosis looks for numerical counterexamples before symbolic simplification. It is up
  to 25× faster on hard inputs.
- Documentation: `docs/ARCHITECTURE.md`, `docs/GRAMMAR.md`, `docs/MISTAKES.md`, screenshots.

## 0.3.0: packaging and typography

- Windows build (PyInstaller) with a self-test and an optional Inno Setup installer.
- Cloudflare Worker proxy, so the Wolfram AppID never ships inside the app.
- GitHub Actions CI.
- Brush-style title font with a free fallback, Shippori Mincho text, and STIX Two Math symbols.
- Mistake Detective 1.0: checks working step by step.

## 0.2.0: from school project to app

- One window and one process, organised as scenes. Replaces three scripts launched with subprocess.
- SQLite history replaces a local MySQL server.
- Offline SymPy engine first, Wolfram|Alpha as a fallback.
- Background worker with timeouts. Errors appear as cards instead of crashing the app.
- Safe parser (no `eval`), native interactive graph, better text input, tests.

## 0.1.0: original

- Pygame calculator using the Wolfram|Alpha API, with a matplotlib graph window and MySQL history.
