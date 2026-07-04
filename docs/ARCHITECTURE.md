# Jarvis Architecture

Last updated: 2026-07-04

Jarvis is a local-first AI engineering assistant. It runs a React/Vite dashboard, a Flask API, local llama.cpp model servers, PostgreSQL exact memory, PostgreSQL + pgvector semantic memory, camera, vision, calibration, measurement workflows, and Boot V3 startup automation on Thor.

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
  +--> Camera / Vision / Scan Mat / Calibration / Measurement
  |                    |
  |                    +--> runtime/camera artifacts
  |                    +--> config/camera_profiles.json
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

Home provides command, voice, camera, quick-command, and live-detail views. Mission Control is a read-only operations page backed by `/api/status/dashboard`. Vision Lab handles camera snapshots, prompt modes, scan-mat artifacts, local vision analysis, calibration, Scan Mat diagnostics, and measurement. Maker Lab, Memory, and System currently use a reusable placeholder page.

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
hooks/useCalibration.ts
hooks/useMeasurement.ts
```

Hooks own reusable frontend state/effects. `useDashboardStatus` polls dashboard status every `appConfig.dashboardRefreshMs`. `useApiHealth` owns API health status and triggers dashboard refresh after health checks. `useCalibration` owns Vision Lab calibration state and calls the calibration API. `useMeasurement` owns Vision Lab measurement state and calls the measurement API.

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

Contains API response shapes consumed by the dashboard, Mission Control, Vision Lab calibration, Scan Mat diagnostics, and measurement UI.

## Backend

The backend entry point is `api.py`, a Flask app with CORS enabled for the local dashboard.

### Route Groups

| Area | Routes |
| --- | --- |
| Health | `/`, `/health` |
| Text and voice | `/text`, `/listen`, `/ask` |
| Dashboard status | `/api/status/dashboard`, `/api/status/brain`, `/api/status/model`, `/api/status/memory`, `/api/status/martybench`, `/api/status/devices`, `/api/status/camera-diagnostics`, `/api/status/calibration`, `/api/status/measurement` |
| Camera | `/api/camera/snapshot`, `/api/camera/latest` |
| Vision | `/api/camera/analyze`, `/api/camera/capture-analyze` |
| Scan Mat | `/api/vision/scan-mat`, `/api/vision/capture-scan-mat` |
| Calibration | `/api/calibration/profile`, `/api/calibration/apply` |
| Measurement | `/api/measurement/analyze` |
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
| `camera_diagnostics_skill.py` | Reports read-only camera diagnostics |
| `vision_skill.py` | Sends images to local vision model |
| `scan_mat_skill.py` | OpenCV scan-mat detection and artifact generation |
| `calibration_skill.py` | Reports calibration readiness |
| `measurement_skill.py` | Reports measurement readiness |
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

## Vision Foundation

The July 3-4 sprint made Vision Lab the main workshop workflow surface.

### Camera Diagnostics

Jarvis can report read-only camera diagnostics for the Thor/Insta360 setup. Current findings:

- `/dev/video0` is the real video capture node.
- `/dev/video1` is the metadata node.
- Driver is `uvcvideo`.
- Standard V4L2 pan/tilt/zoom controls exist, but pan/tilt values do not physically move the Insta360 Link gimbal.
- No Insta360 HID interface is exposed.
- UVC Extension Unit was detected with Unit ID 9, GUID `faf1672d-b71b-4793-8c91-7b1c9b7f95f8`, and 11 controls.
- Real gimbal movement likely requires vendor-specific UVC extension-unit commands.

### Manual Scan Station

The current Scan Mat workflow assumes the camera is manually positioned overhead and kept fixed. Camera profiles live in:

```text
config/camera_profiles.json
```

The active profile stores device mapping, scan-mat assumptions, calibration values, and gimbal-control limitations.

### Calibration

Calibration is profile-backed:

```text
Scan Mat corners + known mat dimensions
  -> core.calibration.compute_calibration_from_mat()
  -> POST /api/calibration/apply
  -> active camera profile calibration values
  -> dashboard / Vision Lab status
```

Calibration records millimeters per pixel, pixels per millimeter, confidence, and timestamp.

### Measurement

Measurement foundation is intentionally simple:

```text
Rectified scan-mat image
  -> POST /api/measurement/analyze
  -> core.measurement.measure_object_bbox_from_image()
  -> largest_contour_bbox_v0
  -> width / height / area / confidence / diagnostics
```

This is bounding-box measurement v0. It is not yet a visual overlay system and should not be treated as precision metrology until calibration and detection quality are validated.

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

Apply Calibration
  -> latest scan corners + known dimensions
  -> POST /api/calibration/apply
  -> active camera profile
  -> dashboard refresh

Measure Object
  -> latest rectified artifact path
  -> POST /api/measurement/analyze
  -> bounding-box measurement result
  -> VisionLab measurement card
```

## Current Architecture Decisions

| Decision | Status |
| --- | --- |
| Local-first operation | Active principle |
| PostgreSQL + pgvector memory | Required architecture |
| llama.cpp for local inference | Current runtime |
| React/Vite dashboard | Current UI stack |
| Mission Control as existing UI page | Implemented |
| Vision Lab as primary camera/calibration/measurement workspace | Implemented |
| No React Router yet | Intentional |
| No cloud dependencies by default | Required |
| Boot V3 does not launch Firefox | Intentional |
| Restart/shutdown buttons not in Mission Control | Intentional |
| Measurement overlay is next, not complete | Active roadmap |
