# Jarvis Architecture

## Overview

Jarvis is a local-first AI assistant running primarily on the NVIDIA Jetson AGX Thor Developer Kit with Ubuntu 24.04.4 LTS.

The system combines local LLM inference, local vision inference, Flask APIs, a React/Vite dashboard, voice support, camera capture, PostgreSQL memory, and workshop-oriented tools.

## Current Runtime Components

```text
Qwen3 30B Text Model       localhost:8080
Gemma 3 4B Vision Model    localhost:8081
Flask API                  localhost:5000
React/Vite Dashboard       ui-app dev/build server
PostgreSQL + pgvector      semantic/project memory
Camera Pipeline            capture + scan workflows
Voice Pipeline             STT/TTS support
```

## High-Level Flow

```text
User
  ↓
React/Vite Dashboard
  ↓
Flask API
  ↓
Core Brain / Router
  ↓
Skills
  ├── llama.cpp text model
  ├── vision model
  ├── camera capture
  ├── scan mat workflow
  ├── semantic memory
  └── status/health tools
```

## Backend

`api.py` is the Flask API entry point.

Route handlers should stay thin. Reusable logic belongs in:

- `core/`
- `skills/`
- `tools/`
- `scripts/`

## Core Layer

The `core/` folder owns Jarvis internals such as:

- brain/router logic
- session management
- memory coordination
- database access helpers

The core should not become a dumping ground for hardware-specific logic.

## Skills Layer

The `skills/` folder contains practical capabilities Jarvis can call.

Examples:

- camera
- vision
- scan mat
- local LLM calls
- status checks
- semantic memory

Skills should be modular and independently testable where practical.

## UI Layer

The `ui-app/` folder contains the React/Vite dashboard.

The UI should remain simple, dark themed, and workshop usable.

Primary UI areas:

- Chat/dashboard
- Status panels
- Camera tools
- Vision Lab
- Scan Mat workflow
- Future Maker Lab

## Memory Architecture

Jarvis uses PostgreSQL + pgvector.

Memory types may include:

- semantic facts
- project notes
- scan records
- generated model records
- benchmark records
- workflow history

Do not introduce another vector database unless explicitly requested.

## Vision Architecture

Vision support currently uses a local Gemma 3 4B Vision model on port 8081.

The vision flow should support:

1. Capture image.
2. Save raw image.
3. Analyze image with local vision model.
4. Run OpenCV scan/mat detection.
5. Save annotated image.
6. Save rectified image.
7. Return image paths and metadata to the UI.

## Scan Mat Architecture

Scan Mat Mode is the bridge between camera vision and Maker Lab.

Expected outputs:

- raw image
- annotated image
- rectified image
- metadata JSON
- calibration data
- measurement data
- future OpenSCAD starter file

The mat is 18 x 24 inches.

## Reliability Goals

Jarvis should be useful even when:

- internet is unavailable
- cloud APIs are unavailable
- one model server is down
- camera capture fails
- vision analysis fails

Failures should be visible, logged, and recoverable.

## Development Philosophy

Jarvis should grow like a workshop tool, not a demo app.

Every feature should answer one of these questions:

- Does this help Marty build something?
- Does this help diagnose or repair something?
- Does this improve local AI capability?
- Does this make Jarvis easier to maintain?

