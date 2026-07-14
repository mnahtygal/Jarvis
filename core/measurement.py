from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict

from core.calibration import get_active_camera_profile

MEASUREMENT_METHOD = "rotated_contour_measurement_v1"
MIN_AREA_PX = 150.0
MIN_AREA_RATIO = 0.0008
MAX_AREA_RATIO = 0.78
BORDER_MARGIN_RATIO = 0.012
MAX_BORDER_CONTACT_RATIO = 0.12
AMBIGUOUS_SCORE_DELTA = 0.025
MEASUREMENT_SUGGESTIONS = [
    "Use a rectified scan-mat image after successful mat detection.",
    "Place one contrasting flat object near the center of the mat.",
    "Keep the object separated from the image boundary and mat border.",
    "Improve lighting and reduce shadows or glare.",
    "Remove small loose items from the mat before measuring.",
]


def get_active_calibration() -> dict:
    try:
        profile = get_active_camera_profile()
    except Exception as exc:
        return _unready_calibration(str(exc))

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
        import numpy as np
    except Exception:
        return _failure_result(
            "OpenCV and NumPy are required for measurement.",
            "opencv_missing",
            calibration=active_calibration,
        )

    path = Path(image_path)
    if not path.is_file():
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
    masks = _candidate_masks(image, cv2, np)
    rejected = {
        "below_minimum_area": 0,
        "implausibly_large": 0,
        "border_contact": 0,
        "invalid_geometry": 0,
        "duplicate": 0,
    }
    candidates: list[dict[str, Any]] = []
    total_contours = 0
    boundary_rejections = 0

    for strategy, mask in masks:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        total_contours += len(contours)
        for contour in contours:
            candidate, reason = _score_candidate(
                contour, strategy, image_width, image_height, image_area, cv2
            )
            if reason:
                rejected[reason] += 1
                if reason in {"border_contact", "implausibly_large"}:
                    boundary_rejections += 1
                continue
            if any(_bbox_iou(candidate["bbox"], existing["bbox"]) > 0.9 for existing in candidates):
                rejected["duplicate"] += 1
                continue
            candidates.append(candidate)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    diagnostics = _base_diagnostics(image_width, image_height, active_calibration)
    diagnostics.update({
        "threshold_strategies_attempted": [name for name, _ in masks],
        "contour_count": total_contours,
        "total_contour_count": total_contours,
        "candidate_count": len(candidates),
        "rejected_candidate_counts": rejected,
        "candidate_scores": [_candidate_diagnostic(item) for item in candidates[:8]],
    })

    if not candidates:
        reason = "object_touching_image_boundary" if boundary_rejections else "no_object_found"
        message = (
            "Object candidates touch the image boundary or resemble the mat frame."
            if boundary_rejections
            else "No measurable object contour found."
        )
        diagnostics["failure_reason"] = reason
        diagnostics["suggestions"] = MEASUREMENT_SUGGESTIONS
        return _failure_payload(message, active_calibration, diagnostics)

    selected = candidates[0]
    if len(candidates) > 1 and _is_ambiguous(candidates[0], candidates[1]):
        diagnostics["failure_reason"] = "ambiguous_object_candidates"
        diagnostics["selected_candidate_score"] = _round_float(selected["score"])
        diagnostics["suggestions"] = MEASUREMENT_SUGGESTIONS
        return _failure_payload(
            "Multiple similarly strong object candidates were found.",
            active_calibration,
            diagnostics,
        )

    contour = selected["contour"]
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect).astype(float)
    mm_x = float(active_calibration["mm_per_pixel_x"])
    mm_y = float(active_calibration["mm_per_pixel_y"])
    edge_measurement = rotated_box_physical_dimensions(box, mm_x, mm_y)
    x, y, width, height = cv2.boundingRect(contour)
    center_x, center_y = float(rect[0][0]), float(rect[0][1])
    contour_area_px = float(cv2.contourArea(contour))
    contour_area_mm2 = contour_area_px * mm_x * mm_y
    axis_area_mm2 = float(width * height) * mm_x * mm_y
    rotated_area_mm2 = edge_measurement["long_side_mm"] * edge_measurement["short_side_mm"]
    confidence = _measurement_confidence(
        selected["score"], active_calibration.get("confidence"), selected["border_contact_ratio"]
    )

    mask_image = np.zeros((image_height, image_width), dtype=np.uint8)
    cv2.drawContours(mask_image, [contour], -1, 255, thickness=cv2.FILLED)
    mask_path = path.with_name(f"{path.stem}_measurement_mask.png")
    overlay_path = path.with_name(f"{path.stem}_measurement_overlay.jpg")
    overlay = _draw_overlay(
        image.copy(), contour, box, (center_x, center_y), edge_measurement,
        confidence, cv2, np,
    )
    if not cv2.imwrite(str(mask_path), mask_image):
        diagnostics["failure_reason"] = "mask_write_failure"
        return _failure_payload("Could not write measurement mask artifact.", active_calibration, diagnostics)
    if not cv2.imwrite(str(overlay_path), overlay):
        diagnostics["failure_reason"] = "overlay_write_failure"
        return _failure_payload("Could not write measurement overlay artifact.", active_calibration, diagnostics)

    bbox_px = {"x": int(x), "y": int(y), "width": int(width), "height": int(height)}
    diagnostics.update({
        "selected_candidate_score": _round_float(selected["score"]),
        "selected_area_ratio": _round_float(selected["area_ratio"]),
        "selected_solidity": _round_float(selected["solidity"]),
        "selected_extent": _round_float(selected["extent"]),
        "border_contact_ratio": _round_float(selected["border_contact_ratio"]),
        "selected_strategy": selected["strategy"],
        "failure_reason": None,
        "suggestions": [],
    })
    long_mm = _round_float(edge_measurement["long_side_mm"])
    short_mm = _round_float(edge_measurement["short_side_mm"])
    angle = _round_float(edge_measurement["rotation_degrees"], digits=2)
    return {
        "ok": True,
        "measurement": {
            "bbox_px": bbox_px,
            "contour_px": [
                {"x": int(point[0][0]), "y": int(point[0][1])}
                for point in contour
            ],
            "bbox_mm": {  # Legacy axis-aligned fields.
                "width": _round_float(width * mm_x),
                "height": _round_float(height * mm_y),
            },
            "rotated_box_px": {
                "points": [{"x": _round_float(p[0], 2), "y": _round_float(p[1], 2)} for p in box],
                "center": {"x": _round_float(center_x, 2), "y": _round_float(center_y, 2)},
                "long_side": _round_float(edge_measurement["long_side_px"]),
                "short_side": _round_float(edge_measurement["short_side_px"]),
                "rotation_degrees": angle,
            },
            "dimensions_mm": {
                "long_side": long_mm,
                "short_side": short_mm,
                "width": long_mm,
                "height": short_mm,
            },
            "center_px": {"x": _round_float(center_x, 2), "y": _round_float(center_y, 2)},
            "center_mm": {"x": _round_float(center_x * mm_x), "y": _round_float(center_y * mm_y)},
            "area_px": _round_float(contour_area_px, 2),
            "area_mm2": _round_float(contour_area_mm2),
            "contour_area_px": _round_float(contour_area_px, 2),
            "contour_area_mm2": _round_float(contour_area_mm2),
            "axis_aligned_bbox_area_mm2": _round_float(axis_area_mm2),
            "rotated_bbox_area_mm2": _round_float(rotated_area_mm2),
            "confidence": confidence,
            "method": MEASUREMENT_METHOD,
            "angle_convention": "clockwise degrees from image +X to the physical long side, normalized to [-90, 90)",
            "artifacts": {"mask_path": str(mask_path), "overlay_path": str(overlay_path)},
        },
        "calibration": active_calibration,
        "diagnostics": diagnostics,
    }


