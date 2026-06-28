# Jarvis Scan Mat Mode Checkpoint

Date: 2026-06-28
Project: Jarvis Local AI Assistant
Host: NVIDIA Thor
Status: Scan Mat Mode v1 in progress

## Summary

Jarvis now has the beginning of a dedicated scan-mat workflow for the workbench.

The Vision Lab UI already provides scan modes for object inspection, measurement help, OCR, 3D print inspection, jet ski part scans, and workbench status. This checkpoint adds a backend endpoint that can capture the current camera view and immediately analyze it with the selected prompt in one request.

This does not yet control the Insta360 Link gimbal. The camera must still be aimed at the mat manually through the Insta360 Link Controller, DeskView, or physical camera positioning before capture.

## Current Scan Mat Hardware

```text
Camera: Insta360 Link
Mount: top of monitor
Scan surface: 18 x 24 inch black measured cutting mat
Current object test: NVMe Raspberry Pi HAT
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

## New Backend Endpoint

Added:

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

## Example Test Command

```bash
curl -s -X POST http://127.0.0.1:5000/api/camera/capture-analyze \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "object",
    "prompt": "Do not identify people. The camera is aimed at an 18 by 24 inch measurement mat. Describe the main object on the mat. Focus on shape, visible components, ports, chips, markings, orientation, and anything useful for a workshop assistant."
  }' | python3 -m json.tool
```

## Current Vision Lab Modes

```text
General Scan
Object on Mat
Measurement Helper
Read Text / Label
3D Print Inspect
Jet Ski Part Scan
Workbench Status
```

## Known Limitations

```text
[ ] No automatic Insta360 gimbal control yet
[ ] No calibration from mat corners yet
[ ] No real dimensional measurement yet
[ ] No object bounding boxes yet
[ ] No saved scan history yet
[ ] No OpenSCAD generation from scans yet
```

## Recommended Physical Workflow

```text
1. Open Insta360 Link Controller or DeskView.
2. Point camera down toward the mat.
3. Confirm the mat fills most of the view.
4. Place object in the center of the grid.
5. Reduce glare.
6. Use Vision Lab to capture and analyze.
```

## Next Recommended Coding Step

Update the Vision Lab UI to call `/api/camera/capture-analyze` from a single button:

```text
Capture + Analyze Current View
```

This will reduce the workflow from two button clicks to one.

## Longer-Term Direction

Future Scan Mat Mode should support:

```text
- camera position presets
- scan history
- measurement calibration
- object comparison
- OpenSCAD starter generation
- 3D print inspection notes
- jet ski part project notes
```
