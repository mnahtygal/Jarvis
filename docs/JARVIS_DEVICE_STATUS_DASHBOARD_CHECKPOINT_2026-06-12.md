# Jarvis Device Status Dashboard Checkpoint

Date: 2026-06-12
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Runtime: llama.cpp with Qwen3 30B
Status: complete, build validated, UI validated

## Summary

This checkpoint documents the completed device status dashboard pass.

Jarvis now reports local hardware readiness through the Flask API and displays that status in the React dashboard. This gives us a clean readiness layer before moving into the more fragile voice and camera work.

This pass does not enable vision yet. Camera and full vision remain later-stage work. This checkpoint only confirms that the key devices are visible and reported cleanly.

## Completed Work

### Backend Device Status Skill

Added:

```text
skills/device_status_skill.py
```

The skill checks local device readiness using standard Linux commands and device paths. It reports microphone, camera, audio backend, and a dock power reminder.

It currently tracks:

- Samson Q2U microphone
- Insta360 Link camera
- PipeWire audio backend
- expected camera path `/dev/video1`
- available `/dev/video*` entries
- Dell dock power note

### Standalone Device Status API

Added:

```text
GET /api/status/devices
```

The endpoint returns a compact readiness object with these sections:

```text
overall
ready
audio_backend
microphone
camera
dock_note
```

Expected healthy result:

```text
overall: READY
ready: true
microphone.detected: true
camera.detected: true
camera.expected_device_present: true
audio_backend: PipeWire
```

### Main Dashboard API Integration

Updated:

```text
skills/dashboard_status_skill.py
```

The main dashboard endpoint now includes a top-level devices section:

```text
GET /api/status/dashboard
```

Dashboard sections now include:

```text
brain
model
memory
martybench
devices
```

### React Dashboard Types

Updated:

```text
ui-app/src/types/dashboard.ts
```

Added:

```text
DeviceStatus
DashboardStatus.devices
```

### React Devices Card

Updated:

```text
ui-app/src/JarvisUI.tsx
```

The top dashboard row now shows five cards:

```text
Brain | Active Model | Memory | Devices | MartyBench
```

The Devices card reports:

```text
Devices
READY
Mic: Samson Q2U · Camera: Insta360 Link · PipeWire
```

Live details also show:

```text
Mic: Samson Q2U
Camera: /dev/video1
```

## Verified State

The following was confirmed from Thor after pulling and restarting the API:

```text
[x] Flask API online
[x] Dashboard API online
[x] Brain READY
[x] Qwen3 30B active through llama.cpp
[x] PostgreSQL memory online
[x] Semantic memory online
[x] Local embeddings available
[x] MartyBench latest result: 34/35 Pass
[x] Samson Q2U microphone detected
[x] Samson Q2U active through PipeWire
[x] Insta360 Link camera detected
[x] Expected camera path present
[x] React UI build passed
[x] React dashboard visually validated
```

## Validation Commands

Pull latest repo:

```bash
cd ~/jarvis
git pull
```

Restart Flask API:

```bash
cd ~/jarvis
pkill -f "python.*api.py"
source .venv/bin/activate
python api.py
```

Test standalone devices endpoint:

```bash
curl http://127.0.0.1:5000/api/status/devices | python3 -m json.tool
```

Test full dashboard endpoint:

```bash
curl http://127.0.0.1:5000/api/status/dashboard | python3 -m json.tool
```

Build React UI:

```bash
cd ~/jarvis/ui-app
npm run build
```

Run React UI:

```bash
cd ~/jarvis/ui-app
npm run dev
```

## Known Good UI State

The dashboard visually shows:

```text
API connected
Dashboard connected
Brain READY
Active Model Qwen3 30B
Memory online
Devices READY
MartyBench 34/35 Pass
```

The Devices card visually shows:

```text
READY
Mic: Samson Q2U
Camera: Insta360 Link
PipeWire
```

## Not Done Yet

These are intentionally still pending:

```text
[ ] Full voice pass hardening
[ ] Better clipped speech handling
[ ] Voice diagnostics panel or logs
[ ] Camera button enablement
[ ] Camera frame capture
[ ] Vision/image understanding pipeline
[ ] Wake/listen loop polish
```

## Next Recommended Step

Begin the first controlled voice pass:

```text
1. Keep camera disabled in UI.
2. Keep current Listen button behavior.
3. Add cleaner listen diagnostics.
4. Improve clipped speech handling.
5. Add a short repeatable voice test checklist.
6. Only after voice is stable, move to camera and vision.
```

## Commit Trail

```text
94fc4e6  Add device status skill
4a8be36  Add device status API endpoint
745f98b  Add device status dashboard types
95a91e0  Include devices in dashboard status
da6abf1  Add devices card to dashboard UI
```

## Final Note

This is an important Jarvis milestone. The dashboard now reports the local assistant stack, memory, benchmark result, and hardware readiness from one place. That gives us a stable launch point before touching voice and camera behavior.
