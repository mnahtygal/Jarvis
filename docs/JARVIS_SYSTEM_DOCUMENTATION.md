# Jarvis System Documentation

Last updated: 2026-06-28
Project: Jarvis Local AI Assistant
Primary host: NVIDIA Jetson AGX Thor Developer Kit (`y-thor`)

---

## Project Overview

Jarvis is Marty's local-first AI assistant platform. It runs primarily on local hardware with persistent memory, local language model inference, local vision inference, voice input/output, a Flask API, and a React dashboard.

Jarvis began on the NVIDIA Jetson AGX Xavier and now runs primarily on the NVIDIA Jetson AGX Thor Developer Kit.

The project has evolved from a local chatbot into a local multimodal assistant and AI workbench for:

```text
- conversation
- memory
- voice
- camera snapshots
- local image understanding
- scan-mat / object inspection
- future maker-lab workflows
```

---

## Current Platform

```text
Host: y-thor
Hardware: NVIDIA Jetson AGX Thor Developer Kit
Architecture: ARM64
Operating System: Ubuntu 24.04.4 LTS
Memory: 128 GB
CUDA: 13.0
Inference engine: llama.cpp
Database: PostgreSQL 16
Vector extension: pgvector
Camera: Insta360 Link
Microphone: Samson Q2U
Main repo: git@github.com:mnahtygal/Jarvis.git
```

---

## Current Service Layout

```text
8080  Qwen3 main brain      jarvis-llama.service
8081  Gemma vision          jarvis-vision.service
5000  Flask API             jarvis-api.service
5173  React UI              manual npm run dev for now
```

The backend services are managed by systemd. The React UI is still manually started:

```bash
cd ~/jarvis/ui-app
npm run build
npm run dev
```

---

## Runtime Models

### Main Brain Model

```text
Qwen3-30B-A3B-Q4_K_M.gguf
```

Served by llama.cpp on port 8080.

### Vision Model

```text
ggml-org/gemma-3-4b-it-qat-GGUF
```

Served by llama.cpp on port 8081.

---

## Current Architecture

### Text / Brain Path

```text
User / UI / API / Voice
   ↓
Flask API or CLI
   ↓
core.brain.think()
   ↓
core.router.route()
   ↓
Skill handler, exact-memory answer, semantic memory, or LLM fallback
   ↓
core.context.build_messages()
   ↓
llama.cpp / Qwen3 30B
   ↓
Jarvis response
```

### Camera / Vision Path

```text
Insta360 Link camera
   ↓
skills.camera_skill.capture_snapshot()
   ↓
runtime/camera/snapshot_*.jpg
   ↓
skills.vision_skill.analyze_image()
   ↓
Gemma vision model on port 8081
   ↓
Activity Log / Vision Lab result
```

### Scan Mat / OpenCV Path

```text
Camera current view
   ↓
Snapshot capture
   ↓
skills.scan_mat_skill.analyze_scan_mat()
   ↓
Mat detection / annotated image / rectified image / grid metadata
   ↓
Future measurement and maker-lab workflows
```

---

## Current Flask API Surface

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

## React UI

Current UI app:

```text
ui-app/
```

Current navigation:

```text
Home | Vision Lab | Maker Lab | Memory | System
```

### Home

Main dashboard, voice, camera, quick commands, status cards, and activity log.

### Vision Lab

Camera snapshot workflows, scan modes, scan-mat workflow, and image analysis.

Current scan modes:

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

Jarvis does not yet automatically tilt the camera down to the mat.

### Maker Lab / Memory / System

These pages are placeholders for upcoming maker, memory-review, and system-control workflows.

---

## Scan Mat Mode

Current hardware:

```text
Camera: Insta360 Link
Mount: top of monitor
Scan surface: 18 x 24 inch black measured cutting mat
```

Current OpenCV skill:

```text
skills/scan_mat_skill.py
```

Current output directory:

```text
runtime/camera/mat_analysis/
```

Current outputs:

```text
*_mat_annotated.jpg
*_mat_rectified.jpg
```

Current capabilities:

```text
[x] Capture current camera view
[x] Analyze latest snapshot with Gemma vision
[x] Capture + analyze in one backend call
[x] Detect large four-corner mat-like contour with OpenCV
[x] Annotate detected mat corners
[x] Perspective-rectify mat image
[x] Estimate grid-line visibility metadata
```

Current limitations:

```text
[ ] No automatic Insta360 gimbal control
[ ] No UI display for annotated/rectified OpenCV output yet
[ ] No object bounding boxes yet
[ ] No calibrated real-world measurements yet
[ ] No saved scan history yet
[ ] No OpenSCAD generation from scan yet
```

---

## Memory Architecture

Jarvis uses three local memory layers.

```text
1. Exact long-term memory in PostgreSQL
2. Conversation history in PostgreSQL
3. Semantic memory in PostgreSQL with pgvector
```

Local embedding model:

```text
models/embeddings/all-MiniLM-L6-v2
```

Semantic memory runs offline and does not require an external token.

Normalized semantic categories:

```text
cruise
hardware
preference
project
test
work
```

---

## Core Components

