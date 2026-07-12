# Manual Scan Station

> **Historical workflow.** This document records the earlier Insta360 overhead
> setup. The current workbench camera is the role-selected Logitech C920; see
> [Vision](VISION.md) and [Architecture](ARCHITECTURE.md). Device paths are not
> permanent assignments.

Last updated: 2026-07-04

## Purpose

This document defines the current manual overhead scan-station workflow for Jarvis Phase 2.2B. The goal is to make Scan Mat captures repeatable before building the Calibration Engine.

For now, Jarvis assumes the Insta360 Link is physically positioned overhead and left fixed after alignment.

## Why Manual Overhead Mode

Insta360 Link gimbal control is not solved yet on Thor. Manual diagnostics show that standard V4L2 pan and tilt controls exist and accept values, but they do not physically move the gimbal. Real gimbal movement likely requires vendor-specific UVC extension-unit commands.

Until that path is mapped, Scan Mat work should rely on a stable physical setup:

```text
Camera fixed overhead
  -> Capture scan mat
  -> Verify mat detection
  -> Save known-good setup profile
  -> Use profile as calibration baseline
```

## Hardware Assumptions

| Item | Current assumption |
| --- | --- |
| Host | NVIDIA Jetson AGX Thor |
| Camera | Insta360 Link |
| Camera mode | Manual overhead |
| Capture device | `/dev/video0` |
| Metadata device | `/dev/video1` |
| Driver | `uvcvideo` |
| Format | `1920x1080 / MJPG / 30 fps` |
| Scan surface | Workbench Scan Mat |

## Camera Device Mapping

Known mapping:

```text
/dev/video0 = real video capture node
/dev/video1 = metadata node
```

Do not switch Scan Mat capture to `/dev/video1`. It is not the image capture stream.

## Manual Alignment Checklist

Before capturing a baseline image:

- [ ] Camera physically pointed straight down.
- [ ] Mat fills most of frame.
- [ ] All four mat corners visible.
- [ ] Lighting even.
- [ ] No glare.
- [ ] Object centered.
- [ ] Camera not moved after alignment.

## Capture A Test Image

Use the Vision Lab UI:

1. Open Jarvis UI at `http://localhost:5173`.
2. Go to `Vision Lab`.
3. Manually position the Insta360 Link overhead.
4. Click `Capture Current View`.
5. Confirm the latest snapshot preview shows the full mat.

Backend endpoint:

```bash
curl -X POST http://127.0.0.1:5000/api/camera/snapshot
```

## Run Scan-Mat Detection

Use the Vision Lab UI:

1. Keep the camera fixed.
2. Click `Scan Mat`.
3. Review raw capture, annotated detection, and rectified view.

Backend endpoint:

```bash
curl -X POST http://127.0.0.1:5000/api/vision/capture-scan-mat
```

## Good Scan Criteria

A good scan should show:

- mat occupies most of the image
- all four mat corners are visible
- mat border is not cropped
- annotated image marks the detected mat boundary
- rectified top-down image is available
- no strong glare over corners or grid
- object does not hide key mat edges or corners

## Failure Meaning

| Symptom | Likely cause |
| --- | --- |
| No mat detected | camera not overhead, mat cropped, poor contrast, glare |
| Annotated image exists but rectified view missing | mat boundary/corners not reliable |
| Corners wrong | mat partially occluded or perspective too steep |
| Image blurry | focus or motion issue |
| Detection changes between captures | camera or mat moved |

## Setup Profile

The initial scan-station profile is stored in:

```text
config/camera_profiles.json
```

Active profile:

```text
thor_manual_overhead_scan_station
```

The profile is intentionally marked `draft` until the overhead setup is physically fixed and a known-good Scan Mat capture is saved.

## Path To Calibration Engine

The Calibration Engine should build on a known-good setup profile. It should not assume measurements are precise until the scan station is repeatable.

Calibration should record:

- active camera profile
- raw image reference
- annotated image reference
- rectified image reference
- known mat dimensions
- pixel-to-mm ratio
- calibration confidence
- timestamp
- notes about lighting, height, zoom, and alignment
