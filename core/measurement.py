from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from core.calibration import get_active_camera_profile

MEASUREMENT_METHOD = "largest_contour_bbox_v0"
MEASUREMENT_SUGGESTIONS = [
    "Use a rectified scan-mat image after successful mat detection.",
    "Place one main object on the mat with clear separation from the background.",
    "Improve lighting and reduce shadows or glare.",
    "Remove small loose items from the mat before measuring.",
]


def get_active_calibration() -> dict:
    try:
        profile = get_active_camera_profile()
    except Exception as exc:
        return {
            "ready": False,
            "profile_id": None,
            "profile_name": None,
            "mm_per_pixel_x": None,
            "mm_per_pixel_y": None,
            "pixels_per_mm_x": None,
            "pixels_per_mm_y": None,
            "confidence": None,
            "error": str(exc),
        }

    calibration = profile.get("calibration", {})
    mm_per_pixel_x = calibration.get("mm_per_pixel_x")
    mm_per_pixel_y = calibration.get("mm_per_pixel_y")
    pixels_per_mm_x = calibration.get("pixels_per_mm_x")
    pixels_per_mm_y = calibration.get("pixels_per_mm_y")
    confidence = calibration.get("confidence")
    ready = (
        calibration.get("status") == "calibrated"
        and _positive_number(mm_per_pixel_x)
        and _positive_number(mm_per_pixel_y)
        and _positive_number(pixels_per_mm_x)
        and _positive_number(pixels_per_mm_y)
    )

    return {
        "ready": ready,
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "mm_per_pixel_x": mm_per_pixel_x,
        "mm_per_pixel_y": mm_per_pixel_y,
        "pixels_per_mm_x": pixels_per_mm_x,
        "pixels_per_mm_y": pixels_per_mm_y,
        "confidence": confidence,
        "error": None if ready else "Active camera profile is not calibrated.",
    }


def measure_object_bbox_from_image(
    image_path: str,
    calibration: dict | None = None,
) -> Dict[str, Any]:
    active_calibration = calibration or get_active_calibration()
    if not active_calibration.get("ready"):
        return _failure_result(
            "Calibration is required before measurement.",
            "calibration_not_ready",
            calibration=active_calibration,
        )

    try:
        import cv2
    except Exception:
        return _failure_result(
            "OpenCV is not installed. Run: pip install opencv-python-headless numpy",
            "opencv_missing",
            calibration=active_calibration,
        )

    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return _failure_result(
            "Image file does not exist.",
            "image_file_missing",
            calibration=active_calibration,
        )

    image = cv2.imread(str(path))
    if image is None:
        return _failure_result(
            "OpenCV could not read image.",
            "opencv_read_failed",
            calibration=active_calibration,
        )

    image_height, image_width = image.shape[:2]
    image_area = float(image_width * image_height)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    candidates = []
    total_contours = 0
    for threshold_mode in [cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY]:
        _, mask = cv2.threshold(
            blurred,
            0,
            255,
            threshold_mode | cv2.THRESH_OTSU,
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        total_contours += len(contours)

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < max(100.0, image_area * 0.001):
                continue
            if area > image_area * 0.85:
                continue

            x, y, width, height = cv2.boundingRect(contour)
            candidates.append({
                "area": area,
                "area_ratio": area / image_area if image_area else 0.0,
                "bbox": {
                    "x": int(x),
                    "y": int(y),
                    "width": int(width),
                    "height": int(height),
                },
            })

    diagnostics = {
        "image_width": int(image_width),
        "image_height": int(image_height),
        "contour_count": total_contours,
        "candidate_count": len(candidates),
        "selected_area_ratio": None,
        "failure_reason": None,
        "suggestions": [],
    }

    if not candidates:
        diagnostics["failure_reason"] = "no_object_contours_found"
        diagnostics["suggestions"] = MEASUREMENT_SUGGESTIONS
        return {
            "ok": False,
            "error": "No measurable object contour found.",
            "calibration": active_calibration,
            "diagnostics": diagnostics,
        }

    candidates.sort(key=lambda item: item["area"], reverse=True)
    selected = candidates[0]
    bbox_px = selected["bbox"]
    mm_per_pixel_x = float(active_calibration["mm_per_pixel_x"])
    mm_per_pixel_y = float(active_calibration["mm_per_pixel_y"])
    width_mm = bbox_px["width"] * mm_per_pixel_x
    height_mm = bbox_px["height"] * mm_per_pixel_y
    area_mm2 = selected["area"] * mm_per_pixel_x * mm_per_pixel_y
    diagnostics["selected_area_ratio"] = _round_float(selected["area_ratio"])

    return {
        "ok": True,
        "measurement": {
            "bbox_px": bbox_px,
            "bbox_mm": {
                "width": _round_float(width_mm),
                "height": _round_float(height_mm),
            },
            "area_px": _round_float(selected["area"], digits=2),
            "area_mm2": _round_float(area_mm2),
            "confidence": _measurement_confidence(
                selected["area_ratio"],
                active_calibration.get("confidence"),
            ),
            "method": MEASUREMENT_METHOD,
        },
        "calibration": active_calibration,
        "diagnostics": diagnostics,
    }


def _failure_result(
    error: str,
    failure_reason: str,
    calibration: dict | None = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": error,
        "calibration": calibration,
        "diagnostics": {
            "image_width": None,
            "image_height": None,
            "contour_count": 0,
            "candidate_count": 0,
            "selected_area_ratio": None,
            "failure_reason": failure_reason,
            "suggestions": MEASUREMENT_SUGGESTIONS,
        },
    }


def _measurement_confidence(area_ratio: float, calibration_confidence: Any) -> float:
    try:
        calibration_score = float(calibration_confidence)
    except (TypeError, ValueError):
        calibration_score = 0.5

    object_score = max(0.1, min(1.0, area_ratio * 8.0))
    return _round_float((calibration_score + object_score) / 2.0, digits=4)


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _round_float(value: float, digits: int = 4) -> float:
    return round(float(value), digits)
