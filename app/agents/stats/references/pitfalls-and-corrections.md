# Multiple comparisons, corrections, and reviewer-triggering pitfalls

Open this when you need multiple-comparison correction, pre-registration logic, or a list
of the statistical mistakes that most reliably trigger reviewer objections.

## Multiple comparisons

Every additional test against the same data inflates the chance of a false positive. A
family of 20 independent tests at α = 0.05 expects one "significant" result by chance alone.
Reviewers check for this whenever they see many panels, subgroups, timepoints, or
genes/features.

Correction strategies, by situation:

- **Few pre-planned comparisons** — Bonferroni (simple, conservative) or Holm (uniformly
  more powerful than Bonferroni, same assumptions).
- **ANOVA followed by pairwise comparisons** — a matched post-hoc test (Tukey HSD for
  all-pairs, Dunnett for vs-control, Sidak), not a series of unprotected t-tests.
- **Many tests, false-discovery framing (omics, screens)** — Benjamini–Hochberg FDR; report
  q-values / adjusted p-values and state the FDR threshold.

State which correction was applied and to which family. "Corrected for multiple
comparisons" with no method named is not enough.

## Pre-specification vs exploratory

- A hypothesis fixed before seeing the data is confirmatory; a comparison chosen after
  inspecting the data is exploratory and should be labelled as such.
- Subgroup findings discovered post hoc are hypothesis-generating, not confirmatory; present
  them that way rather than as primary results.
- If the study was pre-registered, cite the registration and flag any deviation from the
  planned analysis. If it was not, do not imply that it was.

## The pitfalls reviewers flag most

- **Bare threshold instead of exact p** — `P < 0.05` when the value is available.
- **Undefined error bars** — `±` with no statement of s.d./s.e.m./CI.
- **Undefined or inflated n** — no unit, or technical replicates / pseudoreplication
  counted as independent n.
- **Significance without effect size** — "significantly higher" with no magnitude or CI.
- **"Trending toward significance"** — there is no such state; report the exact p and the
  effect, and let the reader judge.
- **Uncorrected multiple comparisons** — many tests, no correction named.
- **HARKing** — presenting a post-hoc subgroup result as if it were the pre-planned primary
  analysis.
- **One-sided test to rescue a result** — switching sidedness after a non-significant
  two-sided test.
- **Significance read as importance** — treating a small but significant effect as
  biologically or clinically meaningful.
- **n = 3 doing heavy lifting** — strong general claims from minimal replication, with no
  acknowledgement of the limited power.
- **Wrong dispersion choice** — s.e.m. error bars used to make variable data look tight.
- **Mismatched test** — parametric test on skewed/ordinal data, or independent test on
  paired data.

Each of these is worth surfacing in an audit with a one-line "why it matters", because the
author can usually fix it by supplying a number or renaming the analysis honestly, not by
re-running the experiment.
