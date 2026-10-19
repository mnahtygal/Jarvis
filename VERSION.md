# Jarvis Version History

Last updated: 2026-10-19

This file tracks major product milestones rather than every Git commit.

## Current Snapshot

**Version:** 2.3.0-dev  
**Primary product phase:** Phase 2 — Maker & Workshop Assistant  
**Parallel engineering milestone:** Developer Agent bounded repair on Thor

### Current platform

- Ubuntu 24.04 on NVIDIA Jetson AGX Thor
- Flask API and React/Vite UI
- Qwen3 30B text model via llama.cpp
- Gemma 3 4B Vision via llama.cpp
- PostgreSQL + pgvector
- Brain v2 deterministic orchestration
- Controlled Developer Agent with AppArmor/Bubblewrap candidate isolation

### 2026-10-19 Developer Agent milestone

Completed and independently verified on Thor:

- Brain v2 recognized the canonical explicit-workspace bounded-session request.
- Jarvis required an exact separate `approve` turn before execution.
- Initial project verification failed as expected.
- The local repair model generated one accepted proposal at confidence 0.8.
- The proposal was applied only to a disposable candidate workspace.
- Candidate verification passed under the live AppArmor/Bubblewrap isolation path.
- Jarvis sealed the exact passing bytes and promoted only those bytes to the
  original source.
- The session consumed 2 of the maximum 3 verification runs.
- Git stage, commit, and push were not invoked.
- Independent project verification completed with **6 passed**.

The repaired benchmark logic changed only `stock.py`; `test_stock.py` remained
read-only.

### Host isolation milestone

Thor now uses the reviewed native/API entry and AppArmor transition chain:

```text
jarvis-api-entry
  -> candidate_userns
  -> candidate_runtime
```

The final live candidate-isolation suite completed with **10 passed** before the
repair benchmark was rerun.

## Maker & Workshop Track

### 2.1 — Foundation — Complete

- Local llama.cpp text and vision serving
- Flask API
- React/Vite dashboard
- PostgreSQL + pgvector memory
- voice and vision pipelines
- GitHub-synchronized development workflow

### 2.2 — Calibration Engine — Complete foundation

- camera diagnostics and role-based selection
- Scan Mat stabilization
- calibration API/profile foundation
- pixel-to-mm conversion
- confidence/diagnostic surfaces

### 2.3 — Measurement Engine — In progress

Implemented:

- measurement API and Vision Lab UI
- role-based C920 workbench and Insta360 face camera
- Scan Mat 609.6 × 457.2 mm workflow
- single-object rotated measurement
- mask/overlay artifacts
- anisotropic X/Y calibration math
- Accuracy v2 segmentation/scoring diagnostics
- mm/in display

Remaining:

- physical ruler/caliper validation against known references
- multiple objects and internal features
- diameter-specific fitting
- measurement history and project association

## Planned Maker Milestones

### 2.4 — OpenSCAD starter generation

Generate conservative, editable starter geometry from validated measurements.

### 2.5 — Maker Lab

Project-oriented scan history, artifacts, notes, CAD comparison, printing,
laser/electronics/Raspberry Pi/SDR workflows.

## Release Philosophy

A milestone is not complete until:

- implementation is present
- relevant tests are green
- Thor behavior is verified when host-specific
- documentation is current
- diffs are reviewed
- GitHub is synchronized

> Architect with ChatGPT. Build with Codex. Validate on Thor.
