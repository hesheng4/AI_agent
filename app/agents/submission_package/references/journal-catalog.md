# Nature Portfolio journal catalogue

Version: 2026-06 (curated snapshot; verify against current journal pages)

This file lists Nature Portfolio journals relevant to the life/physical/computational
sciences with their scope keywords, submission requirements, and differentiators.
It is used by the journal-match step and the checklist-generation step.

## Tier 1: Flagship

| Journal | Scope keywords | Differentiated requirements |
|---|---|---|
| Nature | Broad, high-impact, cross-disciplinary, paradigm-shifting | Reporting Summary mandatory; Extended Data figures + tables; presubmission enquiry recommended; cover letter ≤ 500 words; no word limit on manuscript |
| Nature Genetics | Genetics, genomics, epigenomics, gene regulation | Reporting Summary; ARRIVE for animal work; must deposit sequencing data in public repository |
| Nature Medicine | Translational, clinical, therapeutic, disease mechanism | Reporting Summary; CONSORT for clinical trials; STROBE for observational studies; clinical-trial registration number required |
| Nature Neuroscience | Neural circuits, brain, cognition, neurodegeneration | Reporting Summary; ARRIVE; power analysis or sample-size justification mandatory |
| Nature Cell Biology | Cell signalling, organelle, cytoskeleton, cell cycle | Reporting Summary; ARRIVE; mycoplasma testing statement |
| Nature Chemical Biology | Chemical probes, small molecules, biosynthesis | Reporting Summary; compound characterisation data (NMR, MS) in Supplementary |
| Nature Structural & Molecular Biology | Structure, mechanism, macromolecular complex | Reporting Summary; PDB deposition required; validation report |
| Nature Physics | Quantum, condensed matter, astrophysics, AMO | No Reporting Summary; data availability statement still required |
| Nature Materials | Materials design, characterisation, energy, nanotech | Reporting Summary; FAIR data; code availability |
| Nature Nanotechnology | Nanoscale, nanomedicine, nanofabrication | Reporting Summary; ARRIVE for in vivo; nanomaterial characterisation checklist |

## Tier 2: Sub-journals (broad scope, OA)

| Journal | Scope keywords | Differentiated requirements |
|---|---|---|
| Nature Communications | Broad, solid, not necessarily paradigm-shifting | Reporting Summary; Extended Data optional; cover letter shorter (≤ 300 words typical); OA article-processing charge |
| Scientific Reports | Broad, technically sound, no novelty bar | No Reporting Summary; minimal format requirements; OA |
| Nature Scientific Reports | (alias for Scientific Reports) | — |

## Tier 2: Sub-journals (field-specific)

| Journal | Scope keywords | Differentiated requirements |
|---|---|---|
| Nature Methods | Methods, protocols, analytical tools, software | Reporting Summary; benchmark data required; software + code availability; Method of the Year consideration |
| Nature Biotechnology | Biotech, pharma, agricultural, industrial | Reporting Summary; patent/IP disclosure; clinical-trial registration |
| Nature Ecology & Evolution | Ecology, evolution, behaviour, conservation | Reporting Summary; ARRIVE; data deposition in Dryad/figshare/GBIF |
| Nature Climate Change | Climate, energy policy, earth system | Reporting Summary; data + code availability |
| Nature Machine Intelligence | ML, AI, robotics, computational | No Reporting Summary; code + model availability mandatory; benchmark comparison |
| Nature Computational Science | Algorithms, HPC, scientific computing | No Reporting Summary; code availability; reproducible computational workflow |
| Nature Chemical Engineering | Process, catalysis, separation, scale-up | Reporting Summary; FAIR data |

## Tier 3: Nature Research Journals (formerly Nature Research Communications)

| Journal | Scope keywords | Differentiated requirements |
|---|---|---|
| Nature Cardiovascular Research | Cardiovascular | Reporting Summary; OA |
| Nature Cancer | Oncology, tumour biology | Reporting Summary; ARRIVE; OA |
| Nature Mental Health | Psychiatry, psychology, epidemiology | Reporting Summary; STROBE; OA |

## Journal-match logic

Given an abstract and paper type, score each journal by:

1. **Scope overlap** — do the abstract's subject terms appear in the journal's
   scope keywords?
2. **Impact tier** — flagship journals require paradigm-shifting claims;
   sub-journals require solid, well-controlled work.
3. **Study-type fit** — a methods paper fits Nature Methods better than Nature;
   a clinical trial fits Nature Medicine better than Nature Communications.
4. **Author's own signal** — if the author mentions a specific journal or
   journal tier, weight that heavily.

Present 2–4 candidates ranked by score, with a one-sentence scope-fit reason
for each. The author decides.

## Common requirements (all Nature Portfolio)

Every submission to any Nature Portfolio journal requires:

- Manuscript (Word or LaTeX)
- Figures (editable format: SVG, PDF, EPS, or AI)
- Data Availability Statement
- Competing interests declaration
- Author contributions statement
- Cover letter
- Supplementary Information (if any)
- Reporting Summary (for journals that require it — see table above)

## Reminder

This catalogue is a curated snapshot. Journal requirements change.
**Always verify against the current journal submission page before submitting.**
