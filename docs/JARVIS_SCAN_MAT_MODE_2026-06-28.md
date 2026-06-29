# Jarvis Scan Mat Mode Checkpoint

Date: 2026-06-28
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Status: Scan Mat Mode v1 active, OpenCV geometry layer started

## Summary

Jarvis now has a dedicated scan-mat workflow for the workbench.

The Vision Lab UI provides scan modes for object inspection, measurement help, OCR, 3D print inspection, jet ski part scans, and workbench status. The backend can capture the current camera view, analyze the fresh snapshot with the selected vision prompt, and run a first-pass OpenCV scan-mat detector.

This does not yet control the Insta360 Link gimbal. The camera must still be aimed at the mat manually through the Insta360 Link Controller, DeskView, or physical camera positioning before capture.

## Current Scan Mat Hardware

```text
Camera: Insta360 Link
Mount: top of monitor
Scan surface: 18 x 24 inch black measured cutting mat
Current object test: NVMe Raspberry Pi HAT / small electronics
```

## Important Behavior

The camera capture system uses the current camera angle.

```text
Capture Current View = capture whatever the Insta360 is currently looking at
```

It does not yet mean:

```text
Move camera down -> capture mat -> move camera back
```

That will be a later gimbal-control stage.

## Vision Lab Scan Modes

```text
General Scan
Object on Mat
Measurement Helper
Read Text / Label
3D Print Inspect
Jet Ski Part Scan
Workbench Status
```

Each scan mode sends a different prompt to the local Gemma vision model.

## Backend Endpoints

### Capture Snapshot

```text
POST /api/camera/snapshot
```

Captures a still image from the current camera angle and saves it under:

```text
runtime/camera/
```

### Analyze Latest Snapshot

```text
POST /api/camera/analyze
```

Uses the most recent snapshot and sends it to the local Gemma vision model.

### Capture + Analyze

```text
POST /api/camera/capture-analyze
```

This endpoint performs:

```text
1. Capture a fresh camera snapshot
2. Locate the saved image
3. Send the image to the local vision model
4. Return capture metadata plus analysis metadata
```

Expected successful response includes:

```text
ok: true
mode: selected scan mode
capture: snapshot metadata
analysis: vision response metadata
description: vision description
image_name: analyzed snapshot filename
model: active vision model
```

### OpenCV Analyze Latest Scan Mat Image

```text
POST /api/vision/scan-mat
```

Runs OpenCV scan-mat analysis on the latest saved snapshot.

### OpenCV Capture + Scan Mat

```text
POST /api/vision/capture-scan-mat
```

This endpoint performs:

```text
1. Capture a fresh camera snapshot
2. Run OpenCV mat detection
3. Draw an annotated mat-corner image
4. Generate a rectified mat image if detection succeeds
5. Return mat/grid metadata
```

Expected successful response includes:

```text
ok: true
capture: snapshot metadata
mat_analysis:
  ok: true
  mat_detected: true
  mat:
    width_inches: 24
    height_inches: 18
    corners: [...]
    approx_pixels_per_inch_x: ...
    approx_pixels_per_inch_y: ...
  grid: {...}
```

## OpenCV Skill

Added:

```text
skills/scan_mat_skill.py
```

Current responsibilities:

```text
- Read latest scan image
- Detect a large four-corner mat-like contour
- Annotate detected mat corners
- Perspective-rectify the mat to a normalized 24 x 18 image
- Estimate grid-line visibility with Hough line detection
- Return mat metadata for future measurement workflows
```

Current generated files:

```text
runtime/camera/mat_analysis/*_mat_annotated.jpg
runtime/camera/mat_analysis/*_mat_rectified.jpg
```

## Required Python Packages

If OpenCV is not installed:

```bash
cd ~/jarvis
source .venv/bin/activate
pip install opencv-python-headless numpy
sudo systemctl restart jarvis-api.service
```

## Example Test Commands

### Capture + Analyze with Gemma Vision

```bash
curl -s -X POST http://127.0.0.1:5000/api/camera/capture-analyze \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "object",
    "prompt": "Do not identify people. The camera is aimed at an 18 by 24 inch measurement mat. Describe the main object on the mat. Focus on shape, visible components, ports, chips, markings, orientation, and anything useful for a workshop assistant."
  }' | python3 -m json.tool
```

### Capture + OpenCV Scan Mat

```bash
curl -s -X POST http://127.0.0.1:5000/api/vision/capture-scan-mat \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

### Analyze Latest Snapshot with OpenCV

```bash
curl -s -X POST http://127.0.0.1:5000/api/vision/scan-mat \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

## Recommended Physical Workflow

```text
1. Open Insta360 Link Controller or DeskView.
2. Point camera down toward the mat.
3. Confirm the mat fills most of the view.
4. Keep the mat border visible.
5. Place object in the center of the grid.
6. Reduce glare.
7. Use Vision Lab or curl test endpoint to capture and analyze.
```

## Known Good Visual Target

The best scan input so far is a top-down image where:

```text
[x] Most of the mat is visible
[x] Grid lines are clear
[x] Object is centered on the mat
[x] Perspective distortion is modest
[x] Lighting is bright enough
[x] Glare is controlled
```

## Known Limitations

```text
[ ] No automatic Insta360 gimbal control yet
[ ] OpenCV mat detection is first-pass only
[ ] Mat corner detection may fail if the border is cropped or blocked
[ ] Grid detection is metadata-only, not yet used for real object dimensions
[ ] No object bounding boxes yet
[ ] No saved scan history yet
[ ] No OpenSCAD generation from scans yet
[ ] Vision Lab UI does not yet show annotated/rectified OpenCV outputs
```

## Next Recommended Coding Step

Wire the new OpenCV endpoints into Vision Lab:

```text
[ ] Capture + Analyze Current View
[ ] Detect Mat
[ ] Show annotated mat image
[ ] Show rectified mat image
[ ] Display detected corners and pixels-per-inch estimate
```

## Longer-Term Direction

Future Scan Mat Mode should support:

```text
- camera position presets
- scan history
- measurement calibration
- object detection / bounding boxes
- object comparison
- OpenSCAD starter generation
- 3D print inspection notes
- jet ski part project notes
```

## Commit Trail

```text
74a64d6  Add capture and analyze camera endpoint
6e42e7c  Add Scan Mat Mode checkpoint doc
1dcf7dc  Add OpenCV scan mat analysis skill
4427be5  Add scan mat analysis API endpoint
```
