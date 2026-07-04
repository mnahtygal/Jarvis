# Jarvis

## Local-First AI Engineering Assistant

> Build. Analyze. Design. Remember. All locally.

## Mission

Jarvis is a local-first AI engineering assistant built around the NVIDIA
Jetson AGX Thor. It combines local LLMs, vision, voice, memory, and
engineering tools into a modular platform.

## Status

- Phase 1: Complete
- Phase 2: Architecture substantially complete
- Current version: 2.3.0-dev, Vision Foundation
- Current focus: Measurement Overlay, Phase 3 architecture planning, and Maker Lab foundations

## Features

- React/Vite dashboard with Home, Mission Control, Vision Lab, Maker Lab, Memory, and System views
- Professional frontend architecture using pages, components, hooks, services, config, and shared types
- Flask API for text, voice, dashboard status, camera, vision, scan-mat, calibration, and measurement workflows
- Local llama.cpp text model on port 8080
- Local llama.cpp vision model on port 8081
- PostgreSQL exact memory
- PostgreSQL + pgvector semantic memory
- Camera snapshot and local image analysis
- Camera diagnostics for Insta360 Link and Thor device mapping
- Scan Mat raw, annotated, and rectified artifact workflow
- Scan Mat diagnostics for contour/corner detection reliability
- Manual overhead scan station profile and camera profiles
- Calibration engine with profile-backed pixel-to-mm scale storage
- Interactive Vision Lab calibration UI
- Measurement engine foundation with bounding-box measurement v0
- Vision Lab measurement UI
- Boot V3 Thor startup environment
- Operational CLI and health scripts
- Maker Lab and Phase 3 architecture planned

## Current Architecture

```text
React/Vite UI
  -> Flask API
  -> core.brain / core.router
  -> skills
  -> PostgreSQL / pgvector
  -> llama.cpp text and vision servers
```

Frontend structure:

```text
ui-app/src/pages/       Page-level UI
ui-app/src/components/  Reusable UI primitives
ui-app/src/hooks/       React state/effect hooks
ui-app/src/services/    Frontend HTTP client
ui-app/src/config/      Frontend constants
ui-app/src/types/       Shared TypeScript types
```

Key frontend capabilities:

- Mission Control is a read-only operations view backed by `/api/status/dashboard`.
- Vision Lab owns camera capture, local vision analysis, Scan Mat artifacts, calibration, diagnostics, and measurement UI.
- Reusable hooks now own dashboard status, API health, calibration, and measurement state.
- `services/jarvisApi.ts` is the centralized frontend HTTP client.

Backend structure:

```text
api.py       Flask API entry point
core/        Brain, router, memory, context, DB, boot, calibration, measurement
skills/      Task-specific capabilities and status wrappers
scripts/     Startup, status, smoke-test, and CLI helpers
docs/        Architecture and operations documentation
```

Current backend capability areas:

- Camera diagnostics and snapshot capture
- Scan Mat detection, diagnostics, and artifacts
- Calibration computation and active camera profile persistence
- Measurement engine foundation using rectified scan images
- Dashboard aggregation for Mission Control

## Startup

Start Jarvis services:

```bash
cd ~/jarvis
./scripts/start-jarvis.sh
```

Run the Thor Boot V3 sequence:

```bash
jarvis startup
```

Useful commands:

```bash
jarvis status
jarvis logs
jarvis restart
```

Boot V3 intentionally does not launch Firefox. Firefox restores its own session.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Roadmap](docs/ROADMAP.md)
- [Vision](docs/VISION.md)
- [Phase 2 Summary](docs/PHASE2_SUMMARY.md)
- [Phase 3 Architecture](docs/PHASE3_ARCHITECTURE.md)
- [Ubuntu Startup](docs/UBUNTU_STARTUP.md)
- [Boot History](docs/BOOT_HISTORY.md)
- [Changelog](docs/CHANGELOG.md)
