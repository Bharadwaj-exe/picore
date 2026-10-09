# Mistake Detective: rule catalogue

The Mistake Detective names a misconception only when a rule **reproduces** the student's step.
How that works is described in [ARCHITECTURE.md](ARCHITECTURE.md#the-mistake-detective), and how
well it works is measured in [EVALUATION.md](EVALUATION.md).

Every rule implements `detect(previous_step, student_step) → Diagnosis | None`. Rules are tried in
this order, and the first match wins:
1. specific misconceptions
2. calculus
3. equation rules
4. descriptive checks

Rules only run on steps that have already been judged **invalid**, so a rule can never turn a
correct step into a mistake. Each rule is covered by `tests/test_mistakes.py` and the benchmark
corpus. `tests/test_docs.py` fails if a registered rule is missing from this page.

There are two kinds of diagnosis:
- **Misconception** names *why* the step is wrong: re-applying a known wrong rule reproduced the step.
- **Descriptive** states *what* is wrong (which coefficient, which part of the domain) without
  claiming a cause.

Detection strategies:
- **Rewrite**: apply the wrong rule at every place in the previous step's syntax tree where it
  fits, then compare each result with the student's step. Expressions are compared by value;
  equations by proportional residuals or by solution set.
- **Residual**: compare the residual (left − right) of the previous equation, altered the way the
  misconception would alter it, with the student's residual.
- **Mal-differentiator**: run the AST differentiator with one wrong rule at one node, for every
  node where it fits.

## Algebra

| Rule id | Misconception | Example (previous → student) | Strategy | Limitations |
|---|---|---|---|---|
| `algebra.square_of_sum` | (a + b)ⁿ = aⁿ + bⁿ | (x+3)² → x² + 9 | rewrite every integer power 2–6 of a sum | sums inside sums are expanded one level only |
| `algebra.partial_distribution` | k(a + b) = ka + b | 2(x+3) → 2x + 3 | rewrite: multiply only one term | one missed term at a time |
| `algebra.sign_distribution` | −(a + b) = −a + b | 5 − (x+2) → 5 − x + 2 | rewrite: flip only the first sign | only the first term's sign is modelled |
| `algebra.invalid_cancellation` | cancelling a term instead of a factor | (x+6)/x → 6;  (2x+4)/2 → x + 4 | rewrite: cancel one term / divide one term | numerators that are sums at the top level only |
| `algebra.fraction_addition` | a/b + c/d = (a+c)/(b+d);  k/(a+b) = k/a + k/b | 1/x + 1/y → 2/(x+y);  1/(x+y) → 1/x + 1/y | rewrite | two fractions, or one denominator sum |
| `algebra.exponent_rules` | xᵃxᵇ = xᵃᵇ, (xᵃ)ᵇ = xᵃ⁺ᵇ, xᵃ/xᵇ = x^(a/b), x⁻ⁿ = −xⁿ, (ab)ⁿ = abⁿ, x^(a+b) = xᵃ + xᵇ | (x²)³ → x⁵ | rewrite (6 variants) | same base must be written identically |
| `algebra.function_not_linear` | f(a + b) = f(a) + f(b), f(ka) = k·f(a), f(a/k) = f(a)/k for sin, cos, tan, √, ln, exp | sin(2x) → 2 sin x;  √(16+9y²) → 4 + 3y | rewrite; for √ also the student's "√(9y²) = 3y" | only one function application changed |
| `algebra.log_rules` | ln(ab) = ln a·ln b, ln(a/b) = ln a/ln b, ln(aⁿ) = (ln a)ⁿ, ln a + ln b = ln(a+b) | ln(x³) → (ln x)³ | rewrite | natural log and `log` |
| `algebra.log_base` | reading `log` as base 10 (Pi Core: log = ln) | log(1000x) → 3 + log x | re-read BOTH steps with log = log10; the step must then be valid | only when the whole step becomes valid in base 10 |
| `algebra.dropped_term` *(descriptive)* | a term vanished | x² + 3x + 2 → x² + 2 | previous − term = student | expressions only (equations: `one_side_only`) |
| `algebra.incorrect_factorisation` *(descriptive)* | factors that don't multiply back | x² − 5x + 6 → (x−2)(x+3) | expand the student's product and compare coefficients | polynomials only |
| `algebra.incorrect_expansion` *(descriptive)* | a wrong coefficient after expanding | (x+2)(x+3) → x² + 5x + 5 | compare coefficients term by term | polynomials only |

## Equations

| Rule id | Misconception | Example | Strategy | Limitations |
|---|---|---|---|---|
| `equations.sign_error_moving_term` | moving a term across '=' without changing its sign | x + 5 = 12 → x = 12 + 5 | residual: off by 2·term, for each term **as written** and as expanded | one term at a time |
| `equations.one_side_only` | adding, subtracting or dividing on one side only | 3y + 8 = 20 → 3y = 20;  4(p−1) = 2p+6 → p − 1 = 2p + 6 | residual: off by one term, or one side divided by its constant factor | constant factors only |
| `equations.division_by_expression` | dividing by something that can be zero | x² = 3x → x = 3;  sin x cos x = sin x → cos x = 1 | the divisor must be a common factor of both sides **and** its zeros must be the lost solutions (exact, or found numerically for trig) | numerical branch only searches [−20, 20] |
| `equations.positive_root_only` | keeping only the + square root | x² = 4 → x = 2;  x² = x + 6 → x = √(x+6) | an even power in the previous step, roots lost and none gained | finite solution sets only |
| `equations.sqrt_with_variable` | "square-rooting" while x is still on the other side, giving wrong values | x² = 5x − 6 → x = 5 ± √6 | polynomial equation; the student's values are not solutions | stays silent if the values happen to be solutions |
| `equations.squaring` *(warning)* | squaring both sides adds extraneous roots | √x = x − 2 → x = (x − 2)²;  sin x = cos x → sin²x = cos²x | the student's residual is (left² − right²), or a √ was removed; roots gained, none lost | a warning, because squaring is legitimate if answers are checked afterwards |

## Calculus

`calculus.derivative` is the registry entry. The diagnosis it reports carries a specific id:

| Diagnosis id | Misconception | Example | Strategy |
|---|---|---|---|
| `calculus.power_no_reduce` | d/dx xⁿ = n·xⁿ | d/dx x⁵ → 5x⁵ | mal-differentiator |
| `calculus.power_no_coeff` | d/dx xⁿ = xⁿ⁻¹ | d/dx x⁵ → x⁴ | mal-differentiator |
| `calculus.coefficient_dropped` | d/dx (k·f) = f′ | 4t³ → [d/dt] 3t² | mal-differentiator |
| `calculus.product_naive` | (uv)′ = u′v′ | d/dx x² sin x → 2x cos x | mal-differentiator |
| `calculus.quotient_naive`, `calculus.quotient_sign`, `calculus.quotient_order` | (u/v)′ = u′/v′, sign or order wrong | d/dx sin x / x → cos x | mal-differentiator |
| `calculus.chain_missing` | f(g(x))′ = f′(g(x)) | d/dx sin 3x → cos 3x | mal-differentiator |
| `calculus.trig_sign` | d/dx cos x = sin x | d/dx cos x → sin x | mal-differentiator |
| `calculus.exp_as_power` | d/dx aˣ = x·aˣ⁻¹ | d/dx 2ˣ → x·2ˣ⁻¹ | mal-differentiator |
| `calculus.wrong_variable` | differentiating with respect to the wrong letter | d/dx t³ → 3t² | compare with d/d(other letter) |
| `calculus.antiderivative_domain` *(warning, descriptive)* | an antiderivative valid on only part of the domain | 1/x → [integrate] ln x + C | domain of F ⊉ domain of f |

One mistake per derivative is modelled. A combination of two slips is reported as "wrong" with
evidence, but no cause is named. `[integrate]` also reports a missing `+ C`.

## Trigonometry and domains

| Rule id | Misconception | Example | Strategy | Limitations |
|---|---|---|---|---|
| `trig.degrees_radians` | using degrees (Pi Core uses radians) | sin(30) → 1/2;  sin x + 1 → [sub x=30] 3/2 | re-evaluate numeric angles as degrees and compare | numeric angles only |
| `domain.lost_domain` *(descriptive)* | a rewrite whose result is undefined where the original was defined | ln(x²) → 2 ln x;  x → (√x)² | the equivalence engine reports that the student's side is undefined somewhere the previous side is defined | multi-variable cases need a witness point |

Trig identities used incorrectly, such as sin(2x) → 2 sin x, are handled by `algebra.function_not_linear`.

## When no rule matches

Pi Core still reports that the step is wrong, with concrete evidence:
- a counterexample point (exact for constants, at 60 digits)
- lost or gained solutions (exact)
- or solutions found numerically

It does not guess why. Answers that are correct roundings (`x = cos x → x = 0.739`) are reported as
"couldn't check", not as mistakes.
