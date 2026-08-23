# Submission checklist template

Open this when you need the per-item checklist structure for a submission
package, or the requirements each artefact type must satisfy.

## Checklist items (generic Nature Portfolio)

Each item below is a row in the submission checklist. The skill marks each
✓ / ✗ / ⚠ based on whether the user has provided it.

### Required for all submissions

| # | Item | Artefact type | Produced by skill | Key fields to extract |
|---|---|---|---|---|
| 1 | Manuscript | document | author / nature-writing / nature-polishing | title, author list, abstract, section count, word count |
| 2 | Figures | image files | author / nature-figure | figure count, panel count per figure, format (SVG/PDF/EPS/AI), resolution |
| 3 | Cover letter | document | nature-cover | target journal name, editor name (if named), word count |
| 4 | Data Availability Statement | document | nature-data | repository names, accession numbers, target journal name |
| 5 | Competing interests declaration | text block | author | present / absent |
| 6 | Author contributions | text block | author | CRediT roles, author list |
| 7 | Supplementary Information | document(s) | author | file count, figure/table count within |

### Required by some journals

| # | Item | Artefact type | Produced by skill | Required by | Key fields |
|---|---|---|---|---|---|
| 8 | Reporting Summary | form / document | author / nature-methods | flagship + most sub-journals (see journal-catalog) | study type, rigor elements, statistics section |
| 9 | Extended Data figures | image files | author / nature-figure | Nature flagship | count, must match in-text references |
| 10 | Extended Data tables | document | author | Nature flagship | count, must match in-text references |
| 11 | Suggested reviewers | text block | author | all | 2–6 names, affiliations, expertise, no COI |
| 12 | Excluded reviewers | text block | author | all | names, reason |
| 13 | Presubmission enquiry | email | nature-cover | Nature flagship (recommended) | already sent? Y/N |
| 14 | Clinical trial registration | identifier | author | Nature Medicine, Nature Biotechnology | registry, number |
| 15 | Ethics approval statement | text block | nature-methods | human/animal/biosafety studies | approving body, protocol number |
| 16 | Informed consent statement | text block | nature-methods | human studies | consent type, IRB |
| 17 | Code / software availability | text block | author / nature-data | Nature Methods, Nature MI, Nature Comp Sci | repository URL, licence |
| 18 | Benchmark data | dataset | author | Nature Methods | dataset name, access URL |

### Study-type add-ons

When the study type triggers a reporting standard, add its mandatory items:

| Reporting standard | Study type | Additional items |
|---|---|---|
| CONSORT | Randomised controlled trial | CONSORT flow diagram, trial registration, 25-item checklist |
| STROBE | Observational epidemiology | STROBE checklist, confounder list |
| ARRIVE | Animal experiment | ARRIVE checklist, power/sample-size justification, blinding statement |
| MIQE | qPCR | MIQE checklist, primer sequences, efficiency data |
| PRISMA | Systematic review / meta-analysis | PRISMA flow diagram, search strategy, risk-of-bias assessment |

## Checklist output format

```
## 2. Submission checklist

Journal: [name]
Study type: [type]
Reporting standard: [standard or "none"]

### Required items
[✓] 1. Manuscript — "Title..." (12 figures, 4 tables)
[✗] 2. Cover letter — MISSING
     Route: nature-cover
     Input needed: title, abstract, key result, target journal, significance
[⚠] 3. Data Availability Statement — present but no accession numbers
     Action: add accession numbers or route to nature-data
[✓] 4. Competing interests declaration — "The authors declare no competing interests."
[✗] 5. Author contributions — MISSING
     Route: author (not a skill — must be written by the corresponding author)
[✓] 6. Figures — 12 figures provided (SVG format)
[✓] 7. Supplementary Information — 3 supplementary figures, 2 tables

### Journal-specific items
[✗] 8. Reporting Summary — MISSING (required for [journal])
     Route: nature-methods (rigor elements) + author (statistics section)
[✓] 9. Suggested reviewers — 3 names provided

### Study-type items
[✗] 10. ARRIVE checklist — MISSING (required for animal study)
      Route: nature-methods (rigor elements) + author (experimental details)
```

## Reminder

The checklist template is generic. Journal-specific requirements come from
`journal-catalog.md`. **Always verify against the current journal submission
page before submitting.**
