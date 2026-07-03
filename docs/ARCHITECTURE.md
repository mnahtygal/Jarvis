# Jarvis Architecture

Last updated: 2026-07-03

Jarvis is a local-first AI engineering assistant. It runs a React/Vite dashboard, a Flask API, local llama.cpp model servers, PostgreSQL exact memory, PostgreSQL + pgvector semantic memory, camera and vision workflows, and Boot V3 startup automation on Thor.

## High-Level Diagram

```text
User
  |
  |  browser, voice, CLI
  v
React/Vite UI                 Jarvis CLI / scripts
  |                                   |
  | HTTP                              |
  v                                   v
Flask API -------------------- operational checks
  |
  +--> Brain -> Router -> Skills
  |                    |       |
  |                    |       +--> time, docs, health, runtime, memory, LLM
  |                    |
  |                    +--> PostgreSQL exact memory
  |                    +--> PostgreSQL + pgvector semantic memory
  |
  +--> Camera / Vision / Scan Mat skills
  |                    |
  |                    +--> runtime/camera artifacts
  |                    +--> llama.cpp vision server :8081
  |
  +--> Dashboard status aggregation
                       |
                       +--> text model :8080
                       +--> vision model :8081
                       +--> PostgreSQL / pgvector
                       +--> devices / MartyBench / recent history
```

## Frontend

The frontend lives in `ui-app/` and uses React, TypeScript, and Vite. It still uses simple in-memory page navigation; React Router has not been introduced.

```text
ui-app/src/
  JarvisUI.tsx              Shell, top status cards, page selection, shared state
  pages/                    Page-level UI
  components/               Reusable visual components
  hooks/                    Reusable React state/effect logic
  services/                 HTTP client functions
  config/                   Frontend constants
  types/                    Shared TypeScript types
```

### Pages

```text
pages/HomePage.tsx
pages/MissionControlPage.tsx
pages/VisionLabPage.tsx
pages/PlaceholderPage.tsx
```

Home provides command, voice, camera, quick-command, and live-detail views. Mission Control is a read-only operations page backed by `/api/status/dashboard`. Vision Lab handles camera snapshots, prompt modes, scan-mat artifacts, and local vision analysis. Maker Lab, Memory, and System currently use a reusable placeholder page.

### Components

```text
components/ActivityLog.tsx
components/ControlButton.tsx
components/GlowRing.tsx
components/MissionSection.tsx
components/StatusCard.tsx
components/StatusDot.tsx
```

Components are reusable display primitives. They should not own backend communication.

### Hooks

```text
hooks/useApiHealth.ts
hooks/useDashboardStatus.ts
```

Hooks own reusable frontend state/effects. `useDashboardStatus` polls dashboard status every `appConfig.dashboardRefreshMs`. `useApiHealth` owns API health status and triggers dashboard refresh after health checks.

### Services

```text
services/jarvisApi.ts
```

This is the centralized HTTP client for the frontend. UI code should call service functions rather than using raw `fetch()` directly.

### Config

```text
config/appConfig.ts
```

Current frontend constants:

| Key | Value | Purpose |
| --- | --- | --- |
| `apiBaseUrl` | `http://127.0.0.1:5000` | Flask API base URL |
| `dashboardRefreshMs` | `30000` | Mission/dashboard polling |
| `clockRefreshMs` | `1000` | Header clock update |

### Types

```text
types/dashboard.ts
```

Contains API response shapes consumed by the dashboard and Mission Control.

## Backend

The backend entry point is `api.py`, a Flask app with CORS enabled for the local dashboard.

### Route Groups

| Area | Routes |
| --- | --- |
| Health | `/`, `/health` |
| Text and voice | `/text`, `/listen`, `/ask` |
| Dashboard status | `/api/status/dashboard`, `/api/status/brain`, `/api/status/model`, `/api/status/memory`, `/api/status/martybench`, `/api/status/devices` |
| Camera | `/api/camera/snapshot`, `/api/camera/latest` |
| Vision | `/api/camera/analyze`, `/api/camera/capture-analyze` |
| Scan Mat | `/api/vision/scan-mat`, `/api/vision/capture-scan-mat` |
| Artifacts | `/api/vision/artifacts/raw/<artifact_name>`, `/api/vision/artifacts/mat-analysis/<artifact_name>` |

### Brain

`core/brain.py` is the conversational entry point. It:

1. Cleans the command.
2. Records the user message.
3. Detects and stores a last topic.
4. Routes the command through `core.router.route()`.
5. Stores the assistant response.

### Router

`core/router.py` normalizes user text and selects a response path:

- exact memory commands
- semantic memory commands
- runtime identity
- health/status/help/version/docs
- skill handlers
- LLM fallback

### Skills

The `skills/` layer contains task-specific logic. Current important skills include:

