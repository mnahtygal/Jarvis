# Jarvis

## Local-First AI Engineering Assistant

> Build. Analyze. Design. Remember. All locally.

## Mission

Jarvis is a local-first AI engineering assistant built around the NVIDIA
Jetson AGX Thor. It combines local LLMs, vision, voice, memory, and
engineering tools into a modular platform.

## Status

- Phase 1: Complete
- Phase 2: Active - Maker & Workshop Assistant
- Current focus: Scan Mat, Vision Lab, Mission Control, memory, and Maker Lab foundations

## Features

- React/Vite dashboard with Home, Mission Control, Vision Lab, Maker Lab, Memory, and System views
- Flask API for text, voice, dashboard status, camera, vision, and scan-mat workflows
- Local llama.cpp text model on port 8080
- Local llama.cpp vision model on port 8081
- PostgreSQL exact memory
- PostgreSQL + pgvector semantic memory
- Camera snapshot and local image analysis
- Scan Mat raw, annotated, and rectified artifact workflow
- Boot V3 Thor startup environment
- Operational CLI and health scripts
- Maker Lab planned

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

Backend structure:

```text
api.py       Flask API entry point
core/        Brain, router, memory, context, DB, boot
skills/      Task-specific capabilities
scripts/     Startup, status, smoke-test, and CLI helpers
docs/        Architecture and operations documentation
```

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
- [Ubuntu Startup](docs/UBUNTU_STARTUP.md)
- [Boot History](docs/BOOT_HISTORY.md)
- [Changelog](docs/CHANGELOG.md)
