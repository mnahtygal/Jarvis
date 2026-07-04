from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
