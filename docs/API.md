# Jarvis API

Last verified against `api.py`: 2026-07-17

The Flask API runs at `http://127.0.0.1:5000`. Routes return structured JSON
unless they explicitly serve text or image artifacts.

## Health and Core Routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/` | Plain-text API confirmation |
| GET | `/health` | Lightweight readiness response: `{"status":"ok"}` |
| POST | `/text` | Run a typed command; accepts `command`, optional `use_voice` |
| GET | `/listen` | Capture microphone input and return recognized text |
| POST | `/ask` | Listen, process through Jarvis, optionally speak response |

`GET /health` is the service lifecycle readiness check.

## Camera Roles

Camera roles are resolved dynamically from stable V4L2 identity. Current roles
are Logitech C920=`workbench` and Insta360 Link=`face`. `/dev/video*` paths are
transient runtime results, not stable assignments. `/dev/v4l/by-id` is
preferred, with exact card name plus `bus_info` and optional `/dev/v4l/by-path`
fallbacks.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/api/cameras` | Discovered devices, configured roles, active role/camera |
| GET | `/api/camera/active` | Active role and resolved camera record |
| POST | `/api/camera/active` | Switch active role using `{"role":"workbench"}` |
| POST | `/api/camera/snapshot` | Capture active role, optional `role` or explicit `device` |
| GET | `/api/camera/latest` | Serve latest raw snapshot or return 404 |

Role switching returns `400` for a missing role and `409` for an unknown or
unavailable role. Explicit `device` remains available for diagnostics and
backward compatibility, but a metadata-only node is rejected; normal UI
workflows should use roles.

`GET /api/cameras` preserves `active_camera`, `active_role`, `cameras`,
`devices`, `available`, `display_name`, `id`, `role`, `resolved_device_path`,
`matched_device`, and preferred capture settings. Camera records also report
`capture_device`, `metadata_device`, `capture_by_id`, `metadata_by_id`,
`by_path`, `card_name`, `bus_info`, `device_caps`, `interface_type`,
`stable_identity`, `resolution_method`, and any `resolution_error`.
`resolution_method` is one of `by_id`, `card_name_and_bus_info`, `by_path`,
`legacy_hint`, or `unresolved`.

Each physical USB camera may expose both Video Capture and Metadata Capture
interfaces. Node-specific V4L2 `Device Caps` determines which is which even
when the broad `Capabilities` block lists both. Only Video Capture nodes are
used for snapshots, Scan Mat, vision analysis, and streaming; metadata nodes
are diagnostic output only.

## Vision and Scan Mat

| Method | Route | Request/behavior |
| --- | --- | --- |
| POST | `/api/camera/analyze` | Analyze latest snapshot; optional `prompt` |
| POST | `/api/camera/capture-analyze` | Capture then analyze; optional `prompt`, `mode`, `role`, `device` |
| POST | `/api/vision/scan-mat` | Analyze latest snapshot with OpenCV |
| POST | `/api/vision/capture-scan-mat` | Capture `workbench` role then analyze Scan Mat |
| GET | `/api/vision/artifacts/raw/<artifact_name>` | Serve a raw capture artifact |
| GET | `/api/vision/artifacts/mat-analysis/<artifact_name>` | Serve annotated/rectified artifact |

Scan Mat responses include raw, annotated, and rectified artifact URLs when
available, detection diagnostics, and the canonical 609.6 × 457.2 mm mat
metadata. Physical cameras may be unavailable without making `/health` fail.

## Calibration

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/calibration/profile` | Return active camera profile |
| POST | `/api/calibration/apply` | Compute and persist calibration |

Calibration apply requires `corners`, `known_width_mm`, and `known_height_mm`;
`image_width_px` and `image_height_px` are optional. Current Scan Mat values are
609.6 mm wide and 457.2 mm high.

## Measurement

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/status/measurement` | Measurement readiness/status |
| POST | `/api/measurement/analyze` | Analyze a permitted rectified artifact |

Measurement analysis requires `{"image_path":"..."}`. The path must resolve
to an existing `*_mat_rectified.jpg` artifact inside the Scan Mat artifact
directory. Arbitrary runtime and `/tmp` paths are rejected.

The response preserves legacy `bbox_px`, `bbox_mm`, `area_px`, and `area_mm2`
fields and adds selected-contour and rotated-box points, calibrated long/short dimensions, angle,
center, contour and bounding-box areas, candidate diagnostics, confidence, and
mask/overlay artifact paths and browser-safe URLs. The method is
`rotated_contour_measurement_v1`. Canonical units remain millimeters; inch
conversion is display-only in Vision Lab.

Successful analysis returns `200`. Invalid input paths return `400`.
Calibration/object-selection failures return `422`; unexpected processing or
artifact-write failures return `500`.

## Architecture Lab

Graphify is installed separately at `/home/mnahtygal/repos/graphify`. Jarvis
reads its generated output from `runtime/graphify/graphify-out`; these routes do
not execute Graphify or modify artifacts.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/status/architecture` | Return graph counts, timestamp, paths, and artifact availability |
| GET | `/api/architecture/tree` | Serve `JARVIS_TREE.html` or return 404 |
| GET | `/api/architecture/callflow` | Serve `graphify-callflow.html` or return 404 |

The HTML routes use conditional responses with cache age zero. They expose only
the two fixed filenames; arbitrary Graphify runtime paths are not routed.

## Status Routes

All are `GET` routes:

```text
/api/status/dashboard
/api/status/architecture
/api/status/brain
/api/status/model
/api/status/memory
/api/status/martybench
/api/status/devices
/api/status/camera-diagnostics
/api/status/calibration
/api/status/measurement
```

## Compatibility Rules

- Preserve existing routes and request fields unless migration is documented.
- Return clear error messages and appropriate status codes.
- Prefer camera roles over fixed device paths.
- Do not add cloud dependencies to local camera, model, or memory workflows.
