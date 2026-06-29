# Jarvis Services Checkpoint

Date: 2026-06-24
Last updated: 2026-06-28
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Status: service cleanup complete, dashboard polish complete, scan-mat backend added

## Summary

This checkpoint captures the cleanup step after local voice, camera, and vision were proven working.

The goal was to reduce the number of manually opened terminals and make the Jarvis stack easier to start, restart, validate, and read from the dashboard.

Since the original service checkpoint, Jarvis has also gained Vision Lab scan modes, a capture-and-analyze endpoint, and an OpenCV scan-mat analysis endpoint.

## Current Service Layout

```text
8080  Qwen main brain      jarvis-llama.service
8081  Gemma vision         jarvis-vision.service
5000  Flask API            jarvis-api.service
5173  React UI             manual npm run dev for now
```

The main brain, local vision model, and Flask API now run as systemd services.

## Service Responsibilities

### jarvis-llama.service

Purpose:

```text
Main Jarvis text brain through llama.cpp
```

Health check:

```bash
curl -m 3 -s http://127.0.0.1:8080/health
```

### jarvis-vision.service

Purpose:

```text
Local Gemma multimodal vision server through llama.cpp
```

Health check:

```bash
curl -m 3 -s http://127.0.0.1:8081/health
```

### jarvis-api.service

Purpose:

```text
Flask backend for voice, text, dashboard, camera, vision, and scan-mat routes
```

Health check:

```bash
curl -m 3 -s http://127.0.0.1:5000/health
```

## Helper Scripts Added

### scripts/jarvis-status.sh

Checks:

```text
- jarvis-llama.service
- jarvis-vision.service
- jarvis-api.service
- 8080 health
- 8081 health
- 5000 health
- dashboard API health
- listening Jarvis ports
- git status
```

Usage:

```bash
cd ~/jarvis
./scripts/jarvis-status.sh
```

### scripts/jarvis-restart.sh

Restarts:

```text
- jarvis-llama.service
- jarvis-vision.service
- jarvis-api.service
```

Then runs the status helper if it is executable.

Usage:

```bash
cd ~/jarvis
./scripts/jarvis-restart.sh
```

### scripts/jarvis-smoke-test.sh

Checks the end-to-end working path:

```text
- Qwen brain health
- Gemma vision health
- Flask API health
- dashboard API
- camera snapshot
- vision analyze latest snapshot
- typed brain status command
```

Usage:

```bash
cd ~/jarvis
./scripts/jarvis-smoke-test.sh
```

Future improvement: extend the smoke test to include `/api/camera/capture-analyze` and `/api/vision/capture-scan-mat`.

## First-Time Permission Fix

After pulling the scripts, make them executable:

```bash
cd ~/jarvis
chmod +x scripts/jarvis-status.sh scripts/jarvis-restart.sh scripts/jarvis-smoke-test.sh
```

Optional convenience links:

```bash
sudo ln -sf /home/mnahtygal/jarvis/scripts/jarvis-status.sh /usr/local/bin/jarvis-status
sudo ln -sf /home/mnahtygal/jarvis/scripts/jarvis-restart.sh /usr/local/bin/jarvis-restart
sudo ln -sf /home/mnahtygal/jarvis/scripts/jarvis-smoke-test.sh /usr/local/bin/jarvis-smoke-test
```

Then these commands work from anywhere:

```bash
jarvis-status
jarvis-restart
jarvis-smoke-test
```

## Dashboard Updates

The dashboard includes a dedicated Vision status card.

Expected top cards:

```text
Brain        READY
Active Model Qwen3 30B
Vision       READY
Memory       online
Devices      READY
MartyBench   passing
```

Vision dashboard data is supplied by:

```text
skills/dashboard_status_skill.py
```

The Vision card shows:

```text
- online/offline status
- Gemma vision model label
- llama.cpp runtime
- Thor host
- port 8081
```

