from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.scan_mat_geometry import (
    MAT_HEIGHT_INCHES,
    MAT_HEIGHT_MM,
    MAT_WIDTH_INCHES,
    MAT_WIDTH_MM,
    RECTIFIED_HEIGHT_PX,
    RECTIFIED_WIDTH_PX,
    SCAN_MAT_GEOMETRY_VERSION,
    SCAN_MAT_HOMOGRAPHY_VERSION,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMERA_PROFILES_PATH = PROJECT_ROOT / "config" / "camera_profiles.json"


def load_camera_profiles() -> dict:
    if not CAMERA_PROFILES_PATH.exists():
        raise FileNotFoundError(f"Camera profiles file not found: {CAMERA_PROFILES_PATH}")

    with CAMERA_PROFILES_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Camera profiles file must contain a JSON object.")

    return data


def save_camera_profiles(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("Camera profiles data must be a dictionary.")

    CAMERA_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = CAMERA_PROFILES_PATH.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(data, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(CAMERA_PROFILES_PATH)


def get_active_camera_profile() -> dict:
    data = load_camera_profiles()
    active_profile_id = data.get("active_profile_id")
    if not active_profile_id:
        raise ValueError("Camera profiles file does not define active_profile_id.")

    profiles = data.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError("Camera profiles file must define profiles as a list.")

    for profile in profiles:
        if isinstance(profile, dict) and profile.get("id") == active_profile_id:
            return deepcopy(profile)

    raise ValueError(f"Active camera profile not found: {active_profile_id}")


def get_camera_profile(
    *,
    profile_id: str | None = None,
    logical_camera_id: str | None = None,
    role: str | None = None,
) -> dict:
    """Select one calibration profile without relying on a device node number."""
    data = load_camera_profiles()
    profiles = data.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError("Camera profiles file must define profiles as a list.")

    matches = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        camera = profile.get("camera") or {}
        if profile_id and profile.get("id") != profile_id:
            continue
        if logical_camera_id and camera.get("logical_camera_id") != logical_camera_id:
            continue
        if role and camera.get("role") != role:
            continue
        matches.append(profile)

    if len(matches) != 1:
        criteria = {
            "profile_id": profile_id,
            "logical_camera_id": logical_camera_id,
            "role": role,
        }
        raise ValueError(
            f"Expected exactly one camera calibration profile for {criteria}; "
            f"found {len(matches)}."
        )
    return deepcopy(matches[0])


def rectified_metadata_path(image_path: Path) -> Path:
    return image_path.with_suffix(".metadata.json")


def build_scan_mat_provenance(
    *,
    capture: dict,
    corners: list[list[float]],
    source_width: int,
    source_height: int,
    rectified_width: int,
    rectified_height: int,
    homography: list[list[float]],
    detected_confidence: float | None,
) -> dict:
    camera = capture.get("camera") or {}
    logical_camera_id = camera.get("id")
    role = camera.get("role") or capture.get("role")
    profile = get_camera_profile(logical_camera_id=logical_camera_id, role=role)
    calibration = profile.get("calibration") or {}
    stable_identity = camera.get("stable_identity") or {}
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "calibration_profile_id": profile.get("id"),
        "calibration_status": calibration.get("status"),
        "calibration_confidence": calibration.get("confidence"),
        "logical_camera_id": logical_camera_id,
        "camera_role": role,
        "stable_camera_identity": stable_identity,
        "runtime_device": capture.get("device"),
        "backend": capture.get("backend"),
        "requested_mode": capture.get("requested_mode"),
        "negotiated_mode": capture.get("negotiated_mode"),
        "mode_status": capture.get("mode_status"),
        "mode_mismatches": capture.get("mode_mismatches") or [],
        "source_image_dimensions": {
            "width": int(source_width),
            "height": int(source_height),
        },
        "rectified_output_dimensions": {
            "width": int(rectified_width),
            "height": int(rectified_height),
        },
        "physical_mat": {
            "width_inches": MAT_WIDTH_INCHES,
            "height_inches": MAT_HEIGHT_INCHES,
            "width_mm": MAT_WIDTH_MM,
            "height_mm": MAT_HEIGHT_MM,
            "boundary": "physical_outer_boundary",
        },
        "corners": corners,
        "detected_mat_confidence": detected_confidence,
        "homography": homography,
        "homography_version": SCAN_MAT_HOMOGRAPHY_VERSION,
        "geometry_version": SCAN_MAT_GEOMETRY_VERSION,
    }


def validate_rectified_provenance(
    metadata: dict,
    *,
    active_camera: dict,
) -> tuple[dict | None, list[str]]:
    """Validate artifact/profile/runtime geometry; device numbers are ignored."""
    mismatches: list[str] = []
    profile_id = metadata.get("calibration_profile_id")
    try:
        profile = get_camera_profile(profile_id=profile_id)
    except ValueError as exc:
        return None, [str(exc)]

    camera = profile.get("camera") or {}
    calibration = profile.get("calibration") or {}
    scan_mat = profile.get("scan_mat") or {}
    expected_camera_id = camera.get("logical_camera_id")
    expected_role = camera.get("role")

    _match_value(mismatches, "artifact logical camera", expected_camera_id, metadata.get("logical_camera_id"))
    _match_value(mismatches, "active logical camera", expected_camera_id, active_camera.get("id"))
    _match_value(mismatches, "artifact camera role", expected_role, metadata.get("camera_role"))
    _match_value(mismatches, "active camera role", expected_role, active_camera.get("role"))
    _match_mapping(
        mismatches,
        "stable camera identity",
        camera.get("stable_identity") or {},
        metadata.get("stable_camera_identity") or {},
    )
    _match_mapping(
        mismatches,
        "active stable camera identity",
        camera.get("stable_identity") or {},
        active_camera.get("stable_identity") or {},
    )
    _match_mapping(mismatches, "requested capture mode", camera.get("requested_mode") or {}, metadata.get("requested_mode") or {})
    _match_mapping(mismatches, "negotiated capture mode", camera.get("negotiated_mode") or {}, metadata.get("negotiated_mode") or {})
    _match_mapping(mismatches, "source image dimensions", camera.get("source_image_dimensions") or {}, metadata.get("source_image_dimensions") or {})
    _match_mapping(mismatches, "rectified output dimensions", scan_mat.get("rectified_output_dimensions") or {}, metadata.get("rectified_output_dimensions") or {})
    _match_value(mismatches, "geometry version", SCAN_MAT_GEOMETRY_VERSION, metadata.get("geometry_version"))
    _match_value(mismatches, "homography version", SCAN_MAT_HOMOGRAPHY_VERSION, metadata.get("homography_version"))
    if metadata.get("mode_status") != "requested" or metadata.get("mode_mismatches"):
        mismatches.append("capture mode did not match the requested calibrated mode")
    if calibration.get("status") != "calibrated":
        mismatches.append("calibration profile is not calibrated")
    if metadata.get("calibration_status") != "calibrated":
        mismatches.append("artifact was not produced with a calibrated profile")
    return profile, mismatches


def _match_value(mismatches: list[str], label: str, expected: Any, actual: Any) -> None:
    if expected != actual:
        mismatches.append(f"{label} mismatch: expected={expected!r} actual={actual!r}")


def _match_mapping(
    mismatches: list[str], label: str, expected: dict, actual: dict
) -> None:
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            mismatches.append(
                f"{label}.{key} mismatch: expected={expected_value!r} "
                f"actual={actual.get(key)!r}"
            )


def update_active_camera_profile(updates: dict) -> dict:
    if not isinstance(updates, dict):
        raise ValueError("Camera profile updates must be a dictionary.")

    data = load_camera_profiles()
    active_profile_id = data.get("active_profile_id")
    if not active_profile_id:
        raise ValueError("Camera profiles file does not define active_profile_id.")

    profiles = data.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError("Camera profiles file must define profiles as a list.")

    for profile in profiles:
        if isinstance(profile, dict) and profile.get("id") == active_profile_id:
            _deep_merge(profile, updates)
            save_camera_profiles(data)
            return deepcopy(profile)

    raise ValueError(f"Active camera profile not found: {active_profile_id}")


def compute_calibration_from_mat(
    corners: list[list[float]],
    known_width_mm: float,
    known_height_mm: float,
    image_width_px: int | None = None,
    image_height_px: int | None = None,
) -> dict:
    known_width = _validate_positive_number(known_width_mm, "known_width_mm")
    known_height = _validate_positive_number(known_height_mm, "known_height_mm")
    points = _validate_corners(corners)

    top_px = _distance(points[0], points[1])
    right_px = _distance(points[1], points[2])
    bottom_px = _distance(points[2], points[3])
    left_px = _distance(points[3], points[0])

    pixel_width = (top_px + bottom_px) / 2.0
    pixel_height = (left_px + right_px) / 2.0

    if pixel_width <= 0:
        raise ValueError("Mat pixel width must be greater than 0.")
    if pixel_height <= 0:
        raise ValueError("Mat pixel height must be greater than 0.")

    mm_per_pixel_x = known_width / pixel_width
    mm_per_pixel_y = known_height / pixel_height
    pixels_per_mm_x = pixel_width / known_width
    pixels_per_mm_y = pixel_height / known_height
    confidence = (
        _edge_consistency(top_px, bottom_px) + _edge_consistency(left_px, right_px)
    ) / 2.0

    return {
        "status": "computed",
        "known_width_mm": _round_float(known_width),
        "known_height_mm": _round_float(known_height),
        "image_width_px": _optional_int(image_width_px, "image_width_px"),
        "image_height_px": _optional_int(image_height_px, "image_height_px"),
        "corners": [[_round_float(x), _round_float(y)] for x, y in points],
        "edge_lengths_px": {
            "top": _round_float(top_px),
            "right": _round_float(right_px),
            "bottom": _round_float(bottom_px),
            "left": _round_float(left_px),
        },
        "pixel_width_px": _round_float(pixel_width),
        "pixel_height_px": _round_float(pixel_height),
        "pixel_to_mm_x": _round_float(mm_per_pixel_x),
        "pixel_to_mm_y": _round_float(mm_per_pixel_y),
        "mm_per_pixel_x": _round_float(mm_per_pixel_x),
        "mm_per_pixel_y": _round_float(mm_per_pixel_y),
        "pixels_per_mm_x": _round_float(pixels_per_mm_x),
        "pixels_per_mm_y": _round_float(pixels_per_mm_y),
        "confidence": _round_float(confidence, digits=4),
    }


def apply_calibration_to_active_profile(calibration: dict) -> dict:
    if not isinstance(calibration, dict):
        raise ValueError("Calibration must be a dictionary.")

    required_fields = [
        "pixel_to_mm_x",
        "pixel_to_mm_y",
        "mm_per_pixel_x",
        "mm_per_pixel_y",
        "pixels_per_mm_x",
        "pixels_per_mm_y",
        "confidence",
    ]
    missing_fields = [
        field
        for field in required_fields
        if field not in calibration or calibration.get(field) is None
    ]
    if missing_fields:
        raise ValueError(f"Calibration is missing required fields: {', '.join(missing_fields)}")

    calibration_update = {
        "calibration": {
            "status": "calibrated",
            "known_width_mm": calibration.get("known_width_mm"),
            "known_height_mm": calibration.get("known_height_mm"),
            "pixel_to_mm_x": calibration["pixel_to_mm_x"],
            "pixel_to_mm_y": calibration["pixel_to_mm_y"],
            "mm_per_pixel_x": calibration["mm_per_pixel_x"],
            "mm_per_pixel_y": calibration["mm_per_pixel_y"],
            "pixels_per_mm_x": calibration["pixels_per_mm_x"],
            "pixels_per_mm_y": calibration["pixels_per_mm_y"],
            "confidence": calibration["confidence"],
            "last_calibrated_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    return update_active_camera_profile(calibration_update)


def _deep_merge(target: dict, updates: dict) -> None:
    for key, value in updates.items():
        if (
            isinstance(value, dict)
            and isinstance(target.get(key), dict)
        ):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _validate_positive_number(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number greater than 0.") from exc

    if number <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")

    return number


def _validate_corners(corners: Any) -> list[tuple[float, float]]:
    if not isinstance(corners, list) or len(corners) != 4:
        raise ValueError("corners must contain exactly 4 points.")

    return [_coerce_point(point, index) for index, point in enumerate(corners)]


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer when provided.") from exc


def _coerce_point(point: Any, index: int) -> tuple[float, float]:
    if isinstance(point, dict):
        raw_x = point.get("x")
        raw_y = point.get("y")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        raw_x = point[0]
        raw_y = point[1]
    else:
        raise ValueError(f"corners[{index}] must contain x and y values.")

    try:
        return float(raw_x), float(raw_y)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"corners[{index}] x and y values must be numeric.") from exc


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _edge_consistency(a: float, b: float) -> float:
    largest = max(abs(a), abs(b))
    if largest <= 0:
        return 0.0

    return max(0.0, min(1.0, 1.0 - (abs(a - b) / largest)))


def _round_float(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
