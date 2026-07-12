# Jarvis API/UI Dashboard Checkpoint

> **Historical checkpoint — current behavior may differ.** See the
> [documentation index](README.md), [API](API.md), and
> [architecture](ARCHITECTURE.md).

Date: 2026-06-11
Platform: NVIDIA Thor
Status: Functional checkpoint

---

## Summary

Jarvis now has a working API-backed operations dashboard.

This checkpoint captures the state after completing the first API/UI dashboard pass, validating the live backend endpoints, rendering the React dashboard, and confirming that voice input from the UI reaches the Jarvis brain.

---

## Completed Work

### Dashboard Backend Service

Added a structured dashboard status service:

```text
skills/dashboard_status_skill.py
```

The service returns structured JSON-ready status data for:

- Brain readiness
- Active model/runtime
- PostgreSQL exact memory
- pgvector semantic memory
- Recent conversation history
- Local embedding model status
- MartyBench latest run and score

---

### Dashboard API Endpoints

Added REST endpoints to `api.py`:

```text
/api/status/dashboard
/api/status/brain
/api/status/model
/api/status/memory
/api/status/martybench
```

Validated with curl and `python3 -m json.tool`.

Observed working values:

```text
Brain: READY
Runtime: Thor / Qwen3 30B / llama.cpp
PostgreSQL: online
Exact memory: 9 facts
Semantic memory: 14 rows
LLM endpoint: online, model=Qwen3-30B-A3B-Q4_K_M.gguf
MartyBench latest: conflict / 34 of 35 / Pass
```

---

### React Dashboard UI

Updated the Vite/React UI under:

```text
ui-app/src/JarvisUI.tsx
```

The dashboard now displays live cards for:

- Brain status
- Active model
- Memory status
- MartyBench score
- Last topic
- LLM endpoint
- MartyBench run ID

The UI consumes:

```text
/api/status/dashboard
```

and refreshes periodically.

---

### Component Split Started

Created reusable component:

```text
ui-app/src/components/StatusCard.tsx
```

This begins breaking the large `JarvisUI.tsx` file into safer, smaller UI components.

Future split targets:

```text
ui-app/src/components/GlowRing.tsx
ui-app/src/components/ControlButton.tsx
ui-app/src/components/ActivityLog.tsx
ui-app/src/hooks/useDashboardStatus.ts
ui-app/src/types/dashboard.ts
```

---

## Voice Smoke Test From UI

After the Dell dock power issue was resolved, the Samson Q2U microphone worked through the UI Listen button.

Validated behavior:

```text
[x] UI Listen button works
[x] Samson Q2U audio is captured
[x] Speech-to-text runs
[x] Voice input reaches /ask
[x] Jarvis routes heard text into the brain
[x] Jarvis response returns to the UI activity log
```

Example heard inputs:

```text
Turn on the camera.
write me a dashboard to track the
What's the weather for today?
```

The recognition is not perfect yet, but the end-to-end UI voice path is functional.

---

## Hardware Notes

Thor is using a Dell docking station mainly to solve USB-A port availability for Jarvis peripherals.

Important notes:

```text
Power USB-C Port:
- Dedicated power input only

Host/Data USB-C Port:
- Dell Dock connects here

Camera:
- Insta360 Link
- Device: /dev/video1
- Test: ffplay /dev/video1

Microphone:
- Samson Q2U
- Use PipeWire for playback testing

Audio Test:
- timeout 5 pw-record test.wav
- pw-play test.wav

Important:
- pw-play works for playback
- Raw ALSA tests may not route correctly
```

Dock power must be connected. If the dock loses power, Ubuntu may remember the Samson Q2U as the configured default source while the actual USB device disappears.

---

## Known UI Polish Items

Deferred intentionally:

```text
[ ] Reduce duplicate startup log messages
[ ] Add last refreshed timestamp
[ ] Clean Memory card wording
[ ] Continue component split
[ ] Add audio/device status card later
[ ] Add model switch controls later, after safe UX design
```

---

## Deferred Roadmap

Still intentionally later:

```text
1. Continue API/UI dashboard polish
2. Continue component split
3. Add audio/device status card
4. Voice integration pass
5. Camera/vision pass
```

Voice and camera remain last, even though the hardware is now working.

---

## Current Checkpoint

```text
[x] Dynamic model identity complete
[x] Safe model switching complete
[x] Qwen3 default preserved
[x] DeepSeek selectable
[x] ask_jarvis helper complete
[x] API dashboard backend complete
[x] Dashboard API endpoints complete
[x] React dashboard functional
[x] UI build/run validated locally
[x] Voice UI smoke test passed
[x] Working tree was clean before documentation checkpoint
```

Jarvis now has a real operational dashboard connected to live backend status.
