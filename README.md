# Jarvis

Jarvis is a local-first AI engineering assistant running on an NVIDIA Jetson
AGX Thor. It combines local language and vision models, voice, persistent
memory, camera workflows, and workshop tools without requiring cloud services.

## Current Status

- Current phase: Phase 2, Maker & Workshop Assistant
- Current milestone: calibrated automatic object measurement and validation
- Vision Lab multi-camera and camera-role foundations are complete
- Scan Mat capture, detection, calibration, and raw/annotated/rectified artifacts are stable foundations
- Measurement analysis and UI foundations exist; automatic object isolation,
  overlays, and accuracy validation remain active work

## Runtime Architecture

| Service | Implementation | Address |
| --- | --- | --- |
| UI | React/Vite | `http://localhost:5173` |
| API | Flask | `http://127.0.0.1:5000` |
| Text model | Qwen3 30B via llama.cpp | `http://127.0.0.1:8080` |
| Vision model | Gemma 3 4B Vision via llama.cpp | `http://127.0.0.1:8081` |
| Memory | PostgreSQL + pgvector | local database |

Camera devices are selected by role and resolved dynamically from their V4L2
names. The Logitech HD Pro Webcam C920 is the fixed `workbench` camera; the
Insta360 Link is the `face` camera. `/dev/video*` paths may change after a
restart and are never permanent role assignments.

Voice input prefers the Samson Q2U, resolved by its stable PipeWire device
name. Webcam microphones are not preferred.

## Vision Lab

Vision Lab supports camera-role selection, workshop prompts, and Scan Mat
analysis on a 24 × 18 inch (609.6 × 457.2 mm) mat. A successful scan preserves:

- raw camera capture
- annotated OpenCV detection
- rectified top-down image
- calibration and diagnostic metadata

Object-on-mat, measurement-helper, OCR, and 3D-print inspection prompts are
analysis aids. They do not imply calibrated automatic measurement.

## Service Commands

```bash
jarvis start
jarvis stop
jarvis restart
jarvis status
```

`jarvis restart` reloads Flask API and Vite UI source while preserving healthy
text and vision model processes. API startup must pass `GET /health`; the
camera-role surface is verified with `GET /api/cameras`. The API PID and log are
stored at `/tmp/jarvis-api.pid` and `/tmp/jarvis-api.log`.

## Repository Layout

```text
api.py       Flask API entry point
core/        Brain, routing, memory, camera/audio resolution, calibration
skills/      Vision, Scan Mat, measurement, model, and status capabilities
ui-app/      React/Vite dashboard
scripts/     Startup, restart, status, and operational helpers
hardware/    OpenSCAD sources, STL revisions, and hardware notes
docs/        Current, operational, design, and historical documentation
```

## Documentation

Start with the [documentation index](docs/README.md), then use:

- [Current architecture](docs/ARCHITECTURE.md)
- [Vision and Scan Mat](docs/VISION.md)
- [API reference](docs/API.md)
- [Ubuntu startup and service lifecycle](docs/UBUNTU_STARTUP.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Roadmap](ROADMAP.md)
- [Version history](VERSION.md)
