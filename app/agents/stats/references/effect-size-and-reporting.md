# Effect size, confidence intervals, p-values, and dispersion

Open this when you need exact-p formatting, effect-size choice, CI reporting, error-bar
meaning, or n / replicate definitions.

## Exact p-values

Nature wants the exact p-value, not a threshold, wherever the author has it.

- Report `P = 0.018`, not `P < 0.05`. A threshold discards information the reader needs to
  weigh the evidence.
- Report very small values down to the journal floor, commonly `P < 0.0001` (some journals
  use `P < 0.001`). Confirm the floor for the target journal.
- Never report "n.s." when an exact value exists; give the value.
- Use an italic capital `P` in Nature house style. Avoid `p=.018` (leading-zero and
  lower-case conventions vary; Nature uses `P = 0.018`).
- A p-value is not an effect size and not a probability that the hypothesis is true. Do not
  let it stand in for magnitude or importance.

## Effect sizes — report magnitude, not just significance

Every significance claim should carry the size of the effect. The right measure depends on
the design:

| Comparison | Effect-size measure |
|---|---|
| Difference between two means | Mean difference (in real units), or Cohen's d for standardised |
| Ratio / fold change | Fold change or ratio with CI |
| Two groups, binary outcome | Risk ratio, odds ratio, or risk difference |
| Time-to-event | Hazard ratio |
| Association, continuous | Pearson r / Spearman ρ (with CI) |
| ANOVA / regression | η² / partial η², or R² and standardised coefficients |

A result reported as only "significant (P = 0.01)" is incomplete: a tiny effect can be
significant with large n, and a large effect can miss significance with small n.

## Confidence intervals

Pair every effect estimate with a confidence interval (conventionally 95%).

- The CI shows precision and the plausible range; it is more informative than a p-value
  alone and is increasingly required.
- Report as "2.4-fold (95% CI 1.6–3.3)" or "difference 5.2 mmHg (95% CI 1.1–9.3)".
- A CI that crosses the null (1 for ratios, 0 for differences) is consistent with the
  threshold-based non-significant verdict; reporting both is transparent.

## Dispersion: say what the bar means

Any `±` value or error bar is ambiguous until labelled. The three are not interchangeable:

- **s.d. (standard deviation)** — spread of the data; describes variability of the sample.
- **s.e.m. (standard error of the mean)** — precision of the mean estimate; always smaller
  than s.d. and shrinks with n, so it can visually understate variability. Do not use s.e.m.
  to make a result look tighter than it is.
- **95% CI** — interval for the parameter; preferred when the point of the bar is inference.

State the choice explicitly in every legend: "data are mean ± s.e.m." or "mean ± s.d." or
"median and IQR". For skewed data, median + IQR is usually more honest than mean ± s.d.

## Defining n and replicates

The single most common reviewer question is "what is n?"

- State the number and the unit: "n = 6 mice", "n = 3 biological replicates", "n = 240
  cells from 4 independent experiments".
- **Biological replicate** — independent biological unit (separate animal, separate
  culture, separate patient); this is what supports a biological generalisation.
- **Technical replicate** — same sample measured repeatedly; characterises measurement
  noise, not biological variation, and must not be counted as n for a biological claim.
- If a result rests on one experiment with technical replicates, say so plainly; do not
  present technical replicates as independent n.
- State whether and how often the experiment was reproduced.
