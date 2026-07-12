# Jarvis Camera Snapshot Checkpoint

> **Historical checkpoint — fixed `/dev/video*` mappings below are not current
> assignments.** See [Vision](VISION.md) and [API](API.md).

Date: 2026-06-13
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Status: complete, API validated, UI validated

## Summary

This checkpoint documents the first controlled camera pass for Jarvis.

Jarvis can now capture a single still image from the Insta360 Link camera through a Flask API endpoint. The React dashboard Camera button triggers the snapshot and reports the result in the activity log.

This stage does not add image understanding or vision inference. It only establishes reliable camera capture and UI control.

## Completed Work

### Camera Snapshot Skill

Added:

```text
skills/camera_skill.py
```

The camera skill:

- Uses the configured camera device from `JARVIS_CAMERA_DEVICE`
- Defaults to `/dev/video0`
- Captures one JPEG frame with ffmpeg
- Uses MJPEG input at 1920x1080
- Saves snapshots under `runtime/camera/`
- Returns capture status, elapsed time, relative path, and file size

### Camera Snapshot API

Added endpoint:

```text
POST /api/camera/snapshot
```

Expected successful response:

```text
ok: true
device: /dev/video0
relative_path: runtime/camera/snapshot_....jpg
size_bytes: greater than 0
elapsed_seconds: approximately 1 second
```

### Camera Device Correction

Initial testing showed that `/dev/video1` was present but was not the usable capture stream.

Verified result:

```text
/dev/video0 = usable video capture stream
/dev/video1 = non-capture or alternate node
```

The camera skill was updated to use `/dev/video0` by default.

### React Camera Button

Updated:

```text
ui-app/src/JarvisUI.tsx
```

The Camera button now:

- Enables only when the dashboard detects a camera
- Calls `POST /api/camera/snapshot`
- Displays `Capturing...` during capture
- Logs success details in the activity log
- Logs capture failures cleanly
- Prevents voice and text actions while a capture is in progress

## Validation Results

The following checks passed:

```text
[x] Insta360 Link detected
[x] /dev/video0 format list returned valid MJPEG and H.264 modes
[x] Direct ffmpeg still capture succeeded
[x] Snapshot JPEG opened successfully
[x] Camera snapshot API returned ok: true
[x] Snapshot saved under runtime/camera/
[x] Capture completed in about 1.2 seconds
[x] React UI build passed
[x] UI Camera button triggered the API successfully
[x] UI activity log reported the saved snapshot
```

## Known Good Commands

### Test Camera Formats

```bash
ffmpeg -hide_banner -f video4linux2 -list_formats all -i /dev/video0
```

### Direct Still Capture

```bash
mkdir -p ~/jarvis/runtime/camera

ffmpeg -hide_banner -loglevel error -y \
  -f video4linux2 \
  -input_format mjpeg \
  -video_size 1920x1080 \
  -i /dev/video0 \
  -frames:v 1 \
  ~/jarvis/runtime/camera/test.jpg
```

### Test Camera API

```bash
curl -X POST http://127.0.0.1:5000/api/camera/snapshot | python3 -m json.tool
```

### Build and Run UI

```bash
cd ~/jarvis/ui-app
npm run build
npm run dev
```

## Current Known Good State

```text
[x] Camera detected in device dashboard
[x] Camera button enabled in UI
[x] Snapshot API working
[x] Snapshot saved locally
[x] Activity log reports capture result
[x] Camera backend and UI are build-validated
```

## Viewer Warning Note

Eye of GNOME may print thumbnail-generation warnings such as:

```text
EOG-WARNING: Thumbnail creation failed
```

These warnings are unrelated to the Jarvis camera capture path. The snapshot itself is still valid when the API returns `ok: true` and the JPEG opens successfully.

## Not Done Yet

These remain intentionally pending:

```text
[ ] Snapshot preview inside the dashboard
[ ] Latest snapshot thumbnail endpoint
[ ] Image understanding pipeline
[ ] Vision-capable local model integration
[ ] Ask Jarvis questions about captured images
[ ] Automatic camera cleanup policy
```

## Next Recommended Step

Add a safe snapshot preview inside the dashboard.

Recommended sequence:

```text
1. Add a read-only endpoint for the latest snapshot.
2. Return a browser-safe image URL rather than an absolute path.
3. Show the latest captured image below the controls.
4. Keep vision inference separate until preview behavior is stable.
```

## Commit Trail

```text
62ce79a  Add working camera snapshot API
c071a13  Enable camera snapshot button
```

## Final Note

Jarvis now has a complete local camera capture path:

```text
Insta360 Link
  -> /dev/video0
  -> ffmpeg MJPEG capture
  -> Flask snapshot endpoint
  -> runtime/camera JPEG
  -> React Camera button
  -> activity log confirmation
```

This creates a stable foundation for the next step: dashboard snapshot preview, followed later by true vision understanding.
