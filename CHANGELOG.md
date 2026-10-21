# Changelog

## 0.5.0: hardening, validation and release

This release adds no headline feature. It makes the existing ones defensible.

**Mistake Detective**
- Evaluation benchmark: 230 labelled single steps covering algebra, equations, calculus, trig and
  domains (`tests/data/detective_corpus.json`, `tools/evaluate_detective.py`, `docs/EVALUATION.md`).
  The test suite enforces zero false positives on correct work, zero misattributed or invented
  diagnoses, and recall ≥ 97%. Current results: 0/107 false positives, 115/117 recall, 87/87
  misconceptions named exactly.
- Fixed false positives on correct work. Steps such as `2sin x = 1 → sin x = 1/2` and
  `e^x = x + 2 → x = ln(x + 2)` were flagged because SymPy returned unevaluated solution sets.
- Fixed false acceptances:
  - `(x²−1)/(x−1) = 2 → x + 1 = 2`: proportional residuals that ignore an excluded point
  - `ln(x²) → 2ln x`: a rewrite that loses part of the domain
- New verdict: "numerically supported", for steps that agree at test points but are not proved.
- Rounded answers (`x = cos x → x = 0.739`) are reported as "couldn't check", not as mistakes.
- New rules:
  - `log` read as base 10
  - a constant factor dropped in a derivative
  - differentiating with respect to the wrong variable
  - a fraction split over its denominator
  - one side divided by a constant
  - the domain lost by a rewrite
  - an antiderivative valid on only part of the domain
- Rule fixes:
  - The square-root rule no longer makes a false claim, and only fires on polynomial equations.
  - Rules that raise an error no longer crash a check; the error is logged instead.

**Mathematics**
- Periodic equations give every real solution as a family, e.g. x = 2πn + π/6.
- Identities say every value is a solution.
- Inconsistent polynomial systems are proved to have no solutions.
- Undefined values (`1/0`, `ln 0`, `(−3)!`) are reported as undefined. Divergent integrals are
  reported as not converging.
- New shared real-root finder. Sign changes are refined by bisection, poles are rejected, and
  roots without a sign change (such as `e^x = x + 1` at 0) are found. It never claims to be complete.
- Constants are compared at 60 digits, so `e^(π√163)` is no longer treated as equal to
  `640320³ + 744`. Numerical sampling uses real values only.
- `d/dx` treats the variable as real: `d/dx |x| = sign x`, instead of a 16-second complex-analysis
  result.

**Robustness and security**
- Size limits stop inputs that used to run for minutes:
  - integer powers of symbolic expressions: at most 200
  - a whole query: at most 2000 characters
  - a `check` chain: at most 12 steps
- Only input that looks like a word question is sent to Wolfram|Alpha. Malformed maths is
  explained locally.
- Wolfram responses are validated for structure and size.
- A damaged history database is moved aside instead of crashing the app at startup.
- Config values are type-checked.
- Rotating log file (`picore.log`) records internal errors with tracebacks.
- Property tests: random syntax trees print and re-parse identically, and node spans nest. These
  found and fixed two printer bugs.

**Architecture**
- The printing and text-parsing helpers moved into `picore/lang`. Lower layers no longer import
  from the engine layer.
- The checker exposes `judge_step()` with rule ids for the benchmark.

**Repository**
- `.coverage` is no longer tracked.
- The background music (licence unknown) is no longer in the repository; the app runs silently
  without it.
- Tests: 340, line coverage 87%.

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
