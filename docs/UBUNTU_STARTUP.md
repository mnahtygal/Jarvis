# Ubuntu Startup On Thor

Last updated: 2026-07-03

This document describes how Jarvis starts on the Ubuntu environment used by Thor.

## Purpose

The startup system turns Thor into a repeatable local AI workstation. It starts Jarvis services, checks core endpoints, opens the workspace, and leaves browser session restoration to Firefox.

## Startup Diagram

```text
Ubuntu login
  |
  v
~/.config/autostart/thor-jarvis-startup.desktop
  |
  v
~/jarvis/scripts/startup.sh
  |
  v
~/jarvis/core/boot/boot-v3.sh
  |
  +--> ~/jarvis/scripts/start-jarvis.sh
  |      |
  |      +--> llama.cpp text server :8080
  |      +--> llama.cpp vision server :8081
  |      +--> Flask API :5000
  |      +--> React/Vite UI :5173
  |
  +--> wait for UI
  +--> check UI, text LLM, vision LLM
  +--> show running llama-server processes
  +--> show uptime, memory, disk
  +--> open VS Code
  +--> skip Firefox launch
```

## Autostart Desktop Entry

Thor uses an Ubuntu autostart desktop entry:

```text
~/.config/autostart/thor-jarvis-startup.desktop
```

Expected purpose:

```text
Run ~/jarvis/scripts/startup.sh when the desktop session starts.
```

The exact desktop-entry file lives outside the repository in the user's Ubuntu profile.

## startup.sh

Repository path:

```text
scripts/startup.sh
```

Purpose:

```text
Launch the Boot V3 sequence.
```

Current behavior:

```bash
bash "$HOME/jarvis/core/boot/boot-v3.sh"
```

## boot-v3.sh

Repository path:

```text
core/boot/boot-v3.sh
```

Purpose:

- print the Thor AI Workstation banner
- start Jarvis services
- run service checks
- report running models
- report system resources
- open VS Code
- intentionally skip Firefox launch
- log boot output to `~/jarvis/logs/boot-v3.log`

Boot V3 does not launch Firefox.

Why:

- Firefox already restores its own previous session.
- Launching Firefox from boot scripts can create duplicate windows.
- Browser state belongs to Firefox, not the Jarvis boot script.
- Boot V3 should focus on services, checks, and workspace readiness.

Current Boot V3 message:

```text
Firefox launch skipped - session restore handles pinned tabs
```

## start-jarvis.sh

Repository path:

```text
scripts/start-jarvis.sh
```

Purpose:

Start the local Jarvis service stack if ports are free.

Current startup targets:

| Port | Service | Purpose |
| --- | --- | --- |
| `8080` | Qwen3 llama.cpp server | text brain |
| `8081` | GemmaVision llama.cpp server | vision model |
| `5000` | Flask API | backend routes |
| `5173` | Vite dev server | React UI |

Logs are written under `/tmp/` by `nohup`.

## Jarvis CLI

Repository path:

```text
scripts/jarvis
```

Common commands:

| Command | Purpose |
| --- | --- |
| `jarvis startup` | Run full Thor startup |
| `jarvis boot` | Alias for Boot V3 startup |
| `jarvis start` | Start Jarvis services |
| `jarvis status` | Run health checks |
| `jarvis restart` | Stop then run startup |
| `jarvis logs` | Follow startup log |
| `jarvis edit` | Open VS Code |
| `jarvis ui` | Open UI in Firefox |

## VS Code Startup

Boot V3 opens VS Code to:

```text
~/jarvis
```

It checks for an existing VS Code process targeting the repo first. If VS Code is already running, Boot V3 reports that instead of opening another workspace.

## Firefox Session Restore

Boot V3 intentionally does not open Firefox. Firefox should restore pinned tabs and previous windows using its own session restore.

If the UI is not visible after boot:

1. Confirm the UI is running at `http://localhost:5173`.
2. Open Firefox manually if session restore did not restore the UI.
3. Do not add Firefox launch back into Boot V3 unless the startup design changes.

## Health Checks

Useful checks:

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:5000/api/status/dashboard
```

CLI checks:

```bash
jarvis status
./scripts/jarvis-status.sh
./scripts/jarvis-smoke-test.sh
```

## Running Services And Ports

| Port | Expected process |
| --- | --- |
| `8080` | llama.cpp text server |
| `8081` | llama.cpp vision server |
| `5000` | Flask API |
| `5173` | Vite UI |

Check ports:

```bash
ss -ltn
```

Check llama processes:

```bash
pgrep -af "llama-server"
```

## Troubleshooting

### UI does not respond

```bash
curl http://localhost:5173
jarvis logs
```

Then restart the UI or startup flow as appropriate.

### API is offline

```bash
curl http://127.0.0.1:5000/health
cd ~/jarvis
source .venv/bin/activate
python api.py
```

### Text or vision model is offline

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8081/health
pgrep -af "llama-server"
```

Use:

```bash
./scripts/start-jarvis.sh
```

### Device status is not ready

Check:

- Dell dock power
- Samson Q2U USB/audio visibility
- Insta360 Link visibility
- `/dev/video*`
- PipeWire source status

Dashboard device status is available through:

```bash
curl http://127.0.0.1:5000/api/status/devices
```