## Vision Lab / Scan Mat Additions

Vision Lab now supports multiple scan prompts:

```text
General Scan
Object on Mat
Measurement Helper
Read Text / Label
3D Print Inspect
Jet Ski Part Scan
Workbench Status
```

Camera/vision API endpoints now include:

```text
POST /api/camera/snapshot
GET  /api/camera/latest
POST /api/camera/analyze
POST /api/camera/capture-analyze
POST /api/vision/scan-mat
POST /api/vision/capture-scan-mat
```

OpenCV scan-mat analysis lives in:

```text
skills/scan_mat_skill.py
```

Generated OpenCV outputs are local-only under:

```text
runtime/camera/mat_analysis/
```

Important behavior:

```text
Capture Current View = capture whatever the Insta360 is currently looking at
```

The app does not yet automatically tilt the Insta360 down to the mat.

## Activity Log Polish

The Activity Log was updated to make long entries easier to read.

Updated file:

```text
ui-app/src/components/ActivityLog.tsx
```

The log now formats entries by type:

```text
- Vision
- Camera
- You
- Jarvis
- System
```

Improvements:

```text
[x] Colored left border by log type
[x] Clear uppercase section labels
[x] Better wrapping for long vision responses
[x] Slightly larger vision text
[x] Long model names no longer blow out the card width
[x] Camera and snapshot entries are easier to scan
```

## Known Good Validation Commands

```bash
systemctl status jarvis-llama.service --no-pager
systemctl status jarvis-vision.service --no-pager
systemctl status jarvis-api.service --no-pager

curl -m 3 -s http://127.0.0.1:8080/health
curl -m 3 -s http://127.0.0.1:8081/health
curl -m 3 -s http://127.0.0.1:5000/health
```

Scan Mat validation:

```bash
curl -s -X POST http://127.0.0.1:5000/api/vision/capture-scan-mat \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

Capture + Analyze validation:

```bash
curl -s -X POST http://127.0.0.1:5000/api/camera/capture-analyze \
  -H "Content-Type: application/json" \
  -d '{"mode":"object","prompt":"Do not identify people. Describe the main object on the measurement mat."}' | python3 -m json.tool
```

## Current Known Good UI Validation

```text
[x] Brain READY
[x] Active Model Qwen3 30B
[x] Vision READY on port 8081
[x] Memory online
[x] Devices READY
[x] MartyBench 34/35
[x] Camera preview working
[x] Analyze Snapshot working
[x] Activity Log receiving cleanly formatted vision output
[x] Vision Lab navigation present
[x] Scan mode selector present
```

## Remaining Manual Step

The React UI is still manual for now:

```bash
cd ~/jarvis/ui-app
npm run dev
```

Future improvement:

```text
[ ] Add jarvis-ui.service
```

## Recommended Next Steps

```text
1. Pull latest docs/code.
2. Ensure OpenCV dependencies are installed if testing scan mat.
3. Restart jarvis-api.service.
4. Run jarvis-status.
5. Run jarvis-smoke-test.
6. Test /api/vision/capture-scan-mat.
7. Wire OpenCV outputs into Vision Lab UI.
8. Later, convert React UI to a service.
```

## Commit Trail

```text
43a45e4  Add Jarvis status helper script
286b9f6  Add Jarvis restart helper script
7464cdf  Add Jarvis smoke test script
5989826  Add Jarvis services checkpoint doc
82128ac  Add vision status to dashboard data
bb4b0d5  Add vision dashboard type
a85bec8  Fix dashboard semantic memory import
d1e210c  Add vision status card to UI
d9254e1  Improve activity log formatting
83a56b7  Add Vision Lab navigation and scan modes
74a64d6  Add capture and analyze camera endpoint
6e42e7c  Add Scan Mat Mode checkpoint doc
1dcf7dc  Add OpenCV scan mat analysis skill
4427be5  Add scan mat analysis API endpoint
```
