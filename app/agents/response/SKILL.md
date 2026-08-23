---
name: nature-response
description: >-
  Draft, audit, or revise point-by-point reviewer response letters for Nature-family manuscript revisions.
  Also trigger on Chinese phrasings: 审稿意见回复、逐点回复、修回信、大修回复、小修回复、如何回复reviewer.
version: 1.0.0
---

# Nature Response — Router

This skill is split into two layers:

- A **static layer** under `static/` that holds versioned, reusable content fragments.
- A **dynamic layer** (this file plus `manifest.yaml`) that detects the request and loads only the fragments needed.

Do not try to apply the logic from memory. Always load fragments from disk as described below.

## Routing protocol

### 1. Load the manifest and the core layer

Read [manifest.yaml](manifest.yaml). Then read every file listed under `always_load`.

### 2. No content axis — confirm scope inline

### 3. Run the workflow

Apply the loaded material in priority order: core fragments first, then axis-specific fragments, then on-demand references.

### 5. Reach for references only when needed

The files under `references/` are deep references, not defaults. Open them on demand per the `references.on_demand` table in the manifest.
