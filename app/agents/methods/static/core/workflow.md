# Workflow and output format

## Workflow

1. **Identify study type and journal.** Wet-lab/experimental, clinical/human, animal,
   computational, or field study? Which journal? The study type determines which
   reproducibility items and reporting standard (CONSORT, STROBE, ARRIVE, MIQE, …) apply. If
   the journal's Methods instructions or Reporting Summary conflict with this skill, follow the
   journal.

2. **Inventory against the reproducibility checklist.** Go through the methods detail by item
   type — materials/reagents (supplier, catalogue, RRID, clone, lot where relevant), organisms
   (strain, sex, age, source) and cell lines (source, authentication, mycoplasma status),
   equipment (model, key settings), procedures and exact parameters, controls, replicates
   (biological vs technical), and data-processing software with versions. Mark each present,
   incomplete, or missing. See `references/reproducibility-checklist.md`.

3. **Check rigor elements.** Randomisation, blinding, inclusion/exclusion criteria, and how
   sample size was determined. State each explicitly, or state "not applicable" with a reason.
   See `references/ethics-and-rigor.md`.

4. **Check ethics, approval, and consent.** For human, animal, or biosafety work, confirm the
   approving body, protocol/approval number, and consent procedure are stated. Flag any that
   the author has not provided — never assert an approval that is unconfirmed.

5. **Remove forbidden vague phrasing.** Replace "standard conditions", "routine methods",
   "data were analysed statistically", "samples were randomly assigned" (with no method),
   "the method was validated", and similar with the actual reproducible detail or a
   bracketed author-input placeholder.

6. **Plan the main-text vs Supplementary split.** Keep enough in the main Methods to follow
   the work; route exhaustive protocol depth to Supplementary Methods / the Reporting Summary
   where the journal expects it. See `references/reporting-standards-and-structure.md`.

7. **Defer cleanly.** Point statistical-test choice and p-value reporting to `nature-stats`,
   and the data-availability statement to `nature-data`; do not duplicate them.

8. **Return Methods text or audit, plus unresolved fields.** Ready-to-paste Methods text (or
   subsection) with bracketed placeholders for missing facts, then a list of every item the
   author must supply. In audit mode, lead with blocking gaps.

## Forbidden vague phrasing

These are reproducibility failures; never leave them in drafted or revised text. Replace each
with the actual value, or a clearly bracketed placeholder the author must fill:

- "under standard conditions" → the actual temperature, time, buffer, concentration
- "using routine methods" / "as previously described" (without a citation that truly contains
  the detail) → the steps, or the specific citation
- "data were analysed statistically" → the named test (route to nature-stats)
- "differences were significant" → the test and exact p (route to nature-stats)
- "samples were randomly assigned" → the randomisation method
- "the method was validated" → how it was validated, with what controls
- a reagent/antibody/cell line with no supplier, catalogue, RRID, or authentication
- software named with no version

## Output format

Unless the user asks for another format, return:

```text
Methods
[ready-to-paste Methods text or subsection, with bracketed placeholders for any
 fact the author must supply — reagent identifiers, parameters, versions, approval
 numbers]

Reproducibility audit (audit mode) / Reporting decisions (draft mode)
- [blocking gap or decision, most severe first, with the why]

Missing information / author-input needed
- [each reagent identifier, parameter, version, control, replicate definition,
   approval/consent detail the author must supply, or "None"]

Routed elsewhere
- Statistics (tests, p-values, effect sizes) → nature-stats
- Data/code availability statement → nature-data
[omit lines that do not apply]

中文核对
- [用中文列出作者需要确认或补充的方法项，或 "无"]
```

When auditing an existing Methods section, lead with blocking gaps (missing ethics statement,
unidentified reagents/cell lines, missing parameters or versions, vague phrasing, absent rigor
elements), then provide the revised text.
