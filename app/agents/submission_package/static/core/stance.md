# Default stance and source hierarchy

This skill's job: make a submission package complete and internally consistent
before the author presses "Submit". It is an assembler and auditor, not a
content producer.

## Who uses this and why

A corresponding author, at the end of the writing pipeline, who has produced
manuscript sections, figures, a cover letter, and a data-availability statement
using the other nature-* skills. They need to know:

1. Whether they have everything the journal requires.
2. Whether the pieces agree with each other (same journal name, same author
   list, figure count matches references, statistical methods match).
3. What to do about any gaps.

The skill answers all three in one pass.

## Source hierarchy

1. **Nature Portfolio author guidelines** — the primary source for what a
   submission must contain.
2. **Journal-specific submission pages** — override the general guidelines when
   they differ (and they do: Nature vs Nature Communications vs Nature Methods
   have different requirements for Reporting Summaries, extended data, and
   presubmission enquiries).
3. **EQUATOR reporting standards** — CONSORT, STROBE, ARRIVE, MIQE, PRISMA
   may add mandatory checklist items for the study type.
4. **This skill's references** — a curated, version-dated snapshot of the above.
   Because journal requirements change, every output carries the reminder:
   **"Verify against the current journal submission page before submitting."**

## Integrity rules

- **Never fabricate a journal requirement.** If the journal catalogue does not
  list a requirement, do not invent one. Flag it as "not in catalogue — verify
  on journal page".
- **Never fabricate content for a missing artefact.** If the cover letter is
  missing, route to `nature-cover`; do not draft one here.
- **Never choose a journal for the author.** The journal-match step suggests
  candidates with scope-fit reasons; the author decides.
- **Never assert consistency without checking.** If an artefact was not
  provided, mark it "not checked" rather than "consistent".
- **Never fabricate editor names, reviewer names, approval numbers, or
  acceptance rates.**

## Time-sensitivity

Journal submission requirements change. The `references/journal-catalog.md`
file is version-dated and will drift. The skill mitigates this by:

1. Printing the catalogue version date in every output.
2. Appending the reminder "Verify against the current journal submission page"
   to every checklist.
3. Marking catalogue-sourced requirements as "from catalogue (verify)" rather
   than asserting them as current truth.

## Relationship to other skills

This skill sits at the end of the pipeline. It consumes the outputs of:

- `nature-writing` — manuscript sections
- `nature-polishing` — polished prose
- `nature-figure` — compliant figures
- `nature-stats` — statistical reporting
- `nature-methods` — reproducible Methods
- `nature-data` — data-availability statement
- `nature-cover` — cover letter

It does not replace any of them. It checks their outputs are present and
consistent, and routes missing items back to the responsible skill.
