# Jarvis Architecture Review

Date: 2026-07-03  
Project: Jarvis Local-First AI Engineering Assistant  
Host target: NVIDIA Jetson AGX Thor  
Status: Architecture review before Mission Control / cleanup pass

---

## 1. Executive Summary

Jarvis has evolved from a local chatbot into a local-first AI workstation platform. The current repo contains a working Flask API, React/Vite dashboard, local llama.cpp text runtime, local vision runtime, PostgreSQL exact memory, PostgreSQL + pgvector semantic memory, camera capture, scan-mat analysis, dashboard status endpoints, device status checks, MartyBench status integration, and a new Boot V3 startup system.

The near-term direction should be consolidation, not expansion. Mission Control should not be built as a separate second dashboard. It should be a focused System / Operations page inside the existing React UI and should consume the already-existing `/api/status/dashboard` status model.

---

## 2. Evolution From Project Conversations

### Early Jarvis / MartyBench phase

Jarvis was proven as a real local inference and benchmarking platform through the May 2026 MartyBench session. That work validated:

- llama.cpp OpenAI-compatible local inference
- CUDA-backed local generation
- streaming long-output generation
- HTML / JavaScript benchmark generation
- a practical split where Jetson handles generation and the Windows gaming rig handles WebGL rendering validation

That session established the MartyBench idea: prompt library, side-by-side model comparison, token/sec metrics, scoring, runtime validation, screenshot capture, regression tests, and cleanup passes.

### API / UI Dashboard phase

By June 2026 Jarvis had a working Flask API-backed dashboard. The dashboard status service reports brain readiness, active model/runtime, PostgreSQL exact memory, pgvector semantic memory, recent conversation history, local embedding status, and MartyBench latest score.

### Device status phase

The device dashboard pass added hardware readiness reporting for the Samson Q2U microphone, Insta360 Link camera, PipeWire audio backend, expected camera path, video devices, and the Dell dock power reminder.

### Vision / Camera phase

Jarvis now has camera snapshot routes, latest image serving, vision analysis through the local vision server, scan-mat analysis, and capture-then-analyze workflows.

### Boot V3 phase

Boot V3 converted Thor from a manually started Linux development box into an AI workstation boot environment. It starts Jarvis services, waits for UI readiness, checks text and vision LLM endpoints, reports running models and system resources, opens VS Code, and intentionally leaves Firefox session restore to Firefox.

---

## 3. Current Mental Model

### 3.1 Frontend

Current frontend is a Vite / React / TypeScript app under `ui-app/`.

Key files:

- `ui-app/src/App.tsx`
- `ui-app/src/JarvisUI.tsx`
- `ui-app/src/types/dashboard.ts`
- `ui-app/src/components/StatusCard.tsx`
- `ui-app/src/components/GlowRing.tsx`
- `ui-app/src/components/ControlButton.tsx`
- `ui-app/src/components/ActivityLog.tsx`

Current behavior:

- `App.tsx` renders `JarvisUI` directly.
- `JarvisUI.tsx` owns most UI state and logic.
- Existing navigation pages are: Home, Vision Lab, Maker Lab, Memory, System.
- The dashboard polls `/api/status/dashboard` and renders top-level cards.
- Camera snapshot, image analysis, scan mat, typed command, and voice ask flows are all handled in the same large component.

Frontend conclusion:

The UI is functional but `JarvisUI.tsx` is now too large. Mission Control should use this existing dashboard data model but should accelerate component extraction rather than adding more logic into the same file.

---

### 3.2 Backend

Current backend is Flask in `api.py`.

Major route groups:

- Health and root:
  - `/`
  - `/health`

- Dashboard status:
  - `/api/status/dashboard`
  - `/api/status/brain`
  - `/api/status/model`
  - `/api/status/memory`
  - `/api/status/martybench`
  - `/api/status/devices`

- Voice / text interaction:
  - `/listen`
  - `/ask`
  - `/text`

- Camera / vision:
  - `/api/camera/snapshot`
  - `/api/camera/latest`
  - `/api/camera/analyze`
  - `/api/camera/capture-analyze`
  - `/api/vision/scan-mat`
  - `/api/vision/capture-scan-mat`
  - artifact routes under `/api/vision/artifacts/...`

Backend conclusion:

The Flask API is already capable of supporting Mission Control. The main risk is that `api.py` is becoming a route monolith. The next cleanup pass should split route groups into modules or blueprints.

---

### 3.3 Boot System

Current boot pieces:

- `core/boot/boot-v3.sh`
- `scripts/start-jarvis.sh`
- `scripts/startup.sh`
- `scripts/stop-jarvis.sh`
- `scripts/jarvis-health.sh`
- `scripts/jarvis`
- `~/.config/autostart/thor-jarvis-startup.desktop` on Thor

Boot V3 flow:

1. Print Thor AI Workstation banner.
2. Start Jarvis services via `scripts/start-jarvis.sh`.
3. Wait for `http://localhost:5173`.
4. Check UI, text LLM, and vision LLM endpoints.
5. Print running llama-server processes.
6. Print uptime, memory, and disk.
7. Open VS Code to `~/jarvis`.
8. Skip Firefox launch so Firefox restores its own pinned tabs.

