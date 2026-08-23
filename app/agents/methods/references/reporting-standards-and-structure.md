# Study-type reporting standards and main-text/Supplementary structure

Open this when you need the discipline-specific reporting standard, or the plan for what goes
in the main Methods versus the Supplementary Information / Reporting Summary.

## Reporting standards by study type

Match the study to its community reporting standard and report the items that standard
requires. These are what reviewers in each field check against. Confirm the current version on
the EQUATOR Network or the standard's own site.

| Study type | Standard | Core demand |
|---|---|---|
| Randomised controlled trial | CONSORT | flow diagram, allocation, blinding, primary/secondary outcomes, registration |
| Observational (cohort/case-control/cross-sectional) | STROBE | design, setting, participants, variables, bias, confounders |
| Animal in vivo research | ARRIVE 2.0 | species/strain/sex/age, housing, sample size, randomisation, blinding, outcomes |
| Diagnostic accuracy | STARD | reference standard, participant flow, test methods |
| Systematic review / meta-analysis | PRISMA | search strategy, inclusion, flow diagram, synthesis |
| qPCR experiments | MIQE | assay design, validation, efficiency, controls |
| Prediction model | TRIPOD | predictors, outcome, model building, validation |
| Prognostic/biomarker | REMARK | marker, assay, study population, analysis |

For a clinical trial, the registration (registry name + number) and the CONSORT flow diagram
are frequently required at submission, not optional.

## Nature Portfolio Reporting Summary

Most Nature-family research papers require a completed Reporting Summary. Its statistics
section is covered by `nature-stats`; its materials/rigor sections overlap directly with this
skill's checklist (antibodies, cell lines, animals, human participants, randomisation,
blinding, replication). Treat the Reporting Summary as the authoritative list of what the
journal will ask — if an item is on it, the Methods or Summary must answer it.

## Main text vs Supplementary split

The main Methods should let a reader follow the work and judge its validity; exhaustive
protocol depth belongs in Supplementary Methods or the Reporting Summary. A workable split:

**Main Methods — include:**
- the experimental design and the key procedures a reader needs to understand the results
- the critical reagents, models, and instruments (with identifiers, or a pointer to a
  Supplementary table of them)
- controls, replicate definitions, and the rigor elements (randomisation, blinding,
  exclusion, sample-size rationale)
- the ethics/approval/consent statements (these stay in the main text)
- a pointer to the statistics description and the data/code availability statement

**Supplementary Methods / Reporting Summary — route here:**
- step-by-step protocols and exhaustive parameter tables
- full reagent/antibody/oligo tables with catalogue numbers and RRIDs
- detailed instrument settings and acquisition parameters
- extended computational pipelines, environment specs, and non-default parameters

The principle: nothing required to judge validity should be *only* in the supplement, and
nothing that merely aids exact replication needs to crowd the main text. Keep identifiers
discoverable (a Reporting Summary or a Supplementary "Key Resources"-style table is the
standard home).

## Key Resources table

Many journals accept or encourage a structured key-resources table listing every reagent,
antibody, cell line, organism, software, and dataset with its source and identifier (RRID,
catalogue, version). When the work uses many reagents, recommend this table — it is the
cleanest way to make identifiers complete without bloating the prose, and it maps directly
onto the reproducibility checklist.
