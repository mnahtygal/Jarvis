# Grounded SAM saved-image backend (experimental)

This checkpoint adds an opt-in measurement backend for an existing C920 scan-mat
artifact. OpenCV remains the default. Grounded SAM is disabled by default, has no
live-camera route, and never falls back to OpenCV after it is explicitly selected.

## Boundary and configuration

`config/vision_backends.json` owns the lightweight Jarvis-side settings. Set
`backends.grounded_sam.enabled` to `true` only when the separate loopback worker is
available. The worker accepts only resolved `*_mat_rectified.jpg` paths beneath
`allowed_input_root`, plus the matching metadata sidecar. Prompts are whitespace
normalized, must be nonempty, and are limited to 256 characters by default.

The worker's ML dependencies are declared separately in
`requirements-grounded-sam.txt`. `skills/grounded_sam_client.py` uses only the
standard library, Pillow validation, and existing Jarvis calibration code. It does
not import the worker pipeline. The worker imports Torch and Transformers only from
its lazy model loader after a valid analyze request.

Run the worker from the project root under the dedicated Grounded SAM environment:

```bash
python tools/grounded_sam_worker.py --host 127.0.0.1 --port 8092
```

The first valid request changes model state from `unloaded` to `loading`. A
successful load is cached as `ready`. A failed load is `load_failed` or
`unavailable`, remains visible in health output, and is retried by the next valid
request. A nonblocking process lock admits one inference at a time; concurrent
requests return `worker_busy`. Jarvis enforces the configured request timeout.
Health probes inspect installed distribution metadata and never load a model.

## Request and response

OpenCV-compatible request (the `backend` field may also be omitted):

```json
{"backend": "opencv", "image_path": "runtime/camera/mat_analysis/example_mat_rectified.jpg"}
```

Experimental request:

```json
{
  "backend": "grounded_sam",
  "image_path": "runtime/camera/mat_analysis/example_mat_rectified.jpg",
  "prompt": "small metal gear"
}
```

Grounded SAM results always contain the complete top-level v1 schema. Values that
cannot be known are `null`; maps and lists use empty values. Artifact path keys are
the exception: each path appears only after that artifact was written successfully.
A successful result has this shape (values abbreviated):

```json
{
  "ok": true,
  "backend": "grounded_sam",
  "backend_version": "grounded_sam_saved_image_v1",
  "experimental": true,
  "status": "ready",
  "failure_reason": null,
  "error": null,
  "source_image": {"path": "...", "sha256": "...", "width": 1440, "height": 1080},
  "prompt": "small metal gear",
  "detector": {
    "model": "IDEA-Research/grounding-dino-base",
    "box_threshold": 0.2,
    "text_threshold": 0.15,
    "candidates": [],
    "selected_box": [100.0, 100.0, 400.0, 300.0],
    "selected_label": "gear",
    "selected_confidence": 0.81
  },
  "segmenter": {
    "model": "facebook/sam2-hiera-base-plus",
    "selected_mask_score": 0.92,
    "selected_mask_index": 1,
    "mask_area_pixels": 42000,
    "cleanup": {}
  },
  "measurement": {},
  "calibration": {},
  "artifacts": {"raw_mask_path": "...", "cleaned_mask_path": "...", "diagnostic_overlay_path": "..."},
  "model_load_timing_ms": {"total": 1350.0, "cache_hit": false, "attempt": 1},
  "stage_timings_ms": {},
  "device": "cuda",
  "dtype": "float32",
  "dependency_versions": {},
  "warnings": [],
  "diagnostics": {"saved_image_only": true, "real_models_loaded": true}
}
```

Detector candidates include their box, confidence, label, prompt, area ratio,
boundary flag, acceptance flag, and rejection reasons. Measurement reports both the
maximum occupied mask envelope and a trimmed robust body estimate in millimeters.
Neither path uses known physical answers to tune selection thresholds.

## Failures and HTTP policy

Expected request/data failures use HTTP 422: `invalid_backend`, `backend_disabled`,
`invalid_prompt`, `source_image_missing`, `source_image_unreadable`,
`no_detector_candidate`, `ambiguous_detector_candidates`,
`invalid_segmentation_mask`, `calibration_invalid`, and
`calibration_provenance_mismatch`.

Service failures use HTTP 503: `dependency_missing`, `worker_unavailable`,
`worker_busy`, `model_unavailable`, `model_load_failed`, and `request_timeout`.
`artifact_write_failed` and `internal_error` use HTTP 500. Every failure is a normal
v1 response with `ok=false`, stable `status` and `failure_reason`, a safe `error`,
and any diagnostics available before failure. There is no fallback to OpenCV.

## Provenance guardrails

The worker independently verifies the sidecar belongs to the selected image and
matches the frozen C920 workbench contract: Logitech C920 identity, requested and
negotiated MJPG 1920x1080 at 30 fps, 1440x1080 rectification, 609.6x457.2 mm outer
mat boundary, calibrated status, and expected geometry/homography versions. Any
mismatch fails closed. Insta360 calibration data is neither read nor accepted.

## Tests

The checkpoint tests use mocks and synthetic arrays only; they never load models or
perform inference:

```bash
PYTHONPATH=/home/mnahtygal/jarvis/.venv/lib/python3.12/site-packages \
  /home/mnahtygal/jarvis-grounded-sam/.venv-grounded-sam/bin/python -m pytest -q \
  tests/test_grounded_sam_api_client.py tests/test_grounded_sam_worker.py
```
