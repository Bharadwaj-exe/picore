# Pi Core: portfolio notes

## Summary

Pi Core is an offline desktop environment for school and first-year university maths, written in
Python with Pygame and SymPy. It parses maths with its own lexer and recursive-descent parser into
an AST that keeps source positions and domain information. On top of that it computes results and
verifies them symbolically, or labels them as numerical evidence. It decides whether two
expressions are equivalent, including where they are defined. Its Mistake Detective explains wrong
steps in someone's working by reproducing them with a catalogue of known misconceptions, and it
never accuses a correct step on a guess.

## Key engineering achievements

- **Language front end:**
  - a hand-written lexer and recursive-descent parser with a documented EBNF grammar
  - explicit conventions for ambiguous notation (`-2^2`, `1/2x`, `sin x^2`)
  - source spans on every node, and errors that point at the exact character
- **Domain analysis from the AST, before SymPy simplifies.** SymPy rewrites `x/x` to `1` and
  forgets that x = 0 is excluded. Pi Core reads denominators, logs, roots and tan/cot poles from the
  tree, so it can say that `(x²−1)/(x−1) = x + 1` holds only for x ≠ 1. It can also say that
  `ln(x²) → 2 ln x` is invalid, because the result loses all of x < 0.
- **Equivalence engine with five verdicts** (exact, conditional, numeric-only, not, unknown).
  - A numerical counterexample proves non-equivalence and is tried first.
  - Numerical agreement is only ever "evidence".
  - Constants are compared at 60 digits.
- **Mistake Detective built on mal-rules.** About 20 registered rules: rewrites applied to the
  previous step's tree, residual comparisons for equations, and an AST differentiator that applies
  one wrong rule at one node.
- **Measured evaluation.**
  - A 230-case labelled corpus, scored by a script; the test suite enforces the results.
  - 0 of 107 correct steps flagged; 115 of 117 wrong steps flagged; 87 of 87 expected
    misconceptions named; 0 misattributions.
- **Honest numerics.**
  - A real-root finder that also finds roots without a sign change and rejects poles.
  - Periodic equations are solved as families.
  - "No solutions" is only said when it is proved.
- **Engineering:**
  - a background worker where the latest job wins and failures become results
  - a SQLite history that survives a corrupt file
  - type-checked configuration, a rotating error log
  - a PyInstaller build with a self-test of the frozen executable, and an Inno Setup installer
  - CI on Windows and Linux

## Architecture (short)

