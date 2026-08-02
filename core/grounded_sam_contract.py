"""Stable, dependency-free Grounded SAM response contract."""

from __future__ import annotations

from typing import Any


BACKEND_NAME = "grounded_sam"
BACKEND_VERSION = "grounded_sam_saved_image_v1"

FAILURE_HTTP_STATUS = {
    "invalid_backend": 422,
    "backend_disabled": 422,
    "invalid_prompt": 422,
    "source_image_missing": 422,
    "source_image_unreadable": 422,
    "dependency_missing": 503,
    "worker_unavailable": 503,
    "worker_busy": 503,
    "model_unavailable": 503,
    "model_load_failed": 503,
    "request_timeout": 503,
    "no_detector_candidate": 422,
    "ambiguous_detector_candidates": 422,
    "invalid_segmentation_mask": 422,
    "calibration_invalid": 422,
    "calibration_provenance_mismatch": 422,
    "artifact_write_failed": 500,
    "internal_error": 500,
}

FAILURE_STATUS = {
    "invalid_backend": "invalid_request",
    "backend_disabled": "backend_disabled",
    "invalid_prompt": "invalid_request",
    "source_image_missing": "invalid_frame",
    "source_image_unreadable": "invalid_frame",
    "dependency_missing": "dependency_unavailable",
    "worker_unavailable": "worker_unavailable",
    "worker_busy": "busy",
    "model_unavailable": "model_unavailable",
    "model_load_failed": "model_load_failed",
    "request_timeout": "timeout",
    "no_detector_candidate": "no_object",
    "ambiguous_detector_candidates": "ambiguous",
    "invalid_segmentation_mask": "segmentation_failed",
    "calibration_invalid": "calibration_invalid",
    "calibration_provenance_mismatch": "calibration_invalid",
    "artifact_write_failed": "artifact_write_failed",
    "internal_error": "internal_error",
}


def grounded_sam_result(
    *,
    ok: bool,
    status: str,
    failure_reason: str | None = None,
    error: str | None = None,
    source_image: dict[str, Any] | None = None,
    prompt: str | None = None,
    detector: dict[str, Any] | None = None,
    segmenter: dict[str, Any] | None = None,
    measurement: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
    artifacts: dict[str, str] | None = None,
    model_load_timing_ms: dict[str, Any] | None = None,
    stage_timings_ms: dict[str, Any] | None = None,
    device: str | None = None,
    dtype: str | None = None,
    dependency_versions: dict[str, str | None] | None = None,
    warnings: list[str] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete v1 contract; unavailable values are explicit nulls."""

    return {
        "ok": ok,
        "backend": BACKEND_NAME,
        "backend_version": BACKEND_VERSION,
        "experimental": True,
        "status": status,
        "failure_reason": failure_reason,
        "error": error,
        "source_image": source_image,
        "prompt": prompt,
        "detector": detector,
        "segmenter": segmenter,
        "measurement": measurement,
        "calibration": calibration,
        # Artifact keys exist only after the corresponding write succeeds.
        "artifacts": artifacts or {},
        "model_load_timing_ms": model_load_timing_ms,
        "stage_timings_ms": stage_timings_ms or {},
        "device": device,
        "dtype": dtype,
        "dependency_versions": dependency_versions or {},
        "warnings": warnings or [],
        "diagnostics": diagnostics or {},
    }


def grounded_sam_failure(
    failure_reason: str,
    error: str,
    **values: Any,
) -> dict[str, Any]:
    if failure_reason not in FAILURE_STATUS:
        failure_reason = "internal_error"
    return grounded_sam_result(
        ok=False,
        status=FAILURE_STATUS[failure_reason],
        failure_reason=failure_reason,
        error=error,
        **values,
    )


def grounded_sam_http_status(result: dict[str, Any]) -> int:
    if result.get("ok"):
        return 200
    return FAILURE_HTTP_STATUS.get(str(result.get("failure_reason")), 500)