def rotated_box_physical_dimensions(box_points: Any, mm_x: float, mm_y: float) -> dict[str, Any]:
    """Measure consecutive box edges with anisotropic scale and normalize sides."""
    points = [(float(point[0]), float(point[1])) for point in box_points]
    if len(points) != 4:
        raise ValueError("box_points must contain four points.")
    edges = []
    for index, start in enumerate(points):
        end = points[(index + 1) % 4]
        dx, dy = end[0] - start[0], end[1] - start[1]
        edges.append({
            "start": start,
            "end": end,
            "px": math.hypot(dx, dy),
            "mm": math.hypot(dx * mm_x, dy * mm_y),
            "physical_vector": (dx * mm_x, dy * mm_y),
        })
    side_a_mm = (edges[0]["mm"] + edges[2]["mm"]) / 2.0
    side_b_mm = (edges[1]["mm"] + edges[3]["mm"]) / 2.0
    side_a_px = (edges[0]["px"] + edges[2]["px"]) / 2.0
    side_b_px = (edges[1]["px"] + edges[3]["px"]) / 2.0
    long_index = 0 if side_a_mm >= side_b_mm else 1
    vector = edges[long_index]["physical_vector"]
    angle = math.degrees(math.atan2(vector[1], vector[0]))
    while angle >= 90.0:
        angle -= 180.0
    while angle < -90.0:
        angle += 180.0
    return {
        "long_side_mm": max(side_a_mm, side_b_mm),
        "short_side_mm": min(side_a_mm, side_b_mm),
        "long_side_px": side_a_px if long_index == 0 else side_b_px,
        "short_side_px": side_b_px if long_index == 0 else side_a_px,
        "rotation_degrees": angle,
        "long_edge": edges[long_index],
        "short_edge": edges[1 - long_index],
    }


