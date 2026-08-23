# Workflow and output format

## Workflow

1. **Identify journal and report location.** Confirm the target journal/article type and
   where the text will live: figure legend, Results sentence, table footnote, or Methods
   statistics paragraph. The same result is reported at different granularity in each. If
   journal or field standards (CONSORT, STROBE, ARRIVE) conflict with this skill, follow
   the journal.

2. **Inventory every quantitative claim and its test.** List each comparison, correlation,
   or modelled estimate that the text asserts, and the statistical test behind it. A claim
   with no named test is a blocking gap.

3. **Check n and dispersion.** For each claim, confirm the sample size and what one unit of
   n is (biological vs technical replicate, independent experiments, animals, patients,
   cells). For every ± value or error bar, confirm whether it is s.d., s.e.m., CI, or range.
   Undefined n or undefined error bars are blocking.

4. **Verify test choice and assumptions.** Check that the test matches the design: paired
   vs unpaired, one- vs two-sided, parametric vs non-parametric, and that distributional
   assumptions (normality, equal variance) were addressed where the test requires them.
   When the design fact is ambiguous, raise it as a question — do not default.

5. **Check effect size, CI, and exact p.** Confirm the claim reports magnitude (effect
   size) with a confidence interval, not significance alone, and an exact p-value down to
   the journal floor rather than a bare threshold or "n.s.".

6. **Check multiple-comparison handling.** Where many tests, subgroups, or timepoints are
   compared, confirm a correction or pre-specification, and flag uncorrected families and
   post-hoc subgroup tests.

7. **Draft or revise the statement.** Produce ready-to-paste text at the right granularity
   for the report location, using exact numbers the user supplied and explicit placeholders
   for anything missing.

8. **Return text plus unresolved fields.** List every number, design fact, or correction
   the author must supply or confirm. Lead an audit with blocking issues first.

## Output format

Unless the user asks for another format, return:

```text
Statistics report
[ready-to-paste statement(s) at the right granularity — figure legend line,
 Results sentence, Methods statistics paragraph, or table footnote]

Findings (audit mode) / Reporting decisions (draft mode)
- [blocking issue or decision, most severe first, with the why]

Missing information / author-input needed
- [each missing number, design fact, or correction the author must confirm, or "None"]

中文核对
- [用中文列出作者需要确认或补充的统计项，或 "无"]
```

When auditing existing statistics, lead with blocking issues (undefined n, undefined error
bars, missing test, bare threshold instead of exact p, uncorrected multiple comparisons),
then provide the revised statement.

## Worked micro-examples

**Audit — vague Results claim**

Input: "Treatment increased expression significantly (p < 0.05, n = 3)."
Findings:
- Blocking: no named test; reader cannot judge appropriateness.
- Blocking: n = 3 of what — biological or technical replicates? Independent experiments?
- Missing: effect size and CI; "increased" gives no magnitude.
- Reportable p is a bare threshold; supply the exact value.
Revised (pending author input):
"Treatment increased expression 2.4-fold (95% CI 1.6–3.3; two-sided unpaired t-test,
P = 0.018; n = 3 biological replicates)."  ← fold-change and CI are placeholders to confirm.

**Draft — figure-legend line from supplied numbers**

Input: means and a two-sided Mann–Whitney comparison, 8 mice per group, exact p = 0.0032,
bars are s.e.m.
Output:
"Data are mean ± s.e.m.; n = 8 mice per group. Comparison by two-sided Mann–Whitney U test,
P = 0.0032."
