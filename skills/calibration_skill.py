from __future__ import annotations

from typing import Any, Dict

from core.calibration import get_active_camera_profile, load_camera_profiles


def get_calibration_status() -> Dict[str, Any]:
    try:
        profile = get_active_camera_profile()
        profiles_data = load_camera_profiles()
    except Exception as exc:
        return {
            "ready": False,
            "active_profile_id": None,
            "profile_name": None,
            "status": "unknown",
            "known_width_mm": None,
            "known_height_mm": None,
            "pixel_to_mm_x": None,
            "pixel_to_mm_y": None,
            "mm_per_pixel_x": None,
            "mm_per_pixel_y": None,
            "pixels_per_mm_x": None,
            "pixels_per_mm_y": None,
            "confidence": None,
            "last_calibrated_at": None,
            "error": str(exc),
        }

    calibration = profile.get("calibration", {})
    scan_mat = profile.get("scan_mat", {})
    status = calibration.get("status", "unknown")
    pixel_to_mm_x = calibration.get("pixel_to_mm_x")
    pixel_to_mm_y = calibration.get("pixel_to_mm_y")
    mm_per_pixel_x = calibration.get("mm_per_pixel_x")
    mm_per_pixel_y = calibration.get("mm_per_pixel_y")
    pixels_per_mm_x = calibration.get("pixels_per_mm_x")
    pixels_per_mm_y = calibration.get("pixels_per_mm_y")
    confidence = calibration.get("confidence")

    ready = all(
        value is not None
        for value in [
            pixel_to_mm_x,
            pixel_to_mm_y,
            mm_per_pixel_x,
            mm_per_pixel_y,
            pixels_per_mm_x,
            pixels_per_mm_y,
            confidence,
        ]
    ) and status == "calibrated"

    return {
        "ready": ready,
        "active_profile_id": profiles_data.get("active_profile_id"),
        "profile_name": profile.get("name"),
        "status": status,
        "known_width_mm": scan_mat.get("known_width_mm"),
        "known_height_mm": scan_mat.get("known_height_mm"),
        "pixel_to_mm_x": pixel_to_mm_x,
        "pixel_to_mm_y": pixel_to_mm_y,
        "mm_per_pixel_x": mm_per_pixel_x,
        "mm_per_pixel_y": mm_per_pixel_y,
        "pixels_per_mm_x": pixels_per_mm_x,
        "pixels_per_mm_y": pixels_per_mm_y,
        "confidence": confidence,
        "last_calibrated_at": calibration.get("last_calibrated_at"),
        "error": None,
    }
