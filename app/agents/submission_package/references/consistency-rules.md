# Cross-artefact consistency rules

Open this when you need the checks that run across submission artefacts —
the checks no single-artefact skill can perform because each looks at only one
piece.

## Consistency checks

Each check compares a field extracted from two or more artefacts. The skill
extracts the field values during the inventory step (workflow step 3) and
compares them here.

### C1: Journal name consistency

| Field | Artefacts to check | Match rule |
|---|---|---|
| Target journal name | Cover letter, Data Availability Statement, manuscript (first page / running header) | Exact string match after normalisation (case-insensitive, strip "The") |

Failure mode: author drafted the cover letter for Nature Methods but the DA
statement says Nature Biotechnology (or vice versa). This is a submission-blocking
error.

### C2: Figure count consistency

| Field | Artefacts to check | Match rule |
|---|---|---|
| Number of figures | Manuscript (in-text "Fig. N" / "Figure N" references), figure file set, Extended Data figure set | Every in-text figure reference must have a corresponding file; every file must be referenced in text |

Failure modes:
- Figure referenced in text but no file provided → ✗ missing figure
- Figure file provided but not referenced in text → ⚠ orphan figure (likely wrong)
- Figure numbering gaps (Fig 1, Fig 2, Fig 4) → ⚠ possible missing figure

### C3: Author list consistency

| Field | Artefacts to check | Match rule |
|---|---|---|
| Author names / order | Manuscript title page, cover letter signature, author contributions, competing interests | Same set of names in the same order after normalisation (initials, diacritics) |

Failure mode: cover letter signed by only the corresponding author while the
manuscript has 6 authors — not an error, but flag if the cover letter
mentions "we" and lists a different author count.

### C4: Statistical methods consistency

| Field | Artefacts to check | Match rule |
|---|---|---|
| Statistical tests / methods | Results (test names, p-values), Methods (statistics paragraph), figure legends (test names) | Every test named in Results or a figure legend must appear in the Methods statistics paragraph |

Failure mode: Results says "two-tailed Mann-Whitney U test" but Methods
statistics paragraph only mentions "t-test". This is a reviewer-flagging error.
Route to `nature-stats` for resolution.

### C5: Data availability consistency

| Field | Artefacts to check | Match rule |
|---|---|---|
| Data types / repositories | Data Availability Statement, manuscript (data references), Supplementary Information | Every dataset mentioned in the manuscript (e.g. "deposited in GEO under GSEXXXXX") must appear in the DA statement; every repository in the DA statement must be referenced in the manuscript |

Failure mode: DA statement says "RNA-seq data deposited in GEO" but no GEO
accession appears in the manuscript. Route to `nature-data` for resolution.

### C6: Ethics statement consistency

| Field | Artefacts to check | Match rule |
|---|---|---|
| Ethics / approval mentions | Methods (ethics paragraph), Reporting Summary (if required), cover letter (if it mentions ethics) | If the study uses human/animal subjects, an ethics statement must appear in Methods and the Reporting Summary must include the relevant rigor elements |

Failure mode: Methods mentions animal work but no IACUC protocol number.
Route to `nature-methods` for resolution.

### C7: Extended Data consistency (Nature flagship only)

| Field | Artefacts to check | Match rule |
|---|---|---|
| Extended Data figure/table count | Manuscript (in-text "Extended Data Fig. N" references), Extended Data file set | Same rule as C2 but for Extended Data |

## Check output format

```
## 3. Cross-artefact consistency

[✅] C1: Journal name — "Nature Methods" in cover letter, DA statement, manuscript
[⚠] C2: Figure count — manuscript references Fig 1–8, but only 7 figure files provided
     Missing: Fig 5 (referenced on page 12: "Fig. 5c shows...")
     Action: provide figure file or verify reference
[✅] C3: Author list — 6 authors, consistent across all documents
[⚠] C4: Statistical methods — Results mentions "Mann-Whitney U test" not in Methods statistics paragraph
     In Results: "two-tailed Mann-Whitney U test, P = 0.003"
     In Methods: "Student's t-test (two-sided) was used for comparisons"
     Action: update Methods statistics paragraph or route to nature-stats
[✅] C5: Data availability — GEO and Figshare accessions match
[—] C6: Ethics — ethics statement not checked (no human/animal study indicated)
[—] C7: Extended Data — not applicable (not a Nature flagship submission)
```

## What this step catches that individual skills miss

Individual skills check quality within one artefact:
- `nature-stats` checks that a Results sentence reports p, effect size, n — but
  it does not check that the test in that sentence matches the Methods paragraph.
- `nature-cover` checks that the fit argument names the right journal — but it
  does not check that the DA statement names the same journal.
- `nature-figure` checks that a figure is Nature-compliant — but it does not
  check that every figure is referenced in the text.

This step is the only one that crosses artefact boundaries. That is its
discriminator.