Boot conclusion:

Boot V3 is working and should be treated as stable. Do not reintroduce Firefox launching into Boot V3 unless there is a new explicit design. Browser state belongs to Firefox session restore.

---

### 3.4 LLM Integration

Current text LLM stack:

- Runtime: llama.cpp OpenAI-compatible server
- Primary URL: `http://127.0.0.1:8080/v1/chat/completions`
- Model status URL: `http://127.0.0.1:8080/v1/models`
- Current default model: Qwen3 30B
- Fallback path still references Ollama on port 11434

Key files:

- `skills/llm_skill.py`
- `skills/llama_cpp_skill.py`
- `skills/llm_stream_skill.py`
- `skills/model_runtime.py`
- `core/context.py`

Current behavior:

- `llm_skill.py` routes to llama.cpp first and can fall back to Ollama.
- `llama_cpp_skill.py` builds OpenAI-compatible chat completion payloads.
- `model_runtime.py` checks `/v1/models` and maps model IDs to friendly names.
- `llm_stream_skill.py` supports streaming generation but is still tied to an older hard-coded model ID.

LLM conclusion:

The synchronous LLM path is stronger than the streaming path. Streaming should be upgraded to use `get_active_model_id()`, `build_messages()`, environment-configurable URLs, and the same thinking-stripping behavior as the main llama.cpp skill.

---

### 3.5 Vision

Current vision stack:

- Runtime: llama.cpp vision server
- Port: 8081
- API path: `/v1/chat/completions`
- Default model env: `JARVIS_VISION_MODEL`
- Current local model identity: Gemma 3 4B Vision

Key files:

- `skills/vision_skill.py`
- `skills/camera_skill.py`
- `skills/scan_mat_skill.py`
- API routes in `api.py`

Current behavior:

- Camera snapshots are captured with `ffmpeg` from a configured `/dev/video*` path.
- Latest snapshots are served as JPEGs.
- Vision analysis sends a base64 image payload to the local vision server.
- Scan-mat analysis creates raw, annotated, and rectified artifacts when possible.

Vision conclusion:

Vision is functional enough for Mission Control to report readiness and recent artifacts. Next hardening should focus on camera device consistency: device status expects `/dev/video1`, while camera capture defaults to `/dev/video0` unless `JARVIS_CAMERA_DEVICE` is set.

---

### 3.6 Memory

Jarvis currently has two memory layers.

Exact memory:

- File: `core/memory.py`
- Tables: `memories`, `memory_history`
- Uses PostgreSQL through `core/db.py`
- Supports remember, recall, update, forget, list, and history

Semantic memory:

- File: `core/semantic_memory.py`
- Table: `semantic_memories`
- Uses PostgreSQL + pgvector
- Embedding model: local `all-MiniLM-L6-v2`
- Offline mode enforced through Hugging Face / Transformers env flags
- Supports schema creation, add, search, count, category inference, tag inference, source boosts, category boosts, weighted similarity ranking

Session memory:

- File: `core/session.py`
- Tracks conversation history and last topic for dashboard / context use

Memory conclusion:

Memory is one of Jarvis's strongest areas. The next improvement should be clear separation between exact facts, semantic project notes, session history, and benchmark memory so Mission Control can display each without blending them together.

---

### 3.7 Skills

Skills are currently Python modules under `skills/` and are routed through `core/router.py`.

Observed skill groups:

- Chat / fallback LLM
- Time
- System health
- Health
- Help
- Version
- Runtime identity
- Memory summary
- Semantic memory
- Docs
- Brain status
- Dashboard status
- Device status
- Camera
- Vision
- Scan mat
- MartyBench status

Router behavior:

- `core/brain.py` records user/assistant messages and tracks last topic.
- `core/router.py` normalizes voice/text input and matches commands.
- Known exact-memory questions are answered without the LLM.
- Freeform remember/note/save commands go into semantic memory.
- Fallback goes to the local LLM.

Skills conclusion:

The skill system works, but routing is becoming a long procedural if/else chain. A registry-based skill router would make future growth safer.

---

### 3.8 CLI

Current CLI:

- `scripts/jarvis`

Commands:

- `jarvis start`
- `jarvis startup`
- `jarvis boot`
- `jarvis stop`
- `jarvis restart`
- `jarvis status`
- `jarvis health`
- `jarvis logs`
- `jarvis edit`
- `jarvis ui`

CLI conclusion:

The CLI is now useful but still shell-script based. Keep it simple for now. Add only high-value operations: `doctor`, `mission`, `api-log`, `ui-log`, and `version`.

---

## 4. What's Complete

