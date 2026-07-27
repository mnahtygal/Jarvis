from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from core.calibration import (
    get_active_camera_profile,
    rectified_metadata_path,
    validate_rectified_provenance,
)
from core.camera_roles import get_camera_roles_status
from core.scan_mat_geometry import (
    MAT_HEIGHT_MM,
    MAT_WIDTH_MM,
    RECTIFIED_HEIGHT_PX,
    RECTIFIED_WIDTH_PX,
)

MEASUREMENT_METHOD = "rotated_contour_measurement_v1"
MEASUREMENT_PIPELINE = "vision_lab_accuracy_v2"
MIN_AREA_PX = 150.0
MIN_AREA_RATIO = 0.0025
MAX_AREA_RATIO = 0.78
BORDER_MARGIN_RATIO = 0.025
MAX_BORDER_CONTACT_RATIO = 0.12
AMBIGUOUS_SCORE_DELTA = 0.025
MIN_SOLIDITY = 0.18
MIN_EXTENT = 0.08
MAX_GRID_LINE_ASPECT_RATIO = 45.0
DUPLICATE_BBOX_IOU_THRESHOLD = 0.72
DUPLICATE_CONTOUR_IOU_THRESHOLD = 0.72
# Require moderate combined normalized evidence beyond the individual shape filters.
MIN_CANDIDATE_SCORE = 0.35
MAX_DIAGNOSTIC_CANDIDATES = 8
MAX_OBJECT_CANDIDATES = 64
MEASUREMENT_SUGGESTIONS = [
    "Use a rectified scan-mat image after successful mat detection.",
    "Place one contrasting flat object near the center of the mat.",
    "Keep the object separated from the image boundary and mat border.",
    "Improve lighting and reduce shadows or glare.",
    "Remove small loose items from the mat before measuring.",
]


@dataclass(frozen=True)
class SegmentationResult:
    masks: list[tuple[str, Any]]
    usable_margin_px: int
    usable_area_px: int
    grid_line_pixels: int


def get_active_calibration(image_path: str | Path | None = None) -> dict:
    if image_path is not None:
        return _calibration_for_rectified_artifact(Path(image_path))
    try:
        profile = get_active_camera_profile()
    except Exception as exc:
        return _unready_calibration(str(exc))

    calibration = profile.get("calibration", {})
    scan_mat = profile.get("scan_mat", {})
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
        "known_width_mm": (
            scan_mat.get("known_width_mm") or calibration.get("known_width_mm")
        ),
        "known_height_mm": (
            scan_mat.get("known_height_mm") or calibration.get("known_height_mm")
        ),
        "error": None if ready else "Active camera profile is not calibrated.",
    }


