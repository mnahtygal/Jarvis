# Jarvis

Jarvis is Marty's local-first AI assistant and AI workbench project.

It runs on local hardware, uses local model inference, stores memory in PostgreSQL/pgvector, supports voice, camera snapshots, local vision analysis, a React dashboard, and an early OpenCV scan-mat workflow for workshop/object inspection.

---

## Current Status

Jarvis is currently running on the NVIDIA Jetson AGX Thor Developer Kit as the primary development and inference platform.

Current foundation:

- Local text inference through `llama.cpp`
- Primary brain model: `Qwen3-30B-A3B-Q4_K_M.gguf`
- Local vision model: `ggml-org/gemma-3-4b-it-qat-GGUF`
- PostgreSQL exact long-term memory
- PostgreSQL conversation history
- pgvector semantic memory
- Local/offline MiniLM embeddings
- Flask API backend
- React/Vite dashboard UI
- Voice input through Whisper path
- Voice output through Piper/TTS path
- Camera snapshot capture through Insta360 Link on `/dev/video0`
- Local image analysis through Gemma vision on a separate llama.cpp server
- Vision Lab UI with scan modes
- OpenCV scan-mat analysis skill in progress
- Service-managed backend with status/restart/smoke-test scripts

Jarvis is no longer only a text chatbot. It is now a local multimodal assistant with a growing workshop / maker-lab workflow.

---

## Runtime Services

Current service layout on Thor:

```text
8080  Qwen3 main brain      jarvis-llama.service
8081  Gemma vision          jarvis-vision.service
5000  Flask API             jarvis-api.service
5173  React UI              manual npm run dev for now
```

The backend stack is service-managed. The React UI is still started manually.

Check backend services:

```bash
systemctl status jarvis-llama.service --no-pager
systemctl status jarvis-vision.service --no-pager
systemctl status jarvis-api.service --no-pager
```

Check endpoints:

```bash
curl -m 3 -s http://127.0.0.1:8080/health
curl -m 3 -s http://127.0.0.1:8081/health
curl -m 3 -s http://127.0.0.1:5000/health
```

---

## Quick Start

From Thor:

```bash
cd ~/jarvis
git pull
source .venv/bin/activate
```

Check the full Jarvis backend state:

```bash
./scripts/jarvis-status.sh
```

Restart the backend stack:

```bash
./scripts/jarvis-restart.sh
```

Run the smoke test:

```bash
./scripts/jarvis-smoke-test.sh
```

Start the React UI:

```bash
cd ~/jarvis/ui-app
npm run build
npm run dev
```

Open the Vite URL printed by the terminal, usually:

```text
http://localhost:5173/
```

---

## Current Architecture

```text
User / Voice / UI / API
  ↓
Flask API / React UI
  ↓
core.brain.think()
  ↓
core.router.route()
  ↓
Skill handler, exact-memory direct answer, semantic memory, or LLM fallback
  ↓
core.context.build_messages()
  ↓
llama.cpp / Qwen3 30B on port 8080
  ↓
Jarvis response
```

Vision path:

```text
Insta360 Link camera
  ↓
ffmpeg snapshot capture
  ↓
runtime/camera/snapshot_*.jpg
  ↓
Flask camera / vision route
  ↓
Gemma 3 4B multimodal model on port 8081
  ↓
Activity Log / Vision Lab result
```

Scan Mat path:

```text
Camera current view
  ↓
Snapshot capture
  ↓
OpenCV scan-mat analysis
  ↓
Mat detection / annotated image / rectified image / grid metadata
  ↓
Future measurement + object workflow
```

Not every text request reaches the LLM. Jarvis handles deterministic questions first:

- Runtime/platform questions
- Model/runtime questions
- Memory stack questions
- Jarvis long-term goal questions
- Common exact-memory facts
- Health/status/help/docs commands
- Semantic memory commands

Open-ended requests fall through to the local LLM.

---

## Platform

Current primary platform:

```text
Host: y-thor
Hardware: NVIDIA Jetson AGX Thor Developer Kit
OS: Ubuntu 24.04.4 LTS
Architecture: ARM64
Memory: 128 GB
CUDA: 13.0
Inference: llama.cpp
Database: PostgreSQL 16
Vector extension: pgvector
Camera: Insta360 Link
Microphone: Samson Q2U
```

Previous platform:

```text
NVIDIA Jetson AGX Xavier
```

The Xavier proved the early local Jarvis architecture. Thor is now the active development and inference platform.

---

## Core Components

| Component | Purpose |
|---|---|
| `api.py` | Flask backend for text, voice, dashboard, camera, vision, and scan-mat endpoints. |
| `core/brain.py` | Main thinking entry point. Stores user/assistant messages and calls the router. |
| `core/router.py` | Intent routing, memory commands, deterministic known-fact answers, and LLM fallback. |
| `core/context.py` | Builds prompt/messages for llama.cpp using exact memory, semantic memory, and recent conversation. |
| `core/memory.py` | PostgreSQL-backed exact long-term memory. |
| `core/session.py` | PostgreSQL-backed conversation history and last-topic state. |
| `core/semantic_memory.py` | pgvector semantic memory, local embeddings, source/category/tag ranking. |
| `skills/llama_cpp_skill.py` | Calls the local llama.cpp OpenAI-compatible text server. |
| `skills/llm_skill.py` | LLM routing layer with llama.cpp primary and Ollama fallback. |
| `skills/runtime_skill.py` | Deterministic runtime, model, memory stack, and Jarvis goal responses. |
| `skills/device_status_skill.py` | Detects microphone, camera, PipeWire, and device state. |
| `skills/dashboard_status_skill.py` | Builds dashboard status data for brain, model, vision, memory, devices, MartyBench. |
| `skills/camera_skill.py` | Captures camera snapshots to `runtime/camera/`. |
| `skills/vision_skill.py` | Sends local image data to the Gemma vision model. |
| `skills/scan_mat_skill.py` | OpenCV scan-mat detection, annotation, rectification, and grid metadata. |
| `audio/listen.py` | Voice input path. |
| `audio/speak.py` | Voice output path. |
| `ui-app/` | React/Vite Jarvis Command Center and Vision Lab. |
| `scripts/jarvis-status.sh` | Service and endpoint status helper. |
| `scripts/jarvis-restart.sh` | Restarts backend services. |
| `scripts/jarvis-smoke-test.sh` | End-to-end smoke test. |