def _candidate_masks(image: Any, cv2: Any, np: Any) -> list[tuple[str, Any]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    masks = []
    for name, mode in (("otsu_inverted", cv2.THRESH_BINARY_INV), ("otsu_normal", cv2.THRESH_BINARY)):
        _, mask = cv2.threshold(blurred, 0, 255, mode | cv2.THRESH_OTSU)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        masks.append((name, mask))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    _, hsv_mask = cv2.threshold(saturation, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    hsv_mask = cv2.morphologyEx(hsv_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    masks.append(("hsv_saturation", hsv_mask))
    edges = cv2.Canny(blurred, 40, 120)
    edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, edge_kernel, iterations=2)
    masks.append(("canny_closed", edges))
    return masks


def _score_candidate(contour: Any, strategy: str, width: int, height: int, image_area: float, cv2: Any):
    area = float(cv2.contourArea(contour))
    area_ratio = area / image_area if image_area else 0.0
    if area < max(MIN_AREA_PX, image_area * MIN_AREA_RATIO):
        return None, "below_minimum_area"
    if area_ratio > MAX_AREA_RATIO:
        return None, "implausibly_large"
    x, y, box_width, box_height = cv2.boundingRect(contour)
    if box_width <= 1 or box_height <= 1:
        return None, "invalid_geometry"
    margin = max(2, int(min(width, height) * BORDER_MARGIN_RATIO))
    points = contour.reshape(-1, 2)
    border_points = sum(
        1 for px, py in points
        if px <= margin or py <= margin or px >= width - 1 - margin or py >= height - 1 - margin
    )
    border_contact = border_points / max(1, len(points))
    touches_bbox = x <= margin or y <= margin or x + box_width >= width - margin or y + box_height >= height - margin
    if border_contact > MAX_BORDER_CONTACT_RATIO or (touches_bbox and area_ratio > 0.04):
        return None, "border_contact"
    hull_area = float(cv2.contourArea(cv2.convexHull(contour)))
    solidity = area / hull_area if hull_area > 0 else 0.0
    extent = area / float(box_width * box_height)
    moments = cv2.moments(contour)
    center_x = moments["m10"] / moments["m00"] if moments["m00"] else x + box_width / 2.0
    center_y = moments["m01"] / moments["m00"] if moments["m00"] else y + box_height / 2.0
    center_distance = math.hypot((center_x / width) - 0.5, (center_y / height) - 0.5) / math.sqrt(0.5)
    center_score = max(0.0, 1.0 - center_distance)
    area_score = min(1.0, area_ratio / 0.12) if area_ratio <= 0.35 else max(0.0, 1.0 - ((area_ratio - 0.35) / 0.43))
    boundary_clearance = max(0.0, 1.0 - border_contact)
    score = 0.30 * area_score + 0.22 * solidity + 0.18 * extent + 0.18 * center_score + 0.12 * boundary_clearance
    return {
        "contour": contour,
        "strategy": strategy,
        "area": area,
        "area_ratio": area_ratio,
        "bbox": {"x": x, "y": y, "width": box_width, "height": box_height},
        "solidity": solidity,
        "extent": extent,
        "border_contact_ratio": border_contact,
        "center": (center_x, center_y),
        "score": score,
    }, None


def _draw_overlay(image: Any, contour: Any, box: Any, center: tuple[float, float], physical: dict, confidence: float, cv2: Any, np: Any):
    box_int = np.round(box).astype(np.int32)
    cv2.drawContours(image, [contour], -1, (0, 200, 255), 2)
    cv2.polylines(image, [box_int], True, (0, 255, 0), 3)
    cv2.circle(image, (round(center[0]), round(center[1])), 6, (0, 0, 255), -1)
    for key, color in (("long_edge", (255, 80, 0)), ("short_edge", (255, 0, 255))):
        edge = physical[key]
        start = tuple(round(value) for value in edge["start"])
        end = tuple(round(value) for value in edge["end"])
        cv2.line(image, start, end, color, 4)
        midpoint = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
        cv2.putText(image, f'{edge["mm"]:.2f} mm', midpoint, cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)
    labels = [
        f"2D calibrated measurement | {MEASUREMENT_METHOD}",
        f'Long {physical["long_side_mm"]:.2f} mm  Short {physical["short_side_mm"]:.2f} mm',
        f'Rotation {physical["rotation_degrees"]:.2f} deg  Confidence {confidence * 100:.1f}%',
    ]
    for index, label in enumerate(labels):
        cv2.putText(image, label, (18, 30 + index * 28), cv2.FONT_HERSHEY_SIMPLEX, 0.66, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(image, label, (18, 30 + index * 28), cv2.FONT_HERSHEY_SIMPLEX, 0.66, (20, 20, 20), 1, cv2.LINE_AA)
    return image


def _is_ambiguous(first: dict, second: dict) -> bool:
    if first["score"] - second["score"] >= AMBIGUOUS_SCORE_DELTA:
        return False
    return _bbox_iou(first["bbox"], second["bbox"]) < 0.25


def _bbox_iou(a: dict, b: dict) -> float:
    left, top = max(a["x"], b["x"]), max(a["y"], b["y"])
    right = min(a["x"] + a["width"], b["x"] + b["width"])
    bottom = min(a["y"] + a["height"], b["y"] + b["height"])
    intersection = max(0, right - left) * max(0, bottom - top)
    union = a["width"] * a["height"] + b["width"] * b["height"] - intersection
    return intersection / union if union else 0.0


def _candidate_diagnostic(candidate: dict) -> dict:
    return {
        "strategy": candidate["strategy"],
        "score": _round_float(candidate["score"]),
        "area_ratio": _round_float(candidate["area_ratio"]),
        "solidity": _round_float(candidate["solidity"]),
        "extent": _round_float(candidate["extent"]),
        "border_contact_ratio": _round_float(candidate["border_contact_ratio"]),
        "bbox_px": candidate["bbox"],
    }


def _base_diagnostics(width: int | None, height: int | None, calibration: dict | None) -> dict:
    return {
        "image_width": width,
        "image_height": height,
        "threshold_strategies_attempted": [],
        "contour_count": 0,
        "total_contour_count": 0,
        "candidate_count": 0,
        "rejected_candidate_counts": {},
        "candidate_scores": [],
        "selected_candidate_score": None,
        "selected_area_ratio": None,
        "selected_solidity": None,
        "selected_extent": None,
        "border_contact_ratio": None,
        "calibration_confidence": (calibration or {}).get("confidence"),
        "failure_reason": None,
        "suggestions": [],
    }


def _failure_result(error: str, failure_reason: str, calibration: dict | None = None) -> Dict[str, Any]:
    diagnostics = _base_diagnostics(None, None, calibration)
    diagnostics.update({"failure_reason": failure_reason, "suggestions": MEASUREMENT_SUGGESTIONS})
    return _failure_payload(error, calibration, diagnostics)


def _failure_payload(error: str, calibration: dict | None, diagnostics: dict) -> Dict[str, Any]:
    return {"ok": False, "error": error, "calibration": calibration, "diagnostics": diagnostics}


def _measurement_confidence(score: float, calibration_confidence: Any, border_contact: float) -> float:
    try:
        calibration_score = float(calibration_confidence)
    except (TypeError, ValueError):
        calibration_score = 0.5
    combined = 0.55 * max(0.0, min(1.0, score)) + 0.35 * max(0.0, min(1.0, calibration_score)) + 0.10 * (1.0 - border_contact)
    return _round_float(combined, digits=4)


def _unready_calibration(error: str) -> dict:
    return {
        "ready": False, "profile_id": None, "profile_name": None,
        "mm_per_pixel_x": None, "mm_per_pixel_y": None,
        "pixels_per_mm_x": None, "pixels_per_mm_y": None,
        "confidence": None, "error": error,
    }


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _round_float(value: float, digits: int = 4) -> float:
    return round(float(value), digits)
