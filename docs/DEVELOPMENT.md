# Jarvis Development Guide

Last updated: 2026-07-04

This guide is for developing Jarvis on Thor or another Ubuntu workstation. Jarvis is local-first: avoid adding cloud dependencies, hidden service assumptions, or large frameworks without discussion.

## Ubuntu Setup

Recommended platform:

| Item | Current target |
| --- | --- |
| OS | Ubuntu 24.04 LTS |
| Host | NVIDIA Jetson AGX Thor |
| Python | Project virtual environment in `.venv/` |
| Node | Node/npm for Vite UI |
| Database | PostgreSQL + pgvector |
| Model runtime | llama.cpp |

Common system tools:

```bash
sudo apt update
sudo apt install git curl build-essential python3 python3-venv python3-pip ffmpeg
```

Install PostgreSQL and pgvector using the project/host procedure already established for Thor. Do not replace PostgreSQL + pgvector with another memory system.

## Python

Use the local virtual environment:

```bash
cd ~/jarvis
source .venv/bin/activate
python api.py
```

Required Python check:

```bash
cd ~/jarvis
.venv/bin/python -m compileall -q api.py core skills audio tools
```

## Node / npm

The React app is in `ui-app/`.

```bash
cd ~/jarvis/ui-app
npm install
npm run dev
```

Build check:

```bash
cd ~/jarvis/ui-app
npm run build
```

Lint check, when available:

```bash
cd ~/jarvis/ui-app
npm run lint
```

## VS Code

Boot V3 opens VS Code to `~/jarvis` if it is not already running. Recommended workflow:

1. Open the repo root.
2. Keep backend, UI, scripts, and docs edits in focused changes.
3. Use integrated terminals for API, UI, and checks.
4. Review diffs before staging.

## Git Workflow

Jarvis should stay GitHub-synchronized and recoverable.

Recommended flow:

```bash
git status --short
git diff
git add <focused files>
git commit -m "Add focused change summary"
```

Rules:

- Keep commits focused.
- Do not commit secrets, `.env`, model files, runtime artifacts, or logs.
- Do not commit generated camera artifacts under `runtime/`.
- Do not commit `ui-app/dist/`.
- Do not rewrite working features unless explicitly requested.
- Do not commit without human approval when working as an agent.

## Starting Jarvis

Start the full local stack:

```bash
cd ~/jarvis
./scripts/start-jarvis.sh
```

Run Boot V3:

```bash
cd ~/jarvis
./scripts/startup.sh
```

Using the CLI wrapper:

```bash
jarvis start
jarvis startup
jarvis boot
jarvis status
jarvis logs
```

## Starting the API Manually

```bash
cd ~/jarvis
source .venv/bin/activate
python api.py
```

API URL:

```text
http://127.0.0.1:5000
```

Health check:

```bash
curl http://127.0.0.1:5000/health
```

## Building the UI

```bash
cd ~/jarvis/ui-app
npm run build
```

Run the dev server:

```bash
cd ~/jarvis/ui-app
npm run dev -- --host 0.0.0.0
```

UI URL:

```text
http://localhost:5173
```

## Useful CLI Commands

| Command | Purpose |
| --- | --- |
| `jarvis start` | Start Jarvis services |
| `jarvis startup` / `jarvis boot` | Run Boot V3 |
| `jarvis status` / `jarvis health` | Run health helper |
| `jarvis logs` | Follow startup logs |
| `jarvis edit` | Open VS Code |
| `jarvis ui` | Open UI |
| `jarvis status` | Check API, UI, text LLM, vision LLM, API PID/age, and logs |
| `./scripts/jarvis-smoke-test.sh` | Run end-to-end smoke checks |

## Repository Conventions

### Backend

- Keep Flask route handlers thin.
- Put reusable logic in `skills/`, `core/`, or `tools/`.
- Return useful JSON errors for hardware, model, database, and file operations.
- Prefer `pathlib.Path`.
- Do not hardcode secrets.

### Frontend

- Keep using React + Vite.
- Keep page-level components in `ui-app/src/pages/`.
- Keep reusable visual components in `ui-app/src/components/`.
- Put reusable state/effect logic in `ui-app/src/hooks/`.
- Put HTTP calls in `ui-app/src/services/jarvisApi.ts`.
- Put frontend constants in `ui-app/src/config/appConfig.ts`.
- Keep shared dashboard types in `ui-app/src/types/dashboard.ts`.
- Keep calibration and measurement UI state in reusable hooks.
- Do not add React Router until the app actually needs route-level browser navigation.

### Documentation

Update docs when:

- API routes change.
- UI workflow changes.
- Boot/startup behavior changes.
- Folder structure changes.
- Scan Mat outputs change.
- Calibration, camera profile, or measurement behavior changes.
- Memory behavior changes.

### Vision Lab Development Notes

Vision Lab is the primary UI for camera and workshop workflows. Preserve these behavior boundaries:

- Scan Mat detection should keep raw, annotated, and rectified artifacts working.
- Scan Mat diagnostics should remain backward-compatible additions to the result payload.
- Calibration uses the latest scan corners and known real-world mat dimensions.
- Calibration values are stored in the active camera profile.
- Measurement currently uses the latest rectified scan image and `largest_contour_bbox_v0`.
- Measurement results must include calibration context, confidence, and diagnostics.
- Do not claim precision beyond calibration quality.
- Measurement Overlay is the next Phase 2.3B step; do not mix it into unrelated cleanup.

## Professional Development Workflow

1. Read the relevant files first.
2. Make the smallest safe change.
3. Preserve behavior unless the task says otherwise.
4. Run relevant checks.
5. Review the diff.
6. Update docs for behavior, workflow, or architecture changes.
7. Commit only after approval.

## Current Sprint State

The current Phase 2 foundation includes:

- Mission Control is read-only and backed by `/api/status/dashboard`.
- Frontend code is organized into pages, components, hooks, services, config, and types.
- Role-based Logitech C920 workbench and Insta360 Link face cameras are present.
- V4L2 camera paths and the preferred Samson Q2U microphone are resolved dynamically.
- Scan Mat, calibration, and bounding-box measurement foundations are present.
- Phase 2.3A Measurement Engine foundation is complete.
- Automatic object measurement, overlays, and validation are next.
