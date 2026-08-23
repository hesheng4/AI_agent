# Default stance and source hierarchy

Use this skill to make a Methods section reproducible and compliant: complete enough that an
independent lab could repeat the work, and carrying the rigor elements and ethics
declarations that Nature-family journals require.

The governing policy layer is the Nature Portfolio reporting standards and the Reporting
Summary. The implementation layer is established reproducible-methods practice (full material
identifiers, exact parameters, defined controls and replicates, named software versions) plus
the discipline reporting guidelines (CONSORT, STROBE, ARRIVE, MIQE, and similar).

## The reproducibility test

The single test for every Methods sentence: could a competent independent lab reproduce this
step from what is written? If a reader would have to guess a concentration, a model number, a
parameter, a control, or a software version, the step is not yet reproducible. Concretely, a
complete Methods section lets a reader determine:

- what materials and reagents were used, identified well enough to obtain the same ones
  (supplier, catalogue number, RRID, clone, organism strain, cell line and authentication);
- what equipment and instruments were used, with models and key settings;
- the exact procedure and parameters, in execution order;
- the controls, the replicates (biological vs technical), and the sample-size rationale;
- how data were processed and analysed, with named software and versions;
- that the work meets ethical norms, with the approvals and consent stated.

## Default stance

- Treat the Methods as a reproducibility record, not a narrative. Completeness and precision
  beat readability flourishes here.
- Never invent a protocol fact. Catalogue numbers, RRIDs, instrument models, versions,
  parameter values, approval bodies, and protocol numbers come from the author; flag each
  missing one rather than filling it.
- Replace vague phrasing with specific, reproducible detail. "Standard conditions", "routine
  methods", and "data were analysed statistically" are reproducibility failures, not style
  choices.
- State rigor elements explicitly: randomisation, blinding, inclusion/exclusion criteria, and
  how sample size was determined — or state plainly that an element was not applicable, with
  the reason.
- Carry the required ethics/approval/consent statements for human, animal, and biosafety
  work; never assert an approval the author has not confirmed.
- Keep boundaries clean: defer statistical-test choice and p-value reporting to
  `nature-stats`, and the data-availability statement to `nature-data`. This skill keeps the
  experimental record complete and points to those skills.
- Plan the main-text vs Supplementary split deliberately: enough in the main Methods to follow
  the work, full protocol depth in Supplementary/Reporting Summary where the journal expects
  it.

## Source hierarchy

Use sources in this order:

1. Target journal Methods instructions, Reporting Summary, and the relevant discipline
   reporting standard (CONSORT, STROBE, ARRIVE, MIQE, etc.).
2. Nature Portfolio reporting standards and research-integrity/ethics policies.
3. Established reproducible-methods practice (material identifiers, RRIDs, versions, controls,
   replicates).
4. Field-specific protocol conventions.

If a reporting-standard or ethics-policy detail may have changed, verify the current journal
page before final submission advice.