| Skill | Responsibility |
| --- | --- |
| `dashboard_status_skill.py` | Aggregates dashboard status |
| `device_status_skill.py` | Checks microphone, camera, PipeWire, and dock note |
| `model_runtime.py` | Reads active llama.cpp model information |
| `camera_skill.py` | Captures snapshots with ffmpeg |
| `vision_skill.py` | Sends images to local vision model |
| `scan_mat_skill.py` | OpenCV scan-mat detection and artifact generation |
| `semantic_memory_skill.py` | Semantic memory status/search responses |
| `llm_skill.py`, `llama_cpp_skill.py` | Local text model calls |

## Memory

Jarvis uses PostgreSQL for persistent local memory.

### Exact Memory

`core/memory.py` stores key/value facts and history in PostgreSQL tables such as `memories` and `memory_history`.

### Semantic Memory

`core/semantic_memory.py` stores embeddings in PostgreSQL + pgvector.

Current semantic design:

- local/offline embedding model
- default path: `models/embeddings/all-MiniLM-L6-v2`
- 384-dimensional vectors
- `semantic_memories` table
- metadata categories and tags
- source/category weighting at search time

Do not replace PostgreSQL + pgvector with Chroma, FAISS, Pinecone, or a cloud vector store unless explicitly requested.

## Local Models

Jarvis uses llama.cpp servers.

| Service | Port | Purpose |
| --- | --- | --- |
| Text LLM | `8080` | Main Qwen brain model |
| Vision LLM | `8081` | Gemma vision model |
| Flask API | `5000` | Jarvis backend |
| React UI | `5173` | Vite dashboard |

The text model identity is read from `http://127.0.0.1:8080/v1/models`. Vision status is read from port `8081`.

## Boot System

Boot V3 is the current startup system.

```text
Ubuntu autostart entry
  -> scripts/startup.sh
  -> core/boot/boot-v3.sh
  -> scripts/start-jarvis.sh
  -> services and checks
```

Boot V3 starts Jarvis services, waits for UI readiness, reports model and resource status, opens VS Code, and intentionally does not launch Firefox. Firefox restores its own previous session.

## CLI

`scripts/jarvis` is the human-facing command wrapper:

| Command | Purpose |
| --- | --- |
| `jarvis start` | Start Jarvis services |
| `jarvis startup` / `jarvis boot` | Run full Boot V3 sequence |
| `jarvis stop` | Stop Jarvis UI |
| `jarvis restart` | Stop and restart startup flow |
| `jarvis status` / `jarvis health` | Run health checks |
| `jarvis logs` | Follow startup log |
| `jarvis edit` | Open repo in VS Code |
| `jarvis ui` | Open UI in Firefox |

## Repository Layout

```text
api.py                  Flask API entry point
audio/                  Listen/speak support
core/                   Brain, router, memory, context, DB, boot
skills/                 Task-specific backend capabilities
scripts/                Operational CLI and service helpers
ui-app/                 React/Vite frontend
docs/                   Architecture, operations, roadmap, checkpoints
benchmarks/             MartyBench and evaluation materials
models/                 Local-only model assets
runtime/                Generated camera/scan artifacts
logs/                   Local runtime logs
tools/                  Developer utilities
```

## Data Flow

### Text Command

```text
HomePage typed command
  -> jarvisApi.sendTextCommand()
  -> POST /text
  -> core.brain.think()
  -> core.router.route()
  -> skill / memory / LLM
  -> JSON response
  -> ActivityLog
```

### Voice Ask

```text
HomePage Listen
  -> POST /ask
  -> audio.listen.listen_command()
  -> core.brain.think()
  -> optional audio.speak.speak()
  -> ActivityLog
```

### Dashboard / Mission Control

```text
useDashboardStatus()
  -> jarvisApi.getDashboardStatus()
  -> GET /api/status/dashboard
  -> skills.dashboard_status_skill.get_dashboard_status()
  -> top status cards and Mission Control
```

### Vision Lab

```text
Capture Current View
  -> POST /api/camera/snapshot
  -> runtime/camera/snapshot_*.jpg
  -> GET /api/camera/latest for preview

Analyze Snapshot
  -> POST /api/camera/analyze
  -> local vision server :8081
  -> ActivityLog

Scan Mat
  -> POST /api/vision/capture-scan-mat
  -> raw / annotated / rectified artifacts
  -> VisionLab artifact cards
```

## Current Architecture Decisions

| Decision | Status |
| --- | --- |
| Local-first operation | Active principle |
| PostgreSQL + pgvector memory | Required architecture |
| llama.cpp for local inference | Current runtime |
| React/Vite dashboard | Current UI stack |
| Mission Control as existing UI page | Implemented |
| No React Router yet | Intentional |
| No cloud dependencies by default | Required |
| Boot V3 does not launch Firefox | Intentional |
| Restart/shutdown buttons not in Mission Control | Intentional |

