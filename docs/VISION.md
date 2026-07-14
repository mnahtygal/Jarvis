# Jarvis Vision

Last updated: 2026-07-12

Vision Lab is Jarvis's primary camera, Scan Mat, calibration, and inspection
workspace. It remains local-first: captures and derived artifacts stay on Thor,
and image analysis uses the local Gemma 3 4B Vision server on port 8081.

## Camera Roles

| Role | Camera | Purpose |
| --- | --- | --- |
| `workbench` | Logitech HD Pro Webcam C920 | Fixed Scan Mat and workshop capture |
| `face` | Insta360 Link | Face/general camera use |

The camera resolver discovers V4L2 devices and matches configured camera names.
Linux paths such as `/dev/video0` and `/dev/video2` may swap after restart and
must not be treated as permanent camera assignments. Vision Lab exposes a role
selector and Scan Mat capture always requests the default `workbench` role.

The earlier Insta360 overhead workflow and gimbal investigation remain useful
historical references, but they do not define the current workbench camera.

## Implemented Features

- camera discovery, availability, active-role selection, and role switching
- snapshots from the active role or an explicitly requested role/device
- local image analysis through Gemma 3 4B Vision
- Scan Mat capture from the workbench role
- OpenCV mat detection and corner diagnostics
- perspective correction to a top-down view
- raw, annotated, and rectified artifact URLs
- calibration profile, pixel/unit ratios, and confidence
- single flat-object contour measurement on rectified images
- rotated minimum-area rectangle with anisotropic X/Y calibration
- binary object mask and annotated measurement overlay artifacts
- Vision Lab calibration and measurement result panels

## Scan Mat Pipeline

```text
Logitech C920 workbench role
  -> raw capture
  -> OpenCV 24 × 18 inch mat detection
  -> annotated corner/detection artifact
  -> perspective-rectified top-down artifact
  -> calibration metadata
  -> optional rotated-contour measurement, mask, and overlay
```

Canonical mat dimensions:

| Dimension | Imperial | Metric |
| --- | --- | --- |
| Width | 24 inches | 609.6 mm |
| Height | 18 inches | 457.2 mm |

Calibration quality must accompany measurement results. A detected mat does not
by itself prove precision; camera position, contour quality, shadows, and object
segmentation can still affect results.

## Vision Lab Analysis Modes

The UI currently offers general scan, object-on-mat, measurement-helper, OCR
(`Read Text / Label`), 3D-print inspection, marine-part, and workbench-status
prompts.

These are experimental vision prompts. In particular:

- Measurement Helper asks the vision model for a cautious visual estimate; it
  is not the calibrated measurement engine.
- OCR asks the multimodal model to read visible markings; a dedicated validated
  OCR pipeline is still planned.
- 3D Print Inspect provides qualitative inspection, not dimensional metrology.

## Measurement Status

Implemented Phase 2.3B workflow:

- calibration derived from known mat corners and dimensions
- millimeters-per-pixel and pixels-per-millimeter values
- calibration confidence and timestamp
- scored single-object isolation from threshold, HSV, and edge candidates
- border/frame rejection and candidate-score diagnostics
- axis-aligned and rotated bounding boxes
- calibrated long/short sides using anisotropic X/Y scale
- rotation, center, contour area, bounding-box areas, and confidence
- saved binary mask and annotated overlay artifacts
- millimeter/inch display selection in Vision Lab (backend remains millimeters)

Active work:

- validation against known reference objects
- multiple-object measurement
- holes and internal-feature measurement
- diameter and feature estimation
- OCR-assisted validation and structured marking extraction
- depth and thickness measurement
- full reverse engineering and production-CAD accuracy
- measurement and scan history

Measurements must not be presented as precise until calibration and object
detection quality support that claim.

## Planned Maker Workflow

After measurement validation, the intended sequence is feature detection,
reverse-engineering assistance, editable OpenSCAD starter geometry, and Maker
Lab project/history integration. Generated geometry will remain a documented
starting point, not production-ready CAD.

## Related Documentation

- [Architecture](ARCHITECTURE.md)
- [API](API.md)
- [Ubuntu startup](UBUNTU_STARTUP.md)
- [Scan Mat calibration design](Architecture/SCANMAT_CALIBRATION.md)
- [Historical Insta360 gimbal investigation](CAMERA_GIMBAL_INVESTIGATION.md)
