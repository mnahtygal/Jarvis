# Jarvis Architecture

Last updated: 2026-07-17

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
  +--> Camera role resolver / Vision Lab / Scan Mat / Calibration / Measurement
  |                    |
  |                    +--> runtime/camera artifacts
  |                    +--> config/camera_profiles.json
  |                    +--> llama.cpp vision server :8081
  |
  +--> PipeWire microphone resolver -> Samson Q2U preference
  |
  +--> Architecture Lab -> read-only Graphify HTML artifacts
  |                    +--> runtime/graphify/graphify-out
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
pages/ArchitectureLabPage.tsx
pages/PlaceholderPage.tsx
```

Home provides command, voice, camera, quick-command, and live-detail views. Mission Control is a read-only operations page backed by `/api/status/dashboard`. Vision Lab handles camera snapshots, prompt modes, scan-mat artifacts, local vision analysis, calibration, Scan Mat diagnostics, and measurement. Architecture Lab displays Graphify status, statistics, the generated project tree, and the generated call-flow diagram. Maker Lab, Memory, and System currently use a reusable placeholder page.

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
| Dashboard status | `/api/status/dashboard`, `/api/status/architecture`, `/api/status/brain`, `/api/status/model`, `/api/status/memory`, `/api/status/martybench`, `/api/status/devices`, `/api/status/camera-diagnostics`, `/api/status/calibration`, `/api/status/measurement` |
| Camera | `/api/cameras`, `/api/camera/active`, `/api/camera/snapshot`, `/api/camera/latest` |
| Vision | `/api/camera/analyze`, `/api/camera/capture-analyze` |
| Scan Mat | `/api/vision/scan-mat`, `/api/vision/capture-scan-mat` |
| Calibration | `/api/calibration/profile`, `/api/calibration/apply` |
| Measurement | `/api/measurement/analyze` |
| Architecture | `/api/architecture/tree`, `/api/architecture/callflow` |
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
| `architecture_status_skill.py` | Reads Graphify graph and artifact availability |
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

## Architecture Lab and Graphify

Graphify is installed separately from Jarvis at `/home/mnahtygal/repos/graphify`
and is not a Jarvis Python dependency. Generated output remains untracked under
`runtime/graphify/graphify-out/`. Architecture Lab reads graph status and embeds
only the explicitly allowed `JARVIS_TREE.html` and `graphify-callflow.html`
artifacts through fixed Flask routes. It does not execute Graphify or refresh
generated output.

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

Vision Lab is the main workshop workflow surface.

### Camera Roles

`core/camera_roles.py` separates stable purposes from unstable Linux device
paths. It inventories each V4L2 node, reads card name, `bus_info`, driver,
capabilities, node-specific `Device Caps`, and stable symlinks, then groups the
capture and metadata interfaces for each physical camera:

| Role | Camera | Use |
| --- | --- | --- |
| `workbench` | Logitech HD Pro Webcam C920 | Fixed Vision Lab and Scan Mat capture |
| `face` | Insta360 Link | Face/general camera capture |

Vision Lab retrieves the role inventory from `GET /api/cameras` and switches
the active role through `POST /api/camera/active`. Scan Mat capture explicitly
uses the default `workbench` role. `/dev/video0`, `/dev/video2`, and other node
numbers may change after restart and are never permanent role mappings.

Profile resolution order is `/dev/v4l/by-id`, exact card name plus `bus_info`,
optional `/dev/v4l/by-path`, then an exact unique legacy name hint for backward
compatibility. The transient `/dev/videoX` capture node is returned at runtime
as `resolved_device_path`; stable symlinks and identity details are reported
alongside it. Broad substring matching cannot silently choose between similar
cameras.

Many USB cameras expose one Video Capture node and one Metadata Capture node.
The broad V4L2 `Capabilities` block can list both types for either node, so only
`Device Caps` determines the interface type. Image acquisition code receives
only the Video Capture node. A metadata-only match is unavailable for capture
and is surfaced as a resolution error.

The Insta360 gimbal investigation remains historical/reference information; it
does not define the current Scan Mat camera.

Camera configuration lives in:

```text
config/camera_profiles.json
```

The configuration stores stable identity hints, active role, preferred capture
settings, scan-mat assumptions, and calibration values. Fixed `/dev/video`
numbers are not authoritative configuration.

### Microphone Resolution

`core/microphone.py` enumerates PipeWire/PulseAudio sources. It prefers the
Samson Q2U by stable name hints (or an explicit `JARVIS_MIC_SOURCE` override)
and avoids Insta360, Logitech, C920, webcam, and camera microphones when choosing
a fallback. Device status exposes whether the preferred microphone is present
and active.

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

Boot V3 starts missing services, requires Flask readiness at `GET /health`,
waits for UI readiness, reports all four service endpoints, opens VS Code, and
intentionally does not launch Firefox. Firefox restores its own previous
session.

The service scripts use `nohup` and runtime PID/process validation rather than
the older systemd checkpoint design. `jarvis restart` gracefully stops the
repo-specific API and UI, waits for port 5000 to clear, reloads their source,
and preserves healthy llama.cpp processes on ports 8080 and 8081. The API uses
`/tmp/jarvis-api.pid` and `/tmp/jarvis-api.log`; startup is not successful until
`GET /health` responds. `GET /api/cameras` then verifies the camera-role route.

## CLI

`scripts/jarvis` is the human-facing command wrapper:

| Command | Purpose |
| --- | --- |
| `jarvis start` | Start Jarvis services |
| `jarvis startup` / `jarvis boot` | Run full Boot V3 sequence |
| `jarvis stop` | Stop the repo-specific Jarvis API and UI |
| `jarvis restart` | Reload API and UI; preserve healthy model servers |
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