- Local-first project mission and repo identity
- Flask API running on port 5000
- React/Vite dashboard running on port 5173
- llama.cpp text model runtime on port 8080
- llama.cpp vision runtime on port 8081
- Brain/router path from voice/text into skills and LLM fallback
- Exact PostgreSQL memory
- Semantic PostgreSQL + pgvector memory
- Offline local embedding model path
- Session history / last topic tracking
- Dashboard status service
- Dashboard API endpoints
- Device status checks
- Camera snapshot capture
- Latest snapshot serving
- Vision analysis endpoint
- Scan-mat endpoint and artifact serving
- MartyBench status integration
- Boot V3 startup system
- Jarvis CLI wrapper
- VS Code auto-open on login
- Firefox responsibility cleanly separated from Boot V3

---

## 5. What's In Progress

- Mission Control / operations dashboard
- Component split of `JarvisUI.tsx`
- System page maturity
- Voice hardening
- Camera device reliability
- Vision Lab polish
- Maker Lab design
- Memory page design
- Benchmark / MartyBench v2 operationalization
- Better log access from UI
- Better diagnostics from CLI

---

## 6. Technical Debt

### High priority

1. `JarvisUI.tsx` is too large and owns too many responsibilities.
2. `api.py` is becoming a route monolith.
3. `core/router.py` is a long procedural router and will become hard to maintain.
4. Camera device path mismatch risk: device status expects `/dev/video1`, camera capture defaults to `/dev/video0`.
5. `llm_stream_skill.py` is hard-coded to an older model identity and does not reuse the main context/model runtime path.
6. DB credentials have local defaults in code. Fine for lab use, but should be moved to `.env` and documented.

### Medium priority

1. Dashboard status calls duplicate some checks across brain/model/memory/devices.
2. Shell scripts and Python backend both know service URLs; config should be centralized.
3. Boot logs were committed during the Boot V3 milestone. Runtime logs should not be tracked.
4. CLI help formatting has embedded multi-line echo quirks.
5. Model file names in `scripts/start-jarvis.sh` may differ from actual launched model paths seen in runtime logs.
6. No formal API schema contract exists for dashboard status.

### Low priority

1. UI uses many inline styles.
2. No dedicated route system yet in React.
3. Mission Control route/page should be added cleanly rather than creating a second dashboard app.
4. Tests exist in multiple places but do not yet form a single test command.

---

## 7. Recommended Roadmap

### Phase 1: Stabilize and document the current platform

- Keep Boot V3 stable.
- Add this architecture review to docs.
- Add `.gitignore` entries for logs/runtime artifacts if missing.
- Confirm no runtime logs are tracked.
- Add `jarvis doctor` as a non-destructive diagnostic command.

### Phase 2: Mission Control v0.1

Build Mission Control as a new page inside existing UI, likely under the current System page first.

Use existing source:

- `/api/status/dashboard`

Do not create a second status model unless needed.

Mission Control v0.1 should show:

- Brain readiness
- Text LLM status
- Vision LLM status
- API status
- UI status
- PostgreSQL status
- Semantic memory status
- Device readiness
- Camera/mic status
- Uptime / RAM / disk from Boot/system status if exposed
- Links/buttons for logs later

### Phase 3: Component extraction

Split `JarvisUI.tsx` into:

- `components/layout/AppShell.tsx`
- `components/dashboard/TopStatusCards.tsx`
- `components/dashboard/LiveDetails.tsx`
- `components/home/HomePage.tsx`
- `components/vision/VisionLabPage.tsx`
- `components/memory/MemoryPage.tsx`
- `components/system/SystemPage.tsx`
- `components/mission/MissionControlPage.tsx`
- `hooks/useDashboardStatus.ts`
- `hooks/useCamera.ts`
- `hooks/useJarvisCommand.ts`

### Phase 4: Backend route cleanup

Split Flask routes into modules or blueprints:

- `api/status_routes.py`
- `api/chat_routes.py`
- `api/camera_routes.py`
- `api/vision_routes.py`
- `api/artifact_routes.py`

Keep `api.py` as app factory / route registration.

### Phase 5: Runtime configuration

Create one config source for:

- API port
- UI port
- text LLM URL
- vision LLM URL
- model IDs
- camera device
- PostgreSQL settings
- log paths

Suggested file:

- `.env`
- `config/jarvis.env.example`
- `core/config.py`

### Phase 6: LLM streaming cleanup

Update `skills/llm_stream_skill.py` to:

- use `get_active_model_id()`
- use `build_messages()`
- respect env-configured URL
- share thinking stripping behavior
- support longer benchmark runs cleanly

### Phase 7: MartyBench platform

Turn MartyBench from a successful experiment into a real module:

- benchmark prompt library
- run metadata
- model/runtime capture
- scoring
- artifact folders
- regression comparisons
- UI summary card
- benchmark details page

---

## 8. Recommended Next Move

Do Mission Control, but keep it small:

1. Reuse `/api/status/dashboard`.
2. Add a Mission Control section/page to the existing UI.
3. Do not add restart buttons yet.
4. Do not add new backend status logic unless the current dashboard endpoint lacks a field.
5. Use this work to start extracting `JarvisUI.tsx` into components.

Mission Control v0.1 should be a visibility layer, not a control layer. Once the display is stable, add controls carefully.
