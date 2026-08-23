# Workflow and output format

## Workflow

1. **Identify the target journal.**
   - If the user names a journal, use it.
   - If not, open `references/journal-catalog.md` and run the journal-match
     step: from the manuscript's abstract, key result, and paper type, suggest
     2–4 candidate journals in the Nature Portfolio with a scope-fit reason for
     each. Present as a ranked list; the author chooses.
   - If the chosen journal is not in the catalogue, flag it and fall back to
     generic Nature Portfolio requirements. Strongly recommend the author
     verify the journal's submission page.

2. **Load journal-specific requirements.**
   - Open `references/journal-catalog.md` and extract the requirements for the
     chosen journal.
   - Open `references/checklist-template.md` for the generic checklist
     structure.
   - If the study type triggers a reporting standard (CONSORT, STROBE, ARRIVE,
     MIQE, PRISMA), add the standard's mandatory checklist items.
   - Note the catalogue version date for the output.

3. **Inventory provided artefacts.**
   - Ask the user which artefacts they have, or accept a list/file set.
   - For each artefact, note: present / absent / partially present (e.g. a
     cover letter exists but the user says it needs revision).
   - Record key extractable fields: journal name (from cover letter and DA
     statement), figure count, author list, statistical methods mentioned.

4. **Generate the submission checklist.**
   - For each required item, mark:
     - ✓ present — artefact provided
     - ✗ missing — artefact absent, route to responsible skill
     - ⚠ needs confirmation — artefact present but may need revision
   - For each ✗ item, output the routing instruction (which skill to invoke,
     what input that skill needs).
   - Append the reminder: "Verify against the current journal submission page
     before submitting."

5. **Run cross-artefact consistency checks.**
   - Open `references/consistency-rules.md` and execute every check.
   - For each check, report:
     - ✅ consistent — values match across artefacts
     - ⚠ mismatch — values differ, quote both, ask author to resolve
     - — not checked — one or both artefacts absent
   - This is the step that no single-artefact skill can perform. It is the
     primary discriminator of this skill.

6. **Output the structured report.**
   - Section 1: Journal match (if run) — candidate list with fit reasons.
   - Section 2: Submission checklist — every required item with status and
     routing.
   - Section 3: Consistency report — every check with result.
   - Section 4: Action summary — ordered list of what to do next (which skills
     to invoke, which mismatches to resolve).
   - Section 5: Catalogue version date + verification reminder.

## Output contract

The output must be a single structured report with these five sections, in this
order, using these exact headings:

```
## 1. Journal match
## 2. Submission checklist
## 3. Cross-artefact consistency
## 4. Action summary
## 5. Verification
```

### Checklist item format

```
[✓/✗/⚠] Item name — status detail
  Route: skill-name (if missing)
  Input needed: what that skill requires (if missing)
```

### Consistency check format

```
[✅/⚠/—] Check name: detail
  Value A: "..." (from artefact X)
  Value B: "..." (from artefact Y)
  Action: what to resolve (if mismatch)
```

### Action summary format

Ordered by dependency (produce artefacts before checking consistency):

1. Missing artefacts to produce (routed to skills)
2. Mismatches to resolve manually
3. Final verification step

## Length and format

- The checklist is structured, not prose. Use the formats above.
- No minimum or maximum length — the checklist is as long as the journal
  requires.
- Every output ends with the verification section containing the catalogue
  version date and the reminder.

## Edge cases

- **No journal specified and no abstract provided** — ask for at least an
  abstract or a paper type before running journal match. Do not guess.
- **Journal not in catalogue** — fall back to generic Nature Portfolio
  requirements. Flag prominently. Recommend verifying the journal page.
- **Only some artefacts provided** — mark the rest missing. Do not assume
  absence means "not needed".
- **Artefact provided but unreadable** (e.g. a PDF the skill cannot parse) —
  mark ⚠ and ask the author to extract key fields manually.
- **Contradictory information** (e.g. two different journal names in the same
  cover letter) — flag both values, do not pick one.
