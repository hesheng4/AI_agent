---
name: nature-paper-to-patent
description: >-
  Convert scientific papers into evidence-grounded Chinese invention patent drafts with source mapping, claim-aligned flowcharts, and separate DOCX deliverables.
  Also trigger on Chinese phrasings: 论文转专利、专利草稿、发明专利、权利要求书、说明书.
version: 1.0.0
---

# Nature Paper To Patent — Router

This skill is split into two layers:

- A **static layer** under `static/` that holds versioned, reusable content fragments.
- A **dynamic layer** (this file plus `manifest.yaml`) that detects the request and loads only the fragments needed.

Do not try to apply the logic from memory. Always load fragments from disk as described below.

## Routing protocol

### 1. Load the manifest and the core layer

Read [manifest.yaml](manifest.yaml). Then read every file listed under `always_load`.

### 2. Detect the task_mode

Map the user's need to a `task_mode` value per the manifest. State the detected value before proceeding.

### 3. Load the matching fragment(s)

Read the file mapped for the detected `task_mode`. Do not load every fragment.

### 4. Run the workflow using the loaded material

Apply the loaded material in priority order: core fragments first, then axis-specific fragments, then on-demand references.

### 5. Reach for references only when needed

The files under `references/` are deep references, not defaults. Open them on demand per the `references.on_demand` table in the manifest.