def measure_object_bbox_from_image(
    image_path: str,
    calibration: dict | None = None,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    active_calibration = calibration or get_active_calibration(image_path)
    if not active_calibration.get("ready"):
        return _failure_result(
            "Calibration is required before measurement.",
            "calibration_not_ready",
            calibration=active_calibration,
            processing_ms=_elapsed_ms(started_at),
        )

    try:
        import cv2
        import numpy as np
    except Exception:
        return _failure_result(
            "OpenCV and NumPy are required for measurement.",
            "opencv_missing",
            calibration=active_calibration,
            processing_ms=_elapsed_ms(started_at),
        )

    path = Path(image_path)
    if not path.is_file():
        return _failure_result(
            "Image file does not exist.",
            "image_file_missing",
            calibration=active_calibration,
            processing_ms=_elapsed_ms(started_at),
        )

    image = cv2.imread(str(path))
    if image is None:
        return _failure_result(
            "OpenCV could not read image.",
            "opencv_read_failed",
            calibration=active_calibration,
            processing_ms=_elapsed_ms(started_at),
        )

    image_height, image_width = image.shape[:2]
    expected_rectified = active_calibration.get("rectified_output_dimensions")
    if expected_rectified and (
        int(expected_rectified.get("width", 0)) != image_width
        or int(expected_rectified.get("height", 0)) != image_height
    ):
        return _failure_result(
            "Rectified image geometry does not match its calibration profile.",
            "calibration_geometry_mismatch",
            calibration=active_calibration,
            processing_ms=_elapsed_ms(started_at),
        )
    segmentation = _segment_object_masks(image, cv2, np)
    masks = segmentation.masks
    rejected = {
        "below_minimum_area": 0,
        "implausibly_large": 0,
        "border_contact": 0,
        "invalid_geometry": 0,
        "low_solidity": 0,
        "low_extent": 0,
        "grid_line_like": 0,
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
                contour,
                strategy,
                image_width,
                image_height,
                float(segmentation.usable_area_px),
                segmentation.usable_margin_px,
                cv2,
            )
            if reason:
                rejected[reason] += 1
                if reason == "border_contact":
                    boundary_rejections += 1
                continue
            duplicate = next(
                (
                    existing
                    for existing in candidates
                    if _candidates_represent_same_object(
                        existing, candidate, cv2, np
                    )
                ),
                None,
            )
            if duplicate is not None:
                rejected["duplicate"] += 1
                _merge_candidate(duplicate, candidate)
                continue
            candidates.append(candidate)

    for candidate in candidates:
        consensus_bonus = min(0.12, 0.04 * (len(candidate["strategies"]) - 1))
        candidate["consensus_bonus"] = consensus_bonus
        candidate["score"] = min(1.0, candidate["base_score"] + consensus_bonus)
    _apply_enclosing_structure_penalties(candidates)
    candidates.sort(key=lambda item: item["score"], reverse=True)
    diagnostics = _base_diagnostics(image_width, image_height, active_calibration)
    diagnostics.update({
        "threshold_strategies_attempted": [name for name, _ in masks],
        "contour_count": total_contours,
        "total_contour_count": total_contours,
        "candidate_count": len(candidates),
        "rejected_candidate_counts": rejected,
        "candidate_scores": [
            _candidate_diagnostic(item) for item in candidates[:MAX_DIAGNOSTIC_CANDIDATES]
        ],
        "usable_border_margin_px": segmentation.usable_margin_px,
        "usable_area_px": segmentation.usable_area_px,
        "grid_line_pixels_suppressed": segmentation.grid_line_pixels,
        "minimum_candidate_score": MIN_CANDIDATE_SCORE,
        "processing_ms": _elapsed_ms(started_at),
    })

    if len(candidates) > MAX_OBJECT_CANDIDATES:
        diagnostics["failure_reason"] = "no_object_found"
        diagnostics["background_structure_detected"] = True
        diagnostics["suggestions"] = MEASUREMENT_SUGGESTIONS
        return _failure_payload(
            "No single object could be isolated from repeated background structure.",
            active_calibration,
            diagnostics,
        )

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
    if not _candidate_score_is_acceptable(selected["score"]):
        diagnostics["failure_reason"] = "candidate_score_below_threshold"
        diagnostics["selected_candidate_score"] = _round_float(selected["score"])
        diagnostics["suggestions"] = MEASUREMENT_SUGGESTIONS
        return _failure_payload(
            "The strongest object candidate did not meet the minimum confidence score.",
            active_calibration,
            diagnostics,
        )
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
    box = _order_box_points(cv2.boxPoints(rect).astype(float), np)
    scale = _measurement_scale(active_calibration, image_width, image_height)
    mm_x = scale["mm_per_pixel_x"]
    mm_y = scale["mm_per_pixel_y"]
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
        confidence, selected, segmentation.usable_margin_px, cv2, np,
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
        "selected_strategies": selected["strategies"],
        "selected_strategy_count": len(selected["strategies"]),
        "selected_aspect_ratio": _round_float(selected["aspect_ratio"]),
        "selected_border_distance_px": _round_float(selected["border_distance_px"], 2),
        "selected_geometry": {
            "bbox_px": selected["bbox"],
            "rotated_long_side_px": _round_float(selected["rotated_long_side_px"], 2),
            "rotated_short_side_px": _round_float(selected["rotated_short_side_px"], 2),
            "aspect_ratio": _round_float(selected["aspect_ratio"]),
        },
        "selected_contour_point_count": len(contour),
        "calibration_source": scale["source"],
        "measurement_mm_per_pixel_x": _round_float(mm_x, 8),
        "measurement_mm_per_pixel_y": _round_float(mm_y, 8),
        "failure_reason": None,
        "suggestions": [],
        "processing_ms": _elapsed_ms(started_at),
    })
    long_mm = _round_float(edge_measurement["long_side_mm"])
    short_mm = _round_float(edge_measurement["short_side_mm"])
    angle = _round_float(edge_measurement["rotation_degrees"], digits=2)
    return {
        "ok": True,
        "status": "ready",
        "calibrated": True,
        "unit": "mm",
        "measurement": {
            "bbox_px": bbox_px,
            "contour_px": [
                {"x": int(point[0][0]), "y": int(point[0][1])}
                for point in contour
            ],
            "simplified_contour_px": _simplified_contour_points(contour, cv2),
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
            "calibration_source": scale["source"],
            "mm_per_pixel_x": _round_float(mm_x, 8),
            "mm_per_pixel_y": _round_float(mm_y, 8),
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


def _segment_object_masks(image: Any, cv2: Any, np: Any) -> SegmentationResult:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    blurred = cv2.GaussianBlur(clahe, (5, 5), 0)
    kernel_size = 3 if min(width, height) < 500 else 5
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    grid_mask = _grid_line_mask(blurred, cv2, np)
    margin = max(3, int(round(min(width, height) * BORDER_MARGIN_RATIO)))
    usable_mask = np.zeros((height, width), dtype=np.uint8)
    if width > margin * 2 and height > margin * 2:
        cv2.rectangle(
            usable_mask,
            (margin, margin),
            (width - 1 - margin, height - 1 - margin),
            255,
            thickness=cv2.FILLED,
        )

    def clean(mask: Any) -> Any:
        cleaned = cv2.bitwise_and(mask, cv2.bitwise_not(grid_mask))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=2)
        return cv2.bitwise_and(cleaned, usable_mask)

    masks: list[tuple[str, Any]] = []
    for name, mode in (
        ("clahe_otsu_inverted", cv2.THRESH_BINARY_INV),
        ("clahe_otsu_normal", cv2.THRESH_BINARY),
    ):
        _, mask = cv2.threshold(blurred, 0, 255, mode | cv2.THRESH_OTSU)
        masks.append((name, clean(mask)))

    adaptive_block_size = max(15, min(51, int(min(width, height) * 0.06) | 1))
    for name, mode in (
        ("adaptive_inverted", cv2.THRESH_BINARY_INV),
        ("adaptive_normal", cv2.THRESH_BINARY),
    ):
        mask = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            mode,
            adaptive_block_size,
            5,
        )
        masks.append((name, clean(mask)))

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    _, hsv_mask = cv2.threshold(saturation, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    hsv_mask = cv2.bitwise_and(hsv_mask, cv2.inRange(value, 35, 255))
    hsv_open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    hsv_mask = cv2.morphologyEx(hsv_mask, cv2.MORPH_OPEN, hsv_open_kernel, iterations=1)
    chroma_kernel_size = max(9, min(51, int(min(width, height) * 0.04) | 1))
    chroma_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (chroma_kernel_size, chroma_kernel_size)
    )
    hsv_mask = cv2.morphologyEx(hsv_mask, cv2.MORPH_CLOSE, chroma_kernel, iterations=2)
    chroma_cleanup_size = max(5, min(15, int(min(width, height) * 0.01) | 1))
    chroma_cleanup_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (chroma_cleanup_size, chroma_cleanup_size)
    )
    hsv_mask = cv2.morphologyEx(
        hsv_mask, cv2.MORPH_OPEN, chroma_cleanup_kernel, iterations=1
    )
    hsv_mask = cv2.bitwise_and(hsv_mask, usable_mask)
    masks.append(("hsv_chroma_connected", hsv_mask))

    background_sigma = max(7.0, min(width, height) * 0.035)
    local_background = cv2.GaussianBlur(clahe, (0, 0), sigmaX=background_sigma)
    background_difference = cv2.absdiff(clahe, local_background)
    _, difference_mask = cv2.threshold(
        background_difference, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )
    masks.append(("local_background_difference", clean(difference_mask)))

    return SegmentationResult(
        masks=masks,
        usable_margin_px=margin,
        usable_area_px=int(cv2.countNonZero(usable_mask)),
        grid_line_pixels=int(cv2.countNonZero(grid_mask)),
    )