`lang` (lexer → parser → AST → SymPy backend, domain analysis) → `reasoning` (equivalence, numeric
verification, mal-rules, derivations) → `engine` (command routing, result cards, optional Wolfram
fallback) → `scenes`/`ui` (Pygame). Only the UI layer imports Pygame, so everything else is tested
directly. Details and diagrams: [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing

- 340 automated tests, 87% line coverage (pytest + pytest-cov), run on Windows and Linux in CI.
- They cover:
  - parser conventions and error positions
  - property tests: random syntax trees print and re-parse identically, and spans nest
  - a 3000-input fuzz test
  - a mathematical regression suite
  - pathological and code-injection input with time bounds
  - the Mistake Detective benchmark
  - headless tests that drive every screen with real keyboard and mouse events
  - worker concurrency
  - a damaged history database
  - malformed Wolfram responses (against a local fake server)

## Benchmark results

Measured on the development laptop (Windows 11, Python 3.11, SymPy 1.14); medians.

| Operation | Time |
|---|---|
| Parse `2x^2 + 3x + 1` | 0.1 ms |
| Parse a 280-character expression | 1.7 ms |
| Equivalence `(x^2-1)/(x-1)` vs `x+1` | 30 ms |
| Equivalence `ln(x^2)` vs `2ln(x)` | 73 ms |
| Mistake Detective, 3-step chain | 83 ms |
| Mistake Detective, product-rule slip | 56 ms |
| Solve `x^2 - 5x + 6 = 0` with verification | 11 ms |
| Numerical roots of `sin(x) = x/2` | 1.35 s |
| Mistake Detective benchmark, per step (median / p95 / max) | 30 ms / 385 ms / 2.5 s |
| App start from source (dominated by importing SymPy, ~1.5 s) | ~5 s |
| Frozen `.exe`: cold start plus full self-test | ~3.4 s |
| `.exe` folder size | ~85 MB |

## Known limitations

- **Corpus:** the benchmark corpus is small, written for this project, and labelled under Pi Core's
  conventions. It is a regression benchmark, not evidence about real students.
- **One misconception per step:** two slips in one step are reported as wrong, with evidence, but
  no cause is named.
- **Multi-variable equations** are only checked for rearrangement and scaling.
- **Numerical root search** covers [−20, 20] with a 0.01 grid. It can miss very close roots, and
  says it is not exhaustive.
- **Runaway computations:** Python threads cannot be stopped. A computation past the 25 s timeout
  is abandoned but keeps using CPU. Input size limits make this rare.
- **No `∫` notation inside `check` steps.** The `[integrate]` label covers it.
- **Desktop only:** Pygame does not target mobile or the web.

## Future work

- Run computations in a separate process, so a timed-out job can actually be stopped.
- Grow the evaluation corpus with real anonymised student working, if a teacher can supply it.
- Diagnose two misconceptions in one step (a search over pairs of mal-rules, with a cost bound).
- `∫` syntax in the grammar, so integration steps can be checked like derivatives.

## Technical interview questions

**Why recursive descent?** The grammar is small and has clear precedence levels. One method per
rule makes precedence and associativity explicit, gives good error positions, and needs no parser
generator. Right-associativity of `^` comes from recursing into `unary` for the exponent.

**What grammar does it implement?** EBNF in [GRAMMAR.md](GRAMMAR.md): `statement → side ['=' side]`,
then `expr` (+, −, ±), `term` (*, /, implicit multiplication), `unary`, `power`, `postfix` (!), and
`primary` (numbers, names, calls, parentheses, √, d/dx).

**How does precedence work?** Each level is a function that calls the next tighter level. So
`term` is built out of `unary`/`power`, and `2 + 3·4` becomes `+(2, ·(3, 4))`. Implicit
multiplication has the same precedence as `·`, which is why `1/2x` = (1/2)·x.

**Why an AST?** It keeps the structure as written (`2(x+3)` stays a product), source spans for
highlighting and errors, and domain information. All of these are lost once SymPy evaluates.

**Why can't SymPy's simplified expression be trusted for mistake detection?** SymPy normalises on
construction. `2(x+3)` becomes `2x + 6`, so you can't see whether the student distributed, and
`x/x` becomes `1`, so you lose the excluded point.

**How does domain analysis work?** It walks the AST and collects conditions: denominators ≠ 0,
negative powers, log arguments > 0, square-root arguments ≥ 0, cos ≠ 0 for tan. A derivative's
conditions are taken from the derivative itself. For one variable the conditions become sets with
`solveset`; for several variables a domain difference needs a concrete witness point.

**What is a mal-rule?** A wrong rule that students apply, such as `(a+b)² → a² + b²`, written as
a transformation. The idea comes from intelligent tutoring systems research.

**How does the detector avoid guessing?** Rules only run on steps already shown to be invalid, so
they can't turn a correct step into a mistake. A rule names a cause only if applying it to the
previous step reproduces the student's step (by value, proportional residual or solution set).
Otherwise only the evidence is shown. The benchmark enforces zero invented diagnoses.

**How does equivalence differ from numerical equality?** Equivalence needs a symbolic proof that
the difference simplifies to 0, plus a comparison of domains. Numerical equality at sample points
is reported as "numerically supported" only. A numerical *counterexample* at a point where both
sides are defined does prove non-equivalence.

**Why is numerical verification not proof?** Finitely many points can't establish an identity.
For example, `e^(π√163)` and `640320³ + 744` agree to about 30 digits but are not equal.

**How are timeouts handled?** The UI submits work to a background thread and polls each frame.
After 25 s the job is cancelled from the UI's point of view: its result will be dropped. The thread
itself can't be killed in Python, which is why input size limits exist.

**How does the worker prevent stale results?** Each submission gets an increasing id, recorded as
the latest for its kind. `poll()` only delivers a finished job if its id is still the latest, so
older answers are dropped.

**Why SQLite?** It's embedded, needs no server, uses one file in the user's data folder, and is
transactional. The original version needed a local MySQL server with a root password.

**Why offline-first?** Maths shouldn't depend on a network or an API quota. Wolfram|Alpha is only
used for word questions, and only if configured.

**How is the API key protected?**
- It is never in the source or the git history (both were checked).
- The build script fails if the config file would be bundled into the `.exe`.
- For public builds, a small Cloudflare Worker proxy holds the key, caches answers and rate-limits
  each IP.

**What happens when SymPy can't solve an equation?**
- Polynomials get numerical roots, with an Abel–Ruffini explanation.
- Other equations are scanned for real roots, clearly labelled as numerical and possibly
  incomplete.
- Periodic equations are solved as families.
- "No solutions" appears only when SymPy proves the solution set is empty.
