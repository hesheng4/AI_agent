# Ethics, approvals, consent, and rigor elements

Open this when you need ethics/approval/consent statement templates, or the rigor elements
(randomisation, blinding, inclusion/exclusion, sample-size rationale).

## Ethics and approval statements

Required wherever the work involves humans, animals, or regulated biosafety material. Never
write these as if approval exists when the author has not confirmed it — flag as author-input
and leave a bracketed placeholder. Never invent an approving body, protocol number, or consent
procedure.

### Human participants
A complete statement names: the approving body (IRB / research ethics committee), the protocol
or approval number, that the study was conducted in accordance with the relevant declaration
(commonly the Declaration of Helsinki), and the consent procedure.

Template:
"All experiments involving human participants were approved by [ethics committee / IRB name],
[institution] (protocol number [XXX]). The study was conducted in accordance with the
Declaration of Helsinki. Written informed consent was obtained from all participants [or:
from participants' legal guardians] prior to enrolment."

For identifiable data/images, add a consent-to-publish statement. For clinical trials, add the
registry name and registration number.

### Animal studies
Template:
"All animal procedures were approved by the [IACUC / animal ethics committee name],
[institution] (protocol number [XXX]), and performed in accordance with [relevant national/
institutional guidelines]. [Species, strain, sex, age, source.] [Housing conditions.]"

Reference the ARRIVE guidelines for the full set of items animal studies should report.

### Biosafety / field / other
- Biosafety: approval and containment level for pathogens/recombinant material.
- Field studies: permits for collection, protected species, or access to land/sites.
- Human cell lines / tissue: source approvals and consent where applicable.

## Rigor elements

Nature-family Reporting Summaries ask these explicitly. State each, or state "not applicable"
with a brief reason — silence reads as an omission.

### Sample-size rationale
- How the sample size was chosen: a power analysis (with the assumptions), a pre-registered
  number, or a stated rationale based on prior work or feasibility.
- Avoid "n was chosen based on experience" with nothing further; give the basis. (Effect-size
  and power detail can route to nature-stats.)

### Randomisation
- Whether subjects/samples were randomised to groups, and the method (e.g. random number
  generator, block randomisation).
- If not randomised, say so and why (e.g. observational design).

### Blinding
- Whether investigators were blinded during allocation, during the experiment, and/or during
  outcome assessment and analysis — these are distinct.
- Who was blinded and how. If blinding was not possible, state why.

### Inclusion/exclusion criteria
- Pre-established criteria for including or excluding data, samples, or participants.
- Any data excluded, how many, and the reason — decided before, not after, seeing the result.
- For data exclusion after the fact, the criterion must be stated and justified.

### Reproducibility of findings
- How many times key experiments were independently repeated, and whether attempts succeeded.

### Sex and gender reporting
- Nature Portfolio asks authors to report the sex (and, for human studies, gender) of
  organisms/participants and to account for it in the design and analysis.
- For single-sex studies (e.g. male-only mice), state the choice and justify it, or note it
  as a limitation. Silence on a single-sex design is a common reviewer flag.

## How this interacts with nature-stats

This skill ensures the *design rigor* elements are present and stated (randomisation, blinding,
exclusion, sample-size rationale). The *statistical analysis* itself — test choice, exact
p-values, effect sizes, multiple-comparison correction — is `nature-stats`. When auditing,
flag both: "rigor elements missing" here, and "route the statistics reporting to nature-stats".