def _grid_line_mask(gray: Any, cv2: Any, np: Any) -> Any:
    height, width = gray.shape[:2]
    block_size = max(15, min(51, int(min(width, height) * 0.05) | 1))
    line_mask = np.zeros_like(gray)
    max_thickness = max(3, int(round(min(width, height) * 0.012)))

    for threshold_mode in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            threshold_mode,
            block_size,
            4,
        )
        for orientation, kernel_shape in (
            ("horizontal", (max(15, int(width * 0.06)), 1)),
            ("vertical", (1, max(15, int(height * 0.06)))),
        ):
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_shape)
            opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
            contours, _ = cv2.findContours(
                opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for contour in contours:
                _, _, box_width, box_height = cv2.boundingRect(contour)
                long_side = box_width if orientation == "horizontal" else box_height
                short_side = box_height if orientation == "horizontal" else box_width
                minimum_length = (
                    width * 0.06 if orientation == "horizontal" else height * 0.06
                )
                if long_side >= minimum_length and short_side <= max_thickness:
                    cv2.drawContours(
                        line_mask, [contour], -1, 255, thickness=cv2.FILLED
                    )

    dilation = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.dilate(line_mask, dilation, iterations=1)


def _score_candidate(
    contour: Any,
    strategy: str,
    width: int,
    height: int,
    usable_area: float,
    usable_margin: int,
    cv2: Any,
):
    area = float(cv2.contourArea(contour))
    area_ratio = area / usable_area if usable_area else 0.0
    if area < max(MIN_AREA_PX, usable_area * MIN_AREA_RATIO):
        return None, "below_minimum_area"
    if area_ratio > MAX_AREA_RATIO:
        return None, "implausibly_large"
    x, y, box_width, box_height = cv2.boundingRect(contour)
    if box_width <= 1 or box_height <= 1:
        return None, "invalid_geometry"
    points = contour.reshape(-1, 2)
    border_points = sum(
        1 for px, py in points
        if px <= usable_margin + 1
        or py <= usable_margin + 1
        or px >= width - 2 - usable_margin
        or py >= height - 2 - usable_margin
    )
    border_contact = border_points / max(1, len(points))
    border_distance = min(
        x - usable_margin,
        y - usable_margin,
        width - usable_margin - (x + box_width),
        height - usable_margin - (y + box_height),
    )
    touches_bbox = border_distance <= 1
    if border_contact > MAX_BORDER_CONTACT_RATIO or touches_bbox:
        return None, "border_contact"
    hull_area = float(cv2.contourArea(cv2.convexHull(contour)))
    solidity = area / hull_area if hull_area > 0 else 0.0
    if solidity < MIN_SOLIDITY:
        return None, "low_solidity"
    extent = area / float(box_width * box_height)
    if extent < MIN_EXTENT:
        return None, "low_extent"
    rotated_rect = cv2.minAreaRect(contour)
    rotated_width, rotated_height = [float(value) for value in rotated_rect[1]]
    rotated_short_side = min(rotated_width, rotated_height)
    rotated_long_side = max(rotated_width, rotated_height)
    if rotated_short_side <= 1.0 or rotated_long_side <= 1.0:
        return None, "invalid_geometry"
    aspect_ratio = rotated_long_side / rotated_short_side
    thin_limit = max(3.0, min(width, height) * 0.012)
    if aspect_ratio > MAX_GRID_LINE_ASPECT_RATIO or (
        aspect_ratio > 20.0 and rotated_short_side <= thin_limit
    ):
        return None, "grid_line_like"
    moments = cv2.moments(contour)
    center_x = moments["m10"] / moments["m00"] if moments["m00"] else x + box_width / 2.0
    center_y = moments["m01"] / moments["m00"] if moments["m00"] else y + box_height / 2.0
    center_distance = math.hypot((center_x / width) - 0.5, (center_y / height) - 0.5) / math.sqrt(0.5)
    center_score = max(0.0, 1.0 - center_distance)
    area_score = min(1.0, area_ratio / 0.12) if area_ratio <= 0.35 else max(0.0, 1.0 - ((area_ratio - 0.35) / 0.43))
    boundary_clearance = min(
        1.0,
        max(0.0, border_distance) / max(1.0, min(width, height) * 0.15),
    )
    shape_stability = min(1.0, rotated_short_side / max(3.0, min(width, height) * 0.025))
    strategy_adjustment = {
        "hsv_chroma_connected": 0.05,
        "local_background_difference": -0.20,
    }.get(strategy, 0.0)
    score = max(0.0, (
        0.28 * area_score
        + 0.18 * solidity
        + 0.14 * extent
        + 0.14 * center_score
        + 0.14 * boundary_clearance
        + 0.12 * shape_stability
        + strategy_adjustment
    ))
    return {
        "contour": contour,
        "strategy": strategy,
        "strategy_priority": _strategy_priority(strategy),
        "area": area,
        "area_ratio": area_ratio,
        "bbox": {"x": x, "y": y, "width": box_width, "height": box_height},
        "solidity": solidity,
        "extent": extent,
        "border_contact_ratio": border_contact,
        "border_distance_px": float(border_distance),
        "center": (center_x, center_y),
        "aspect_ratio": aspect_ratio,
        "rotated_long_side_px": rotated_long_side,
        "rotated_short_side_px": rotated_short_side,
        "strategies": [strategy],
        "base_score": score,
        "strategy_adjustment": strategy_adjustment,
        "score": score,
    }, None


def _merge_candidate(existing: dict, candidate: dict) -> None:
    strategies = list(dict.fromkeys([*existing["strategies"], *candidate["strategies"]]))
    if candidate["strategy_priority"] > existing["strategy_priority"]:
        existing.update(candidate)
    existing["strategies"] = strategies


def _apply_enclosing_structure_penalties(candidates: list[dict[str, Any]]) -> None:
    """Demote broad illumination regions that surround a clearer object."""
    for outer in candidates:
        outer["enclosing_structure_penalty"] = 0.0
        for inner in candidates:
            if inner is outer:
                continue
            if outer["area_ratio"] < inner["area_ratio"] * 3.0:
                continue
            if not _bbox_contains_center(outer["bbox"], inner["bbox"]):
                continue
            if inner["extent"] < outer["extent"] + 0.15:
                continue
            if inner["solidity"] <= outer["solidity"]:
                continue
            outer["enclosing_structure_penalty"] = 0.08
            outer["score"] = max(0.0, outer["score"] - 0.08)
            break


def _bbox_contains_center(outer: dict, inner: dict) -> bool:
    center_x = inner["x"] + inner["width"] / 2.0
    center_y = inner["y"] + inner["height"] / 2.0
    return (
        outer["x"] <= center_x <= outer["x"] + outer["width"]
        and outer["y"] <= center_y <= outer["y"] + outer["height"]
    )


def _strategy_priority(strategy: str) -> int:
    if strategy == "hsv_chroma_connected":
        return 4
    if strategy.startswith("clahe_otsu"):
        return 3
    if strategy.startswith("adaptive"):
        return 2
    return 1


def _draw_overlay(
    image: Any,
    contour: Any,
    box: Any,
    center: tuple[float, float],
    physical: dict,
    confidence: float,
    selected: dict,
    usable_margin: int,
    cv2: Any,
    np: Any,
):
    box_int = np.round(box).astype(np.int32)
    height, width = image.shape[:2]
    cv2.rectangle(
        image,
        (usable_margin, usable_margin),
        (width - 1 - usable_margin, height - 1 - usable_margin),
        (160, 160, 160),
        1,
    )
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
        f'Score {selected["score"]:.3f}  Strategies {len(selected["strategies"])}',
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


def _candidates_represent_same_object(
    first: dict,
    second: dict,
    cv2: Any,
    np: Any,
) -> bool:
    """Group cross-strategy contours only when their filled shapes agree."""
    if (
        _bbox_iou(first["bbox"], second["bbox"])
        < DUPLICATE_BBOX_IOU_THRESHOLD
    ):
        return False
    return (
        _contour_iou(first["contour"], second["contour"], cv2, np)
        >= DUPLICATE_CONTOUR_IOU_THRESHOLD
    )


def _contour_iou(first: Any, second: Any, cv2: Any, np: Any) -> float:
    first_points = first.reshape(-1, 2)
    second_points = second.reshape(-1, 2)
    left = int(min(first_points[:, 0].min(), second_points[:, 0].min()))
    top = int(min(first_points[:, 1].min(), second_points[:, 1].min()))
    right = int(max(first_points[:, 0].max(), second_points[:, 0].max()))
    bottom = int(max(first_points[:, 1].max(), second_points[:, 1].max()))
    width = right - left + 1
    height = bottom - top + 1
    if width <= 0 or height <= 0:
        return 0.0

    offset = np.array([[[left, top]]], dtype=np.int32)
    first_local = first.astype(np.int32) - offset
    second_local = second.astype(np.int32) - offset
    first_mask = np.zeros((height, width), dtype=np.uint8)
    second_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.drawContours(first_mask, [first_local], -1, 255, thickness=cv2.FILLED)
    cv2.drawContours(second_mask, [second_local], -1, 255, thickness=cv2.FILLED)
    intersection = cv2.countNonZero(cv2.bitwise_and(first_mask, second_mask))
    union = cv2.countNonZero(cv2.bitwise_or(first_mask, second_mask))
    return float(intersection) / float(union) if union else 0.0


def _candidate_score_is_acceptable(score: Any) -> bool:
    try:
        return float(score) >= MIN_CANDIDATE_SCORE
    except (TypeError, ValueError):
        return False


def _candidate_diagnostic(candidate: dict) -> dict:
    return {
        "strategy": candidate["strategy"],
        "strategies": candidate["strategies"],
        "strategy_count": len(candidate["strategies"]),
        "score": _round_float(candidate["score"]),
        "base_score": _round_float(candidate["base_score"]),
        "strategy_adjustment": _round_float(candidate.get("strategy_adjustment", 0.0)),
        "consensus_bonus": _round_float(candidate.get("consensus_bonus", 0.0)),
        "enclosing_structure_penalty": _round_float(
            candidate.get("enclosing_structure_penalty", 0.0)
        ),
        "area_ratio": _round_float(candidate["area_ratio"]),
        "solidity": _round_float(candidate["solidity"]),
        "extent": _round_float(candidate["extent"]),
        "aspect_ratio": _round_float(candidate["aspect_ratio"]),
        "border_contact_ratio": _round_float(candidate["border_contact_ratio"]),
        "border_distance_px": _round_float(candidate["border_distance_px"], 2),
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
        "selected_strategy": None,
        "selected_strategies": [],
        "selected_strategy_count": 0,
        "selected_aspect_ratio": None,
        "selected_border_distance_px": None,
        "selected_geometry": None,
        "selected_contour_point_count": None,
        "usable_border_margin_px": None,
        "usable_area_px": None,
        "grid_line_pixels_suppressed": 0,
        "minimum_candidate_score": MIN_CANDIDATE_SCORE,
        "calibration_confidence": (calibration or {}).get("confidence"),
        "measurement_unit": "mm",
        "pipeline": MEASUREMENT_PIPELINE,
        "calibration_profile_id": (calibration or {}).get("profile_id"),
        "calibration_source": None,
        "measurement_mm_per_pixel_x": None,
        "measurement_mm_per_pixel_y": None,
        "mat_detected": width is not None and height is not None,
        "rectified_image": width is not None and height is not None,
        "processing_ms": None,
        "failure_reason": None,
        "suggestions": [],
    }


def _failure_result(
    error: str,
    failure_reason: str,
    calibration: dict | None = None,
    processing_ms: float | None = None,
) -> Dict[str, Any]:
    diagnostics = _base_diagnostics(None, None, calibration)
    diagnostics.update({
        "failure_reason": failure_reason,
        "processing_ms": processing_ms,
        "suggestions": MEASUREMENT_SUGGESTIONS,
    })
    return _failure_payload(error, calibration, diagnostics)


def _failure_payload(error: str, calibration: dict | None, diagnostics: dict) -> Dict[str, Any]:
    failure_reason = diagnostics.get("failure_reason")
    status = {
        "calibration_not_ready": "calibration_missing",
        "image_file_missing": "invalid_frame",
        "opencv_read_failed": "invalid_frame",
        "opencv_missing": "measurement_failed",
        "no_object_found": "no_object",
        "object_touching_image_boundary": "no_object",
        "candidate_score_below_threshold": "low_confidence",
        "ambiguous_object_candidates": "low_confidence",
        "calibration_geometry_mismatch": "calibration_invalid",
    }.get(failure_reason, "measurement_failed")
    return {
        "ok": False,
        "status": status,
        "calibrated": bool((calibration or {}).get("ready")),
        "unit": "mm",
        "error": error,
        "calibration": calibration,
        "diagnostics": diagnostics,
    }


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
        "confidence": None, "known_width_mm": None, "known_height_mm": None,
        "error": error,
    }


