# Jarvis AI Engineering Playbook

## Mission

Jarvis is a local-first AI engineering assistant built to help with software development, 3D printing, laser engraving, electronics, Raspberry Pi projects, SDR, data engineering, and workshop tasks.

Reliability, maintainability, and local operation always take priority over flashy features.

## Current Phase

Phase 2: Maker & Workshop Assistant

Primary focus:

1. Finish Scan Mat workflow.
2. Add accurate calibration and measurement.
3. Add object recognition and comparison.
4. Generate OpenSCAD starter models from scans.
5. Build Maker Lab workflows.
6. Add persistent scan history and project memory.
7. Introduce practical agentic engineering workflows.

Do not jump ahead to automation, robotics, cloud sync, or complex agent behavior until the Scan Mat and Maker Lab foundations are stable.

## Core Principles

Jarvis must remain:

- Local-first
- Offline-capable
- Modular
- Maintainable
- Understandable
- Testable
- Recoverable
- GitHub-synchronized

Prefer simple, boring, reliable code over clever code.

## Non-Negotiables

Do not introduce cloud dependencies unless explicitly requested.

Do not replace PostgreSQL + pgvector with another memory/vector system.

Do not remove or rewrite working features unless explicitly requested.

Do not break existing API routes without adding compatibility or migration notes.

Do not add large frameworks without discussion.

Do not hide failures. Return useful errors and log enough context to debug.

Do not make undocumented architecture changes.

## Preferred Development Workflow

1. Inspect the existing repo before changing code.
2. Make the smallest safe change that accomplishes the task.
3. Preserve existing behavior unless the task explicitly says otherwise.
4. Run relevant checks.
5. Show the diff before commit.
6. Update documentation when behavior, endpoints, folders, or workflow changes.
7. Commit only after human approval.

## Required Checks

For Python changes:

```bash
.venv/bin/python -m compileall -q api.py core skills audio tools
```

For UI changes:

```bash
cd ui-app
npm run lint
npm run build
```

If a check cannot run, explain exactly why.

## Repository Areas

Common structure:

```text
api.py                  Flask API entry point
core/                   Brain, router, memory, sessions
skills/                 Tool/skill modules including camera, vision, scan mat, llama.cpp
ui-app/                 React/Vite dashboard
scripts/                Operational scripts
tools/                  Dev, benchmark, health, and utility tools
docs/                   Project documentation
```

## Backend Rules

Use clear Flask route names.

Keep route handlers thin. Put reusable logic in `skills/`, `core/`, or `tools/`.

Prefer `pathlib.Path` over string path manipulation.

Prefer type hints for new Python functions.

Use structured JSON responses for API calls.

Every endpoint that performs hardware, model, camera, database, or file operations should return useful failure details.

Do not hardcode secrets, passwords, or machine-specific paths unless they are private local defaults and clearly documented.

## Frontend Rules

Use React + Vite only.

Keep the dashboard simple and workshop-friendly.

Do not introduce Next.js or a new UI framework without approval.

Use dark UI styling consistent with the existing app.

Preserve existing dashboard behavior.

Avoid huge components when a small child component would improve readability.

Use React hooks correctly and keep lint clean.

## Vision Lab Rules

Vision Lab is the primary UI for camera and scan workflows.

For Scan Mat work, always preserve these outputs when possible:

- Raw captured image
- Annotated OpenCV detection image
- Rectified top-down image
- Metadata JSON

Never trust measurements until calibration is proven.

Do not add OpenSCAD generation until raw, annotated, rectified, and calibrated measurement outputs are stable.

## Scan Mat Rules

The workshop mat is 18 x 24 inches.

Scan Mat Mode should eventually support:

- Mat detection
- Perspective correction
- Pixel-to-inch/mm calibration
- Object bounding boxes
- Measurement overlays
- Scan history
- OpenSCAD starter generation

Current priority is display and stabilization, not advanced modeling.

## Measurement Rules

All measurements must record:

- Unit used
- Calibration source
- Pixel-to-unit ratio
- Confidence or quality indicator where possible
- Raw image reference
- Rectified image reference

Never present measurements as precise unless calibration quality supports it.

## Memory Rules

Semantic memory lives in PostgreSQL + pgvector.

Do not introduce Chroma, FAISS, Pinecone, cloud vector search, or another memory system unless explicitly requested.

Project memory should be practical and inspectable.

Prefer storing structured records for scans, projects, generated models, decisions, and notes.

## Maker Lab Rules

Maker Lab should support real workshop workflows:

- 3D printing
- OpenSCAD generation
- laser engraving prep
- electronics notes
- Raspberry Pi builds
- SDR projects
- part comparison
- repair notes

Keep Maker Lab features grounded in files, scans, measurements, and project memory.

## OpenSCAD Rules

Generated OpenSCAD should be starter geometry, not guaranteed final CAD.

Prefer simple primitives, named parameters, and comments.

Generated models should include:

- Units
- Source scan ID if available
- Assumptions
- Editable dimensions
- Clear TODO comments

Do not claim generated models are production-ready.

## Documentation Rules

Update docs when:

- API routes change
- folder structure changes
- Scan Mat outputs change
- setup steps change
- model ports change
- memory behavior changes
- UI workflow changes

Docs should be useful to Marty returning to the project days or weeks later.

## Model Architecture

Current local model layout:

- Qwen3 30B text model on port 8080
- Gemma 3 4B Vision model on port 8081
- Flask API on port 5000
- React/Vite dashboard
- PostgreSQL + pgvector memory

Preserve this architecture unless explicitly asked to change it.

## Security Rules

Local-first does not mean careless.

Avoid committing:

- passwords
- tokens
- private keys
- `.env` files
- personal data dumps
- large generated artifacts

Move configurable secrets to environment variables.

## Git Rules

Keep commits focused.

Good commit messages:

```text
Add Scan Mat image display support
Fix Vision Lab lint issue
Document Phase 2 Maker Lab roadmap
Add scan output metadata schema
```

Avoid giant mixed commits.

## Agent Behavior

When acting as an AI coding agent:

- Read relevant files first.
- State assumptions.
- Make minimal changes.
- Run checks.
- Show the diff.
- Do not commit unless asked.
- Do not push unless asked.

