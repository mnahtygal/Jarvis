"""Validation of fixed C920 Scan Mat calibration provenance."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


EXPECTED_PROFILE_ID = "logitech_c920_overhead_scan_mat"
EXPECTED_LOGICAL_CAMERA_ID = "logitech_c920"
EXPECTED_CAMERA_ROLE = "workbench"
EXPECTED_PIXEL_FORMAT = "MJPG"
EXPECTED_SOURCE_WIDTH = 1920
EXPECTED_SOURCE_HEIGHT = 1080
EXPECTED_RECTIFIED_WIDTH = 1440
EXPECTED_RECTIFIED_HEIGHT = 1080
EXPECTED_MAT_WIDTH_MM = 609.6
EXPECTED_MAT_HEIGHT_MM = 457.2
EXPECTED_GEOMETRY_VERSION = "scan_mat_geometry_v1"
EXPECTED_HOMOGRAPHY_VERSION = "opencv_perspective_outer_boundary_v1"


class CalibrationProvenanceError(ValueError):
    """Raised when a fixture is not from the calibrated C920 path."""


@dataclass(frozen=True)
class MetricCalibration:
    profile_id: str
    logical_camera_id: str
    camera_role: str
    pixels_per_mm_x: float
    pixels_per_mm_y: float
    mm_per_pixel_x: float
    mm_per_pixel_y: float
    confidence: float
    geometry_version: str
    homography_version: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_equal(
    mismatches: list[str],
    label: str,
    actual: Any,
    expected: Any,
) -> None:
    if actual != expected:
        mismatches.append(
            f"{label}: expected {expected!r}, received {actual!r}"
        )


def _require_close(
    mismatches: list[str],
    label: str,
    actual: Any,
    expected: float,
    *,
    tolerance: float = 1e-6,
) -> None:
    try:
        numeric = float(actual)
    except (TypeError, ValueError):
        mismatches.append(
            f"{label}: expected numeric {expected!r}, received {actual!r}"
        )
        return
    if abs(numeric - expected) > tolerance:
        mismatches.append(
            f"{label}: expected {expected!r}, received {numeric!r}"
        )


def validate_c920_provenance(
    metadata: dict[str, Any],
    *,
    rectified_width: int,
    rectified_height: int,
) -> MetricCalibration:
    """Reject artifacts outside the completed fixed C920 calibration."""

    mismatches: list[str] = []
    requested = metadata.get("requested_mode") or {}
    negotiated = metadata.get("negotiated_mode") or {}
    source = metadata.get("source_image_dimensions") or {}
    rectified = metadata.get("rectified_output_dimensions") or {}
    physical = metadata.get("physical_mat") or {}

    _require_equal(
        mismatches,
        "calibration_profile_id",
        metadata.get("calibration_profile_id"),
        EXPECTED_PROFILE_ID,
    )
    _require_equal(
        mismatches,
        "logical_camera_id",
        metadata.get("logical_camera_id"),
        EXPECTED_LOGICAL_CAMERA_ID,
    )
    _require_equal(
        mismatches,
        "camera_role",
        metadata.get("camera_role"),
        EXPECTED_CAMERA_ROLE,
    )
    _require_equal(
        mismatches,
        "calibration_status",
        metadata.get("calibration_status"),
        "calibrated",
    )
    _require_equal(
        mismatches,
        "mode_status",
        metadata.get("mode_status"),
        "requested",
    )
    _require_equal(
        mismatches,
        "mode_mismatches",
        metadata.get("mode_mismatches") or [],
        [],
    )
    for label, mode in (("requested_mode", requested), ("negotiated_mode", negotiated)):
        _require_equal(
            mismatches,
            f"{label}.pixel_format",
            mode.get("pixel_format"),
            EXPECTED_PIXEL_FORMAT,
        )
        _require_equal(
            mismatches,
            f"{label}.width",
            mode.get("width"),
            EXPECTED_SOURCE_WIDTH,
        )
        _require_equal(
            mismatches,
            f"{label}.height",
            mode.get("height"),
            EXPECTED_SOURCE_HEIGHT,
        )
        _require_close(
            mismatches,
            f"{label}.fps",
            mode.get("fps"),
            30.0,
        )

    _require_equal(
        mismatches,
        "source_image_dimensions.width",
        source.get("width"),
        EXPECTED_SOURCE_WIDTH,
    )
    _require_equal(
        mismatches,
        "source_image_dimensions.height",
        source.get("height"),
        EXPECTED_SOURCE_HEIGHT,
    )
    _require_equal(
        mismatches,
        "rectified_output_dimensions.width",
        rectified.get("width"),
        EXPECTED_RECTIFIED_WIDTH,
    )
    _require_equal(
        mismatches,
        "rectified_output_dimensions.height",
        rectified.get("height"),
        EXPECTED_RECTIFIED_HEIGHT,
    )
    _require_equal(
        mismatches,
        "actual_rectified_width",
        rectified_width,
        EXPECTED_RECTIFIED_WIDTH,
    )
    _require_equal(
        mismatches,
        "actual_rectified_height",
        rectified_height,
        EXPECTED_RECTIFIED_HEIGHT,
    )
    _require_close(
        mismatches,
        "physical_mat.width_mm",
        physical.get("width_mm"),
        EXPECTED_MAT_WIDTH_MM,
    )
    _require_close(
        mismatches,
        "physical_mat.height_mm",
        physical.get("height_mm"),
        EXPECTED_MAT_HEIGHT_MM,
    )
    _require_equal(
        mismatches,
        "physical_mat.boundary",
        physical.get("boundary"),
        "physical_outer_boundary",
    )
    _require_equal(
        mismatches,
        "geometry_version",
        metadata.get("geometry_version"),
        EXPECTED_GEOMETRY_VERSION,
    )
    _require_equal(
        mismatches,
        "homography_version",
        metadata.get("homography_version"),
        EXPECTED_HOMOGRAPHY_VERSION,
    )
    stable_identity = metadata.get("stable_camera_identity") or {}
    for key in ("bus_info", "by_id_prefix", "by_path_prefix", "card_name"):
        if not stable_identity.get(key):
            mismatches.append(f"stable_camera_identity.{key}: missing")

    corners = metadata.get("corners")
    if (
        not isinstance(corners, list)
        or len(corners) != 4
        or any(not isinstance(point, list) or len(point) != 2 for point in corners)
    ):
        mismatches.append("corners: expected four ordered 2D points")
    homography = metadata.get("homography")
    if (
        not isinstance(homography, list)
        or len(homography) != 3
        or any(not isinstance(row, list) or len(row) != 3 for row in homography)
    ):
        mismatches.append("homography: expected a 3x3 matrix")

    if mismatches:
        raise CalibrationProvenanceError(
            "Calibration provenance mismatch: " + "; ".join(mismatches)
        )

    pixels_per_mm_x = EXPECTED_RECTIFIED_WIDTH / EXPECTED_MAT_WIDTH_MM
    pixels_per_mm_y = EXPECTED_RECTIFIED_HEIGHT / EXPECTED_MAT_HEIGHT_MM
    if abs(pixels_per_mm_x - pixels_per_mm_y) > 1e-12:
        raise CalibrationProvenanceError(
            "Rectified X/Y metric scale is inconsistent."
        )

    return MetricCalibration(
        profile_id=EXPECTED_PROFILE_ID,
        logical_camera_id=EXPECTED_LOGICAL_CAMERA_ID,
        camera_role=EXPECTED_CAMERA_ROLE,
        pixels_per_mm_x=pixels_per_mm_x,
        pixels_per_mm_y=pixels_per_mm_y,
        mm_per_pixel_x=1.0 / pixels_per_mm_x,
        mm_per_pixel_y=1.0 / pixels_per_mm_y,
        confidence=float(metadata.get("calibration_confidence")),
        geometry_version=EXPECTED_GEOMETRY_VERSION,
        homography_version=EXPECTED_HOMOGRAPHY_VERSION,
        timestamp=str(metadata.get("created_at")),
    )


def load_and_validate_c920_provenance(
    metadata_path: Path,
    *,
    rectified_width: int,
    rectified_height: int,
) -> tuple[dict[str, Any], MetricCalibration]:
    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"Calibration provenance sidecar not found: {metadata_path}"
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise CalibrationProvenanceError(
            "Calibration provenance must contain a JSON object."
        )
    calibration = validate_c920_provenance(
        metadata,
        rectified_width=rectified_width,
        rectified_height=rectified_height,
    )
    return metadata, calibration