def _calibration_for_rectified_artifact(path: Path) -> dict:
    metadata_path = rectified_metadata_path(path)
    if not metadata_path.is_file():
        return _unready_calibration(
            f"Calibration provenance metadata is missing: {metadata_path}"
        )
    try:
        import json
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        camera_status = get_camera_roles_status()
        active_camera = camera_status.get("active_camera") or {}
        profile, mismatches = validate_rectified_provenance(
            metadata, active_camera=active_camera
        )
    except Exception as exc:
        return _unready_calibration(f"Calibration provenance validation failed: {exc}")
    if profile is None or mismatches:
        result = _unready_calibration("; ".join(mismatches))
        result["validation_mismatches"] = mismatches
        return result
    calibration = profile.get("calibration") or {}
    scan_mat = profile.get("scan_mat") or {}
    return {
        "ready": True,
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "logical_camera_id": metadata.get("logical_camera_id"),
        "camera_role": metadata.get("camera_role"),
        "mm_per_pixel_x": calibration.get("mm_per_pixel_x"),
        "mm_per_pixel_y": calibration.get("mm_per_pixel_y"),
        "pixels_per_mm_x": calibration.get("pixels_per_mm_x"),
        "pixels_per_mm_y": calibration.get("pixels_per_mm_y"),
        "confidence": calibration.get("confidence"),
        "known_width_mm": scan_mat.get("known_width_mm"),
        "known_height_mm": scan_mat.get("known_height_mm"),
        "rectified_output_dimensions": scan_mat.get("rectified_output_dimensions"),
        "provenance_path": str(metadata_path),
        "provenance": metadata,
        "error": None,
    }


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _measurement_scale(calibration: dict, image_width: int, image_height: int) -> dict:
    known_width = calibration.get("known_width_mm")
    known_height = calibration.get("known_height_mm")
    if _positive_number(known_width) and _positive_number(known_height):
        return {
            "mm_per_pixel_x": float(known_width) / float(image_width),
            "mm_per_pixel_y": float(known_height) / float(image_height),
            "source": "rectified_mat_dimensions",
        }
    if image_width == RECTIFIED_WIDTH_PX and image_height == RECTIFIED_HEIGHT_PX:
        return {
            "mm_per_pixel_x": MAT_WIDTH_MM / float(RECTIFIED_WIDTH_PX),
            "mm_per_pixel_y": MAT_HEIGHT_MM / float(RECTIFIED_HEIGHT_PX),
            "source": "canonical_rectified_mat_geometry",
        }
    return {
        "mm_per_pixel_x": float(calibration["mm_per_pixel_x"]),
        "mm_per_pixel_y": float(calibration["mm_per_pixel_y"]),
        "source": "profile_pixel_scale_fallback",
    }


def _round_float(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _order_box_points(points: Any, np: Any) -> Any:
    pts = np.asarray(points, dtype=float)
    if pts.shape != (4, 2):
        raise ValueError("Rotated box must contain four 2D points.")
    center = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
    ordered = pts[np.argsort(angles)]
    top_left_index = int(np.argmin(ordered.sum(axis=1)))
    return np.roll(ordered, -top_left_index, axis=0)


def _simplified_contour_points(contour: Any, cv2: Any) -> list[dict[str, int]]:
    perimeter = cv2.arcLength(contour, True)
    simplified = cv2.approxPolyDP(contour, max(1.0, perimeter * 0.002), True)
    if len(simplified) > 256:
        step = math.ceil(len(simplified) / 256)
        simplified = simplified[::step]
    return [
        {"x": int(point[0][0]), "y": int(point[0][1])}
        for point in simplified
    ]


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000.0, 2)