---

## API Endpoints

Core:

```text
GET  /health
POST /text
POST /ask
GET  /api/status/dashboard
GET  /api/status/brain
GET  /api/status/model
GET  /api/status/memory
GET  /api/status/martybench
GET  /api/status/devices
```

Camera and vision:

```text
POST /api/camera/snapshot
GET  /api/camera/latest
POST /api/camera/analyze
POST /api/camera/capture-analyze
```

Scan Mat / OpenCV:

```text
POST /api/vision/scan-mat
POST /api/vision/capture-scan-mat
```

---

## Vision Lab

The React UI now includes top-level navigation:

```text
Home | Vision Lab | Maker Lab | Memory | System
```

Vision Lab currently supports scan modes:

```text
General Scan
Object on Mat
Measurement Helper
Read Text / Label
3D Print Inspect
Jet Ski Part Scan
Workbench Status
```

Important current behavior:

```text
Capture Current View = capture whatever the Insta360 is currently looking at
```

The camera does not automatically tilt down yet. For scan-mat work, aim the Insta360 down using the Insta360 Link Controller / DeskView or manual positioning before capture.

---

## Scan Mat Mode

Current scan surface:

```text
18 x 24 inch black measured cutting mat
```

Current Scan Mat Mode goals:

- Use the mat as a repeatable workbench scan area
- Detect the mat with OpenCV
- Generate annotated images with the detected mat outline
- Generate rectified mat images for cleaner analysis
- Estimate grid line visibility
- Prepare for future object measurements and OpenSCAD workflows

Test OpenCV scan-mat capture:

```bash
curl -s -X POST http://127.0.0.1:5000/api/vision/capture-scan-mat \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

Outputs are saved under:

```text
runtime/camera/mat_analysis/
```

If OpenCV is missing:

```bash
source .venv/bin/activate
pip install opencv-python-headless numpy
sudo systemctl restart jarvis-api.service
```

---

## Memory Architecture

Jarvis uses three local memory layers.

### 1. Exact Long-Term Memory

Stored in PostgreSQL and managed by:

```text
core/memory.py
```

Examples:

```text
favorite_ship = Eurodam
my wife's name = Kelly
my workplace = GM
my preferred database = SQL Server
my taco tuesday drink = Diet Coke
```

Common exact-memory questions are answered directly without LLM fallback.

### 2. Conversation History

Stored in PostgreSQL table:

```text
conversation_history
```

Managed by:

```text
core/session.py
```

Used for recent context and follow-up awareness.

### 3. Semantic Memory

Stored in PostgreSQL with pgvector and managed by:

```text
core/semantic_memory.py
```

Embedding model:

```text
models/embeddings/all-MiniLM-L6-v2
```

The embedding model is local/offline. No Hugging Face token or external API is required.

Current normalized categories:

```text
cruise
hardware
preference
project
test
work
```

---

## Project Structure

```text
jarvis/
├── api.py
├── main.py
├── testbrain.py
├── audio/
│   ├── listen.py
│   └── speak.py
├── core/
│   ├── brain.py
│   ├── context.py
│   ├── db.py
│   ├── llm.py
│   ├── memory.py
│   ├── router.py
│   ├── semantic_memory.py
│   └── session.py
├── skills/
│   ├── brain_status_skill.py
│   ├── camera_skill.py
│   ├── chat_skill.py
│   ├── dashboard_status_skill.py
│   ├── device_status_skill.py
│   ├── docs_skill.py
│   ├── health_skill.py
│   ├── help_skill.py
│   ├── llama_cpp_skill.py
│   ├── llm_skill.py
│   ├── model_runtime.py
│   ├── ollama_skill.py
│   ├── runtime_skill.py
│   ├── scan_mat_skill.py
│   ├── semantic_memory_skill.py
│   ├── system_skill.py
│   ├── time_skill.py
│   ├── version_skill.py
│   └── vision_skill.py
├── scripts/
│   ├── jarvis-status.sh
│   ├── jarvis-restart.sh
│   ├── jarvis-smoke-test.sh
│   ├── voice_test.sh
│   └── start_jarvis_llama_server.sh
├── tools/
├── docs/
├── models/
├── benchmarks/
├── runtime/
│   └── camera/        # local snapshots, ignored by git
└── ui-app/
```

---

## Current Roadmap

Recommended next order:

1. Stabilize Scan Mat Mode backend detection.
2. Wire `/api/vision/capture-scan-mat` into Vision Lab UI.
3. Add annotated/rectified scan preview in the UI.
4. Add a one-click Capture + Analyze Current View flow.
5. Add scan history and saved object notes.
6. Add measurement calibration from the mat grid.
7. Add OpenSCAD starter generation for scanned parts.
8. Add optional camera-position/gimbal automation later.
9. Convert React UI to a service.

---

## Notes

Jarvis is intentionally local-first.

Current design principles:

- Keep inference local when possible.
- Keep images local under `runtime/camera/`.
- Do not identify people in vision prompts.
- Treat camera movement as manual until a safe gimbal-control path exists.
- Build reliable assistant/workbench workflows before adding automation.
