# Workflow, architecture, and output format

## Workflow

1. **Identify letter type and target journal.** Full submission cover letter, presubmission
   enquiry, or transfer/resubmission letter? Which journal, exactly? If the journal is
   unnamed, flag it as required input — the fit argument cannot be generic.

2. **Extract the one-sentence advance and the strongest evidence.** From the manuscript,
   abstract, or author notes, find the single most important result and state it in one
   plain sentence. This is the spine of the letter. If it is unclear, ask rather than guess.

3. **Identify the gap and the significance.** What was unresolved before this work, and what
   does the advance change? Size the significance to the evidence the author actually has.

4. **Build the journal-fit argument.** Tie the advance to this journal's stated scope and
   readership specifically. Name what makes it a match (breadth of interest, methodological
   advance, timeliness). A fit paragraph that fits any journal is a failure.

5. **Assemble declarations and logistics.** Non-dual-submission statement, competing
   interests, corresponding author, and — if the journal allows — suggested and excluded
   reviewers with brief reasons. Flag anything the author must confirm (ethics approval,
   author agreement, data deposition).

6. **Draft to the architecture and enforce the length budget.** One page, ~250–500 words.
   Cut generic impact sentences before cutting the hook or fit argument.

7. **Return the letter plus unresolved fields.** Ready-to-paste letter text, then a list of
   every fact the author must supply or confirm. In audit mode, lead with blocking issues.

## Paragraph architecture

A standard full cover letter runs four to five short paragraphs:

1. **Opening + hook (2–4 sentences).** Address the editor; name the manuscript title and
   that it is submitted for consideration; then the hook — why the advance is consequential,
   in plain language. Lead with the science, not with "We are pleased to submit".
2. **Gap → advance (3–5 sentences).** The unresolved problem, then "Here we show / we
   report…" with the single key result and its strongest quantitative support.
3. **Significance (2–4 sentences).** What the result changes, who it matters to, and why now
   — calibrated, concrete, no slogans.
4. **Fit to journal (2–3 sentences).** Why this journal and its readership specifically.
5. **Declarations + close (2–4 sentences).** Non-dual-submission, competing interests,
   suggested/excluded reviewers if applicable, corresponding-author line, courteous close.

A presubmission enquiry is shorter: hook, advance, one significance sentence, and a direct
question to the editor about whether the work fits — no reviewer suggestions or full
declarations.

## Length budget

- Target one page, ~250–500 words.
- The hook and the fit argument are load-bearing; protect them when cutting.
- Generic impact sentences ("This work will be of broad interest to many fields") are the
  first to cut — they carry no information for the editor.
- If the draft exceeds the budget, compress significance and background, not the advance or
  the fit.

## Output format

Unless the user asks for another format, return:

```text
Cover letter
[ready-to-paste letter text, addressed and signed, within the length budget]

Word count: [number] (target ~250–500)

Reporting decisions (draft mode) / Findings (audit mode)
- [decision or blocking issue, most important first, with the why]

Missing information / author-input needed
- [each fact the author must supply or confirm — journal name, key numbers,
   ethics/data statements, reviewer suggestions — or "None"]

中文核对
- [用中文列出作者需要确认或补充的项，或 "无"]
```

When auditing an existing letter, lead with blocking issues (no hook, significance not
supported, no journal-specific fit, overclaiming, over length), then provide the revision.
