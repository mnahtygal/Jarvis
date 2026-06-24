# Jarvis Services Checkpoint

Date: 2026-06-24
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Status: service cleanup in progress

## Summary

This checkpoint captures the cleanup step after local voice, camera, and vision were proven working.

The goal is to reduce the number of manually opened terminals and make the Jarvis stack easier to start, restart, and validate.

## Current Service Layout

```text
8080  Qwen main brain      jarvis-llama.service
8081  Gemma vision         jarvis-vision.service
5000  Flask API            jarvis-api.service
5173  React UI             manual npm run dev for now
```

The main brain, local vision model, and Flask API are now intended to run as systemd services.

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
Flask backend for voice, text, dashboard, camera, and vision routes
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

## Known Good Validation Commands

```bash
systemctl status jarvis-llama.service --no-pager
systemctl status jarvis-vision.service --no-pager
systemctl status jarvis-api.service --no-pager

curl -m 3 -s http://127.0.0.1:8080/health
curl -m 3 -s http://127.0.0.1:8081/health
curl -m 3 -s http://127.0.0.1:5000/health
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
1. Pull this checkpoint and scripts.
2. chmod the scripts executable.
3. Run jarvis-status.
4. Run jarvis-smoke-test.
5. Add vision status to the dashboard.
6. Later, convert React UI to a service.
```
