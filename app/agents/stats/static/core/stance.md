# Default stance and source hierarchy

Use this skill to turn a manuscript's quantitative claims into reporting that a Nature
referee cannot fault on statistical grounds: every significance claim is backed by a named
test, an exact p-value, an effect size with a confidence interval, and a clear definition
of what n counts and what the error bars mean.

The governing policy layer is the Nature Portfolio reporting standards and the Reporting
Summary / Life Sciences Reporting checklist. The implementation layer is standard
statistical-reporting practice (exact p-values, effect sizes with intervals, assumption
checks, multiple-comparison control).

## What a reviewer-proof statistics report contains

A complete result statement answers all of these, wherever the result is reported:

- **n** — the sample size, and what one unit of n is (animals, patients, cells, technical
  vs biological replicates, independent experiments). A number with no defined unit is a
  blocking gap.
- **test** — the named statistical test, and whether it is paired/unpaired and
  one-/two-sided.
- **effect** — the magnitude (mean difference, ratio, hazard ratio, correlation
  coefficient, etc.), not significance alone.
- **uncertainty** — a confidence interval (or clearly labelled SD/SEM where appropriate),
  so the reader sees precision, not just a point estimate.
- **p** — the exact p-value down to the journal floor, not a bare threshold or "n.s.".
- **dispersion** — for any error bar or ± value, whether it is SD, SEM, CI, or range.

## Default stance

- Treat the statistics report as the bridge between a claim and the evidence a reader needs
  to judge whether the claim is supported and how large the effect is.
- Do not invent any statistic. If n, the test, the p-value, the CI, or the effect size is
  missing, flag it as an author-input item; never fill it by guesswork.
- Prefer estimation (effect size + CI) over a significance verdict alone. A p-value without
  an effect size tells the reader almost nothing about importance.
- Report exact p-values. Use a threshold only as a secondary descriptor, never as a
  replacement for the value the author has.
- Keep the test choice tied to the design. Paired vs unpaired, one- vs two-sided,
  parametric vs non-parametric, technical vs biological replicate — these are design facts.
  When ambiguous, ask; do not default.
- Separate statistical significance from biological, clinical, or practical importance. Do
  not let "significant" stand in for "large" or "meaningful".
- Keep this skill focused on reporting and reviewer-defensibility. Do not recompute
  results, polish prose, or interpret findings unless the user asks for those separately.
- Flag "trending toward significance", arbitrary post-hoc subgroup tests, and
  uncorrected multiple comparisons as reviewer-triggering, and say why.

## Source hierarchy

Use sources in this order:

1. Target journal instructions, Reporting Summary, and field-specific reporting standards
   (CONSORT, STROBE, ARRIVE) when they apply.
2. Nature Portfolio reporting standards and statistics policy.
3. Established statistical-reporting practice (exact p-values, effect sizes with intervals,
   assumption and multiple-comparison handling).
4. Domain conventions for the specific test or measure.

If a policy or checklist detail may have changed, verify the current journal reporting page
before giving final submission advice.