| Component | Purpose |
|---|---|
| `api.py` | Flask API for text, voice, dashboard, camera, vision, and scan-mat endpoints. |
| `core/brain.py` | Main thinking entry point. |
| `core/router.py` | Intent routing and LLM fallback. |
| `core/context.py` | Builds LLM context from memory/history. |
| `core/memory.py` | PostgreSQL exact memory. |
| `core/session.py` | Conversation history/session state. |
| `core/semantic_memory.py` | pgvector semantic memory. |
| `skills/camera_skill.py` | Camera snapshot capture. |
| `skills/vision_skill.py` | Local Gemma image analysis. |
| `skills/scan_mat_skill.py` | OpenCV scan-mat analysis. |
| `skills/dashboard_status_skill.py` | Dashboard status payload. |
| `skills/device_status_skill.py` | USB/audio/video device status. |
| `skills/model_runtime.py` | Active model name/runtime status. |
| `audio/listen.py` | Voice input. |
| `audio/speak.py` | Voice output. |
| `ui-app/` | React/Vite UI. |

---

## Helper Scripts

```text
scripts/jarvis-status.sh
scripts/jarvis-restart.sh
scripts/jarvis-smoke-test.sh
scripts/voice_test.sh
```

### jarvis-status

Checks services, health endpoints, listening ports, and git status.

```bash
cd ~/jarvis
./scripts/jarvis-status.sh
```

### jarvis-restart

Restarts the backend services.

```bash
cd ~/jarvis
./scripts/jarvis-restart.sh
```

### jarvis-smoke-test

Checks brain health, vision health, API health, dashboard API, camera snapshot, vision analysis, and a text command.

```bash
cd ~/jarvis
./scripts/jarvis-smoke-test.sh
```

---

## Validation Commands

Backend service checks:

```bash
systemctl status jarvis-llama.service --no-pager
systemctl status jarvis-vision.service --no-pager
systemctl status jarvis-api.service --no-pager
```

Health checks:

```bash
curl -m 3 -s http://127.0.0.1:8080/health
curl -m 3 -s http://127.0.0.1:8081/health
curl -m 3 -s http://127.0.0.1:5000/health
```

Capture + analyze:

```bash
curl -s -X POST http://127.0.0.1:5000/api/camera/capture-analyze \
  -H "Content-Type: application/json" \
  -d '{"mode":"object","prompt":"Describe the main object on the measurement mat."}' | python3 -m json.tool
```

OpenCV scan mat:

```bash
curl -s -X POST http://127.0.0.1:5000/api/vision/capture-scan-mat \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

---

## Python Environment

Current virtual environment:

```text
~/jarvis/.venv
```

Activate:

```bash
cd ~/jarvis
source .venv/bin/activate
```

Important packages:

```text
flask
flask-cors
requests
psycopg2-binary
python-dotenv
openai
numpy
psutil
opencv-python-headless
```

If testing scan-mat OpenCV support:

```bash
source .venv/bin/activate
pip install opencv-python-headless numpy
sudo systemctl restart jarvis-api.service
```

---

## Main Repo Structure

```text
jarvis/
├── api.py
├── main.py
├── testbrain.py
├── audio/
├── core/
├── skills/
│   ├── camera_skill.py
│   ├── dashboard_status_skill.py
│   ├── device_status_skill.py
│   ├── scan_mat_skill.py
│   └── vision_skill.py
├── scripts/
│   ├── jarvis-status.sh
│   ├── jarvis-restart.sh
│   └── jarvis-smoke-test.sh
├── docs/
├── models/
├── benchmarks/
├── runtime/
│   └── camera/
└── ui-app/
```

`runtime/camera/` is local runtime output and should stay out of Git.

---

## Previous Platform: Xavier

The Xavier was the original Jarvis development platform and remains useful as a historical baseline.

---

## MartyBench

MartyBench is the local benchmark concept used to evaluate Jarvis inference performance.

Current direction:

```text
- Compare Xavier vs Thor
- Compare 7B vs 30B models
- Track tokens/sec
- Track first token latency
- Track long-context stability
- Track code generation quality
- Track browser/runtime success
- Track final patch effort
```

---

## Current Priorities

Recommended next development order:

```text
1. Stabilize OpenCV scan-mat detection.
2. Wire OpenCV outputs into Vision Lab UI.
3. Add Capture + Analyze Current View button in Vision Lab.
4. Display annotated and rectified scan images.
5. Add scan history and object notes.
6. Add calibrated measurement estimates.
7. Add OpenSCAD starter generation from scans.
8. Convert React UI to a service.
9. Investigate safe Insta360 gimbal control later.
```

---

## Current System Status

Jarvis is now a local Thor-powered multimodal assistant platform with:

```text
[x] local Qwen3 30B brain
[x] local Gemma 3 4B vision
[x] PostgreSQL exact memory
[x] pgvector semantic memory
[x] voice input/output path
[x] camera snapshots
[x] Vision Lab UI
[x] service-managed backend
[x] status/restart/smoke-test scripts
[x] first OpenCV scan-mat geometry layer
```

This marks the transition from a Jetson Xavier local assistant experiment to a Jetson Thor local multimodal AI workbench.
