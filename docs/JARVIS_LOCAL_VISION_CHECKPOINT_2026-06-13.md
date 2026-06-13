# Jarvis Local Vision Checkpoint

Date: 2026-06-13
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Status: complete, API validated, UI validated

## Summary

This checkpoint documents the first complete local vision pass for Jarvis.

Jarvis can now capture a camera snapshot, preview it in the React dashboard, analyze the latest image with a separate local multimodal model, and return the description to the activity log.

The vision path is fully local and runs independently from the main Jarvis brain.

## Runtime Architecture

```text
Port 8080: Qwen3 30B through llama.cpp
Purpose: main Jarvis brain and text reasoning

Port 8081: Gemma 3 4B multimodal through llama.cpp
Purpose: image understanding and scene description

Port 5000: Flask API
Purpose: Jarvis backend, camera, voice, dashboard, and vision routes

Port 5173 or 5174: React UI
Purpose: Jarvis Command Center
```

Keeping the models on separate ports prevents camera analysis from replacing or interrupting the main Jarvis model.

## Vision Model

The first local vision model is:

```text
ggml-org/gemma-3-4b-it-qat-GGUF
```

llama.cpp reports the model capabilities as:

```text
completion
multimodal
```

The model was started with the llama.cpp built-in vision option:

```bash
cd ~/llama.cpp

./build/bin/llama-server \
  --vision-gemma-4b-default \
  --host 127.0.0.1 \
  --port 8081
```

## Vision Server Validation

Health check:

```bash
curl -s http://127.0.0.1:8081/health
```

Expected:

```text
status: ok
```

Model check:

```bash
curl -s http://127.0.0.1:8081/v1/models | python3 -m json.tool
```

Expected model:

```text
ggml-org/gemma-3-4b-it-qat-GGUF
```

Expected capability:

```text
multimodal
```

## Vision Analysis Skill

Added:

```text
skills/vision_skill.py
```

The skill:

- Reads the latest local JPEG snapshot
- Base64-encodes the image in Python
- Sends the image to the local vision server
- Uses the OpenAI-compatible `/v1/chat/completions` endpoint
- Returns the model description, usage, and timing details
- Reports clear errors when the vision server is offline
- Avoids face identification requests

Default vision endpoint:

```text
http://127.0.0.1:8081/v1/chat/completions
```

Default model:

```text
ggml-org/gemma-3-4b-it-qat-GGUF
```

## Camera Analysis API

Added endpoint:

```text
POST /api/camera/analyze
```

The endpoint:

- Selects the newest snapshot under `runtime/camera/`
- Uses the local Gemma vision server
- Accepts an optional custom prompt
- Returns a local scene description

Example request:

```bash
curl -s -X POST http://127.0.0.1:5000/api/camera/analyze \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

Expected successful response:

```text
ok: true
model: ggml-org/gemma-3-4b-it-qat-GGUF
description: local image description
image_name: latest snapshot file
```

## React Vision Controls

Updated:

```text
ui-app/src/JarvisUI.tsx
```

The dashboard now includes:

```text
Camera
Analyze Snapshot
```

The Analyze Snapshot button:

- Enables when a snapshot is available
- Calls `POST /api/camera/analyze`
- Shows `Analyzing...` while the model is working
- Prevents overlapping voice, camera, text, and vision actions
- Writes the vision result into the activity log
- Reports when the vision server on port 8081 is offline

## End-to-End Vision Flow

```text
Insta360 Link
  -> /dev/video0
  -> ffmpeg snapshot capture
  -> runtime/camera JPEG
  -> dashboard preview
  -> POST /api/camera/analyze
  -> Gemma 3 4B vision server on port 8081
  -> scene description
  -> dashboard activity log
```

## Validation Results

The following checks passed:

```text
[x] Gemma vision server started on port 8081
[x] Vision server health returned ok
[x] llama.cpp reported multimodal capability
[x] Direct Python vision test returned a scene description
[x] Flask camera analyze endpoint returned ok: true
[x] Latest snapshot was correctly selected
[x] Vision description appeared in the React activity log
[x] Analyze Snapshot button worked
[x] Camera preview remained visible
[x] Qwen3 main brain remained active on port 8080
[x] React UI build passed
[x] Live UI test passed
```

## Performance Observed

A successful vision request completed locally in only a few seconds.

Observed behavior included:

```text
prompt processing: about 2 seconds
description generation: about 2 to 3 seconds
```

This is fast enough for an on-demand Analyze Snapshot button.

## Known Limitations

The 4B vision model can misclassify some objects or visible text. This is normal for a small local multimodal model.

Current limitations:

```text
[ ] No automatic continuous video analysis
[ ] No object tracking
[ ] No person identification
[ ] No vision memory storage
[ ] No voice question about the current image
[ ] No custom prompt field in the UI
[ ] No vision status card in the dashboard
[ ] Vision server is not yet managed by systemd
```

## Safety and Privacy

The current design keeps image processing local on Thor.

```text
No cloud API
No external image upload
No API tokens required
No face identification
```

Snapshots remain under:

```text
runtime/camera/
```

This directory is excluded from Git.

## Known Good Startup Sequence

### Main Jarvis Brain

```bash
sudo systemctl start jarvis-llama.service
curl -s http://127.0.0.1:8080/health
```

### Vision Server

```bash
cd ~/llama.cpp

./build/bin/llama-server \
  --vision-gemma-4b-default \
  --host 127.0.0.1 \
  --port 8081
```

### Flask API

```bash
cd ~/jarvis
source .venv/bin/activate
python api.py
```

### React UI

```bash
cd ~/jarvis/ui-app
npm run build
npm run dev
```

## Current Known Good State

```text
[x] Main Qwen3 brain online
[x] Local Gemma vision model online
[x] Voice capture working
[x] Camera snapshot working
[x] Snapshot preview working
[x] Local vision analysis working
[x] Vision result displayed in UI
[x] PostgreSQL and pgvector memory online
[x] Device dashboard READY
[x] MartyBench passing
```

## Commit Trail

```text
8ac7da7  Add local vision analysis skill
153a4e0  Add camera vision analysis endpoint
c180727  Add analyze snapshot button
```

## Recommended Pause Point

This is a stable feature checkpoint. Stop adding new features until this state is pulled, regression-tested, and preserved cleanly.

Recommended next session priorities:

```text
1. Add a managed startup path for the vision server.
2. Add vision-server health to the dashboard.
3. Add a repeatable vision regression script.
4. Only then consider custom image questions or voice-to-vision integration.
```

## Final Note

Jarvis now has a complete local multimodal workflow while preserving the main text model as the primary brain.

```text
Voice + Camera + Snapshot Preview + Local Vision
```

This is a major project milestone and a strong stopping point.
