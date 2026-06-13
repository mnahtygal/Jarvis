# Jarvis Voice Hardening Checkpoint

Date: 2026-06-13
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Status: complete, direct test passed, UI test passed

## Summary

This checkpoint documents the first controlled Jarvis voice hardening pass.

The goal was to improve reliability without changing the broader voice architecture. The pass focused on extending the listen window, adding useful diagnostics, and creating a repeatable voice test script.

Camera and vision were intentionally left untouched.

## Completed Work

### Listen Window Increased

Updated:

```text
audio/listen.py
```

The default recording window was increased from 5 seconds to 7 seconds.

This reduces clipping for longer spoken requests while keeping the interaction short and predictable.

The value remains configurable through:

```text
JARVIS_LISTEN_SECONDS
```

### Recording Diagnostics Added

The listener now reports:

```text
recording elapsed time
recorded WAV size
recording return code
transcription elapsed time
transcribed character count
heard text
```

Example diagnostic flow:

```text
[LISTEN] Recording 7 second(s)...
[LISTEN] Recording complete: elapsed=... size=... bytes returncode=...
[LISTEN] Transcription complete: elapsed=... chars=...
[LISTEN] Heard: ...
```

These diagnostics make it easier to separate microphone, recording, and transcription issues.

### Repeatable Voice Test Script

Added:

```text
scripts/voice_test.sh
```

Default usage:

```bash
cd ~/jarvis
./scripts/voice_test.sh
```

Optional custom recording duration:

```bash
./scripts/voice_test.sh 10
```

The script automatically uses:

```text
~/jarvis/.venv/bin/python
```

This avoids accidental use of the system Python environment.

## Validation Results

The following checks passed:

```text
[x] Combined Jarvis regression check passed
[x] Direct audio/listen.py voice test passed
[x] Seven-second recording completed successfully
[x] Whisper transcription completed successfully
[x] Repeatable scripts/voice_test.sh test passed
[x] React UI build passed
[x] Flask API started successfully
[x] UI Listen button path passed
[x] Voice input reached Jarvis brain
[x] Jarvis response returned to the activity log
```

## Current Voice Path

```text
Samson Q2U
  -> PipeWire / Pulse source
  -> parec WAV capture
  -> local Whisper transcription
  -> Flask /ask endpoint
  -> Jarvis brain/router
  -> UI activity log
  -> optional spoken response
```

## Known Good Commands

### Direct Listener Test

```bash
cd ~/jarvis
source .venv/bin/activate
python audio/listen.py
```

### Repeatable Voice Test

```bash
cd ~/jarvis
./scripts/voice_test.sh
```

### Start Flask API

```bash
cd ~/jarvis
source .venv/bin/activate
python api.py
```

### Build and Run UI

```bash
cd ~/jarvis/ui-app
npm run build
npm run dev
```

## Current Known Good State

```text
[x] Samson Q2U detected
[x] PipeWire source available
[x] Voice recording works
[x] Local Whisper transcription works
[x] Seven-second listen window works
[x] Voice diagnostics visible in terminal
[x] UI Listen button works
[x] Voice request reaches Jarvis
[x] UI displays heard text and response
```

## Not Done Yet

These are intentionally still pending:

```text
[ ] Automatic silence detection
[ ] Push-to-stop or cancel listening
[ ] Heard-text preview before routing
[ ] Better retry messaging when no speech is detected
[ ] Voice diagnostics card in the dashboard
[ ] Wake-word loop hardening
[ ] Full TTS behavior review
[ ] Camera and vision integration
```

## Next Recommended Step

The next voice pass should remain incremental:

```text
1. Compare several short and long voice prompts.
2. Record examples of any clipped or misheard phrases.
3. Decide whether seven seconds is the right default.
4. Add silence-aware recording only if fixed-duration capture remains limiting.
5. Keep camera and vision disabled until voice behavior is stable.
```

## Commit Trail

```text
710e2d9  Improve voice listen timing diagnostics
e957b44  Add repeatable voice test script
```

## Final Note

This checkpoint establishes a stable voice baseline. Jarvis now has a longer listen window, useful recording diagnostics, a repeatable voice test, and a confirmed end-to-end UI voice path.
