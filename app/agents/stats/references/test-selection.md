# Test selection and assumptions

Open this when you need to choose or justify a statistical test, check its assumptions, or
resolve parametric vs non-parametric, paired vs unpaired, one- vs two-sided.

The skill does not pick a test for the author when the design is ambiguous. It checks that
the test matches the stated design and flags the design facts the author must confirm. The
guidance below is for that check, not for substituting the author's judgement.

## The three design facts that drive the choice

Before any test name is appropriate, three facts must be settled. Each is the author's
design fact, not a default:

1. **Paired or independent?** Repeated measures on the same unit (before/after, matched
   pairs, same animal across conditions) are paired; separate units are independent.
   Choosing an unpaired test for paired data wastes power and is wrong; the reverse is
   anticonservative.
2. **One- or two-sided?** Two-sided is the default and the safer reporting choice. A
   one-sided test must be justified by a directional hypothesis fixed in advance; using it
   to rescue a marginal result is a classic reviewer flag.
3. **What is the unit of replication?** Technical replicates (same sample measured several
   times) are not independent and must not be treated as n for a biological claim.
   Pseudoreplication — counting cells from one animal as n — inflates significance and is
   one of the most common rejection-grade errors.

## Parametric vs non-parametric

Parametric tests (t-test, ANOVA, Pearson) assume approximate normality and, for several of
them, equal variance. With small n these assumptions cannot be verified reliably, which is
itself worth stating.

- Continuous, roughly normal, adequate n → parametric (t-test / ANOVA).
- Skewed, ordinal, or small-n data where normality is doubtful → non-parametric
  (Mann–Whitney U, Wilcoxon signed-rank, Kruskal–Wallis).
- Report which assumption checks were done (e.g. Shapiro–Wilk, Levene), or state that with
  the available n the test was chosen conservatively.

## Quick routing table

| Design | Common appropriate test |
|---|---|
| Two independent groups, continuous, normal | Two-sided unpaired t-test (Welch's if variances differ) |
| Two paired/matched measurements, normal | Paired t-test |
| Two independent groups, non-normal/ordinal | Mann–Whitney U |
| Two paired measurements, non-normal/ordinal | Wilcoxon signed-rank |
| 3+ independent groups, normal | One-way ANOVA + post hoc correction |
| 3+ independent groups, non-normal | Kruskal–Wallis + corrected post hoc |
| Repeated measures across conditions | Repeated-measures / mixed-effects ANOVA |
| Two categorical variables | Chi-square (large counts) or Fisher's exact (small counts) |
| Association between two continuous variables | Pearson (linear, normal) or Spearman (monotonic/ranked) |
| Time-to-event outcome | Log-rank test; Cox model for adjusted hazard ratios |
| Adjusting for covariates / nested data | Regression / mixed-effects model |

This table is a sanity check, not a substitute for a statistician on a complex design. When
the design involves nesting, repeated measures, or many covariates, recommend modelling
(mixed-effects / regression) and say so rather than forcing a pairwise test.

## Common mismatches to flag

- Many independent t-tests where one ANOVA (with correction) is the correct family.
- A bare t-test on clearly skewed or count data.
- Treating technical replicates as independent n.
- Switching to a one-sided test only after a two-sided result was non-significant.
- Pearson correlation asserted for an obviously non-linear or rank relationship.
