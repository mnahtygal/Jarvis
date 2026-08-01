"""Fail-closed validation for saved C920 rectified-image provenance."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


EXPECTED = {
    "calibration_profile_id": "logitech_c920_overhead_scan_mat",
    "logical_camera_id": "logitech_c920",
    "camera_role": "workbench",
    "calibration_status": "calibrated",
    "mode_status": "requested",
    "geometry_version": "scan_mat_geometry_v1",
    "homography_version": "opencv_perspective_outer_boundary_v1",
}
SOURCE_SIZE = (1920, 1080)
RECTIFIED_SIZE = (1440, 1080)
MAT_SIZE_MM = (609.6, 457.2)


class ProvenanceMismatch(ValueError):
    pass


def _values_match(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-6)
        )
    return actual == expected


def load_validated_provenance(
    image_path: Path,
    provenance_path: Path,
    *,
    image_width: int,
    image_height: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_path = image_path.with_suffix(".metadata.json").resolve()
    if provenance_path.resolve() != expected_path:
        raise ProvenanceMismatch("Provenance path does not match the source image sidecar.")
    if not provenance_path.is_file():
        raise FileNotFoundError(f"Provenance sidecar is missing: {provenance_path}")
    try:
        metadata = json.loads(provenance_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProvenanceMismatch("Provenance sidecar is unreadable JSON.") from exc
    if not isinstance(metadata, dict):
        raise ProvenanceMismatch("Provenance sidecar must contain a JSON object.")
    mismatches = []
    for name, expected in EXPECTED.items():
        if metadata.get(name) != expected:
            mismatches.append(f"{name}: expected {expected!r}")
    if metadata.get("mode_mismatches") or []:
        mismatches.append("mode_mismatches must be empty")
    for label in ("requested_mode", "negotiated_mode"):
        mode = metadata.get(label) or {}
        for field, expected in (
            ("pixel_format", "MJPG"), ("width", 1920),
            ("height", 1080), ("fps", 30.0),
        ):
            if mode.get(field) != expected:
                mismatches.append(f"{label}.{field}: expected {expected!r}")
    source = metadata.get("source_image_dimensions") or {}
    rectified = metadata.get("rectified_output_dimensions") or {}
    physical = metadata.get("physical_mat") or {}
    checks = (
        ("source width", source.get("width"), SOURCE_SIZE[0]),
        ("source height", source.get("height"), SOURCE_SIZE[1]),
        ("rectified width", rectified.get("width"), RECTIFIED_SIZE[0]),
        ("rectified height", rectified.get("height"), RECTIFIED_SIZE[1]),
        ("actual width", image_width, RECTIFIED_SIZE[0]),
        ("actual height", image_height, RECTIFIED_SIZE[1]),
        ("mat width", physical.get("width_mm"), MAT_SIZE_MM[0]),
        ("mat height", physical.get("height_mm"), MAT_SIZE_MM[1]),
        ("mat boundary", physical.get("boundary"), "physical_outer_boundary"),
    )
    for label, actual, expected in checks:
        if not _values_match(actual, expected):
            mismatches.append(f"{label}: expected {expected!r}, received {actual!r}")
    identity = metadata.get("stable_camera_identity") or {}
    for key in ("bus_info", "by_id_prefix", "by_path_prefix", "card_name"):
        if not identity.get(key):
            mismatches.append(f"stable_camera_identity.{key}: missing")
    if mismatches:
        raise ProvenanceMismatch("; ".join(mismatches))
    pixels_per_mm_x = image_width / MAT_SIZE_MM[0]
    pixels_per_mm_y = image_height / MAT_SIZE_MM[1]
    return metadata, {
        "ready": True,
        "profile_id": EXPECTED["calibration_profile_id"],
        "logical_camera_id": EXPECTED["logical_camera_id"],
        "camera_role": EXPECTED["camera_role"],
        "pixels_per_mm_x": pixels_per_mm_x,
        "pixels_per_mm_y": pixels_per_mm_y,
        "mm_per_pixel_x": 1.0 / pixels_per_mm_x,
        "mm_per_pixel_y": 1.0 / pixels_per_mm_y,
        "confidence": metadata.get("calibration_confidence"),
        "geometry_version": EXPECTED["geometry_version"],
        "homography_version": EXPECTED["homography_version"],
        "provenance_path": str(provenance_path),
    }
