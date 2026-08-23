---
name: nature-paper2ppt
description: >-
  Build a Nature-style Chinese PPTX presentation from a scientific paper. Identifies paper type, writes Chinese slides, creates .pptx, and runs self-review loop.
  Also trigger on Chinese phrasings: 论文做PPT、论文汇报、组会PPT、文献汇报、学术汇报、做幻灯片、讲paper.
version: 2.0.0
---

# Nature Paper2Ppt — Router

This skill is split into two layers:

- A **static layer** under `static/` that holds versioned, reusable content fragments.
- A **dynamic layer** (this file plus `manifest.yaml`) that detects the request and loads only the fragments needed.

Do not try to apply the logic from memory. Always load fragments from disk as described below.

## Routing protocol

### 1. Load the manifest and the core layer

Read [manifest.yaml](manifest.yaml). Then read every file listed under `always_load`.

### 2. Detect the paper_type

Map the user's need to a `paper_type` value per the manifest. State the detected value before proceeding.

### 3. Load the matching fragment(s)

Read the file mapped for the detected `paper_type`. Do not load every fragment.

### 4. Run the workflow using the loaded material

Apply the loaded material in priority order: core fragments first, then axis-specific fragments, then on-demand references.

### 5. Reach for references only when needed

The files under `references/` are deep references, not defaults. Open them on demand per the `references.on_demand` table in the manifest.
