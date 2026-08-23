# Reproducibility checklist and forbidden phrasing

Open this when you need the full reproducibility checklist by item type, or the
forbidden-phrase list with replacements.

## The checklist, by item type

For each item the work uses, the Methods (main text or Supplementary) must give enough for an
independent lab to obtain or reconstruct the same thing.

### Reagents and chemicals
- supplier and catalogue number
- lot number where lot-to-lot variation matters (e.g. sera, some antibodies)
- concentration/amount actually used, not just "added"
- for kits: name, supplier, catalogue, and any deviation from the manufacturer protocol

### Antibodies
- target, host species, clone, monoclonal/polyclonal
- supplier and catalogue number
- **RRID** (Research Resource Identifier)
- dilution/amount and application (WB, IF, IHC, flow)
- validation statement or citation

### Cell lines
- source/origin (repository or lab)
- **authentication** method and date (e.g. STR profiling)
- **mycoplasma** testing status
- passage number range if relevant
- RRID where available

### Model organisms
- species, strain, and source/repository (RRID where available)
- sex and age/developmental stage
- housing/husbandry conditions for animals
- genotype for engineered lines

### Human participants
- recruitment, setting, dates
- inclusion/exclusion criteria
- demographics relevant to the study
- (ethics/consent: see ethics-and-rigor.md)

### Equipment and instruments
- manufacturer and model
- key acquisition settings (e.g. microscope objective, laser lines, detector; sequencer model
  and run mode; cytometer configuration)

### Procedures and parameters
- the steps in execution order
- exact parameters: temperatures, durations, concentrations, volumes, speeds, cycle numbers
- any deviation from a cited protocol

### Replicates and controls
- positive and negative controls used
- biological vs technical replicates, defined and counted
- number of independent experiments

### Software and code
- software name **and version** for every analysis tool
- key non-default parameters
- custom code: language, availability pointer (route the availability statement to nature-data)
- reference genomes/databases with version/build

## Forbidden vague phrasing (replace every instance)

| Vague phrase | Replace with |
|---|---|
| under standard conditions | the actual temperature, time, buffer, concentration |
| using routine/conventional methods | the steps, or a citation that truly contains them |
| as previously described | a specific citation that contains the full protocol, else the steps |
| data were analysed statistically | the named test and software (route to nature-stats) |
| differences were significant | the test and exact p (route to nature-stats) |
| samples were randomly assigned | the randomisation method actually used |
| investigators were blinded | who was blinded, to what, and how |
| the method/antibody was validated | how, with which controls |
| cells were cultured normally | medium, supplements, %CO₂, temperature, passaging |
| a high/low concentration | the actual concentration with units |
| sufficient/appropriate amount | the actual amount |

The rule: if a competent reader cannot reproduce the step from the words, the words are not
yet Methods. Either supply the value or leave a clearly bracketed `[author to supply: …]`
placeholder — never paper over the gap with a vague phrase.
