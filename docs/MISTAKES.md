# Mistake Detective: rule catalogue

Each rule names a misconception. A diagnosis is reported only when applying the rule to the
previous step reproduces the student's step exactly (see [ARCHITECTURE.md](ARCHITECTURE.md)).
Every row has a regression test in `tests/test_mistakes.py`, and `tests/test_docs.py` checks that
every registered rule id appears here.

| Rule id | Category | Example of the mistake | What Pi Core says is correct |
|---|---|---|---|
| `algebra.square_of_sum` | Algebra · incorrect expansion | (x+3)² → x² + 9 | x² + 6x + 9 |
| `algebra.partial_distribution` | Algebra · incorrect distribution | 2(x+3) → 2x + 3 | 2x + 6 |
| `algebra.sign_distribution` | Algebra · sign error | −(x−4) → −x − 4 ;  5 − (x+2) → 5 − x + 2 | 4 − x ;  3 − x |
| `algebra.invalid_cancellation` | Algebra · invalid cancellation | (x+6)/x → 6 ;  (2x+4)/2 → x + 4 | 1 + 6/x ;  x + 2 |
| `algebra.fraction_addition` | Algebra · fractions | 1/x + 1/y → 2/(x+y) | (x + y)/(xy) |
| `algebra.exponent_rules` | Algebra · exponent rules | x²·x³ → x⁶ ;  (x²)³ → x⁵ ;  x⁻² → −x² ;  (2x)³ → 2x³ ;  e^(a+b) → eᵃ + eᵇ | x⁵ ; x⁶ ; 1/x² ; 8x³ ; eᵃ·eᵇ |
| `algebra.function_not_linear` | Algebra · function rules | sin(2x) → 2 sin x ;  √(x²+9) → x + 3 | 2 sin x cos x ; (no simplification) |
| `algebra.log_rules` | Algebra · logarithm rules | ln(xy) → ln x · ln y ;  ln(x³) → (ln x)³ | ln x + ln y ;  3 ln x |
| `calculus.derivative` | Calculus · power / product / quotient / chain rule, trig derivatives, exponentials | d/dx x³ → 3x³ ;  d/dx x²sin x → 2x cos x ;  d/dx sin 3x → cos 3x ;  d/dx cos x → sin x ;  d/dx 2ˣ → x·2ˣ⁻¹ | 3x² ;  x²cos x + 2x sin x ;  3cos 3x ;  −sin x ;  2ˣ ln 2 |
| `trig.degrees_radians` | Trigonometry · degrees vs radians | sin(30) → 1/2 | sin(30) ≈ −0.988 in radians |
| `equations.sign_error_moving_term` | Equations · sign error | x + 5 = 12 → x = 12 + 5 | x = 7 |
| `equations.one_side_only` | Equations · unbalanced operation | 3x + 4 = 2x + 9 → x + 4 = 9 + 2x | x + 4 = 9 |
| `algebra.dropped_term` | Algebra · dropped term | x² + 3x + 2 → x² + 2 | (nothing removed) |
| `equations.division_by_expression` | Equations · missed roots | x² = 3x → x = 3 | x(x − 3) = 0, so x = 0 or x = 3 |
| `equations.sqrt_with_variable` | Equations · incorrect rearrangement | x² = 5x − 6 → x = 5 ± √6 | x² − 5x + 6 = 0 → (x − 2)(x − 3) = 0 |
| `equations.positive_root_only` | Equations · missed roots | x² = 4 → x = 2 ;  (x−1)² = 9 → x − 1 = 3 | x = ±2 ;  x = −2 or x = 4 |
| `equations.squaring` *(warning)* | Equations · extraneous roots | √x = x − 2 → x = (x − 2)² | keep only x = 4 (x = 1 fails the original) |
| `algebra.incorrect_factorisation` | Algebra · incorrect factorisation | x² − 5x + 6 → (x − 2)(x + 3) | (x − 2)(x − 3), with the wrong coefficients named |
| `algebra.incorrect_expansion` | Algebra · incorrect expansion | (x+2)(x+3) → x² + 5x + 5 | x² + 5x + 6, with the wrong coefficient named |

Labelled steps add checks of their own:
- `[d/dx]` sends any wrong derivative through the calculus rules above.
- `[integrate]` reports a missing constant of integration.

When no rule reproduces a wrong step, Pi Core still shows *that* it is wrong, with a
counterexample or the lost and gained solutions, but it does not guess *why*.
