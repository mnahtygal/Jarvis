# skills/scan_mat_skill.py

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAT_WIDTH_INCHES = 24.0
MAT_HEIGHT_INCHES = 18.0
DETECTOR_EPSILON_RATIOS = [0.015, 0.02, 0.03, 0.04, 0.05]
MIN_MAT_AREA_RATIO = 0.08
MIN_RECTANGULARITY = 0.45
MIN_FALLBACK_RECTANGULARITY = 0.72
MIN_ASPECT_RATIO = 0.7
MAX_ASPECT_RATIO = 2.6
TARGET_ASPECT_RATIO = MAT_WIDTH_INCHES / MAT_HEIGHT_INCHES
DIAGNOSTIC_REJECTION_LIMIT = 8
SCAN_MAT_SUGGESTIONS = [
    "Move camera closer so the mat fills more of the frame.",
    "Improve lighting and reduce glare.",
    "Make sure all four mat corners are visible.",
    "Use a higher-contrast mat boundary.",
    "Keep the camera fixed and pointed at the mat.",
]


def _cv2_missing() -> Dict[str, Any]:
    return {
        "ok": False,
        "mat_detected": False,
        "error": "OpenCV is not installed. Run: pip install opencv-python-headless numpy",
    }


def _order_points(points: List[List[float]]):
    import numpy as np

    pts = np.array(points, dtype="float32")
    rect = np.zeros((4, 2), dtype="float32")
    sums = pts.sum(axis=1)
    rect[0] = pts[np.argmin(sums)]
    rect[2] = pts[np.argmax(sums)]
    diffs = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diffs)]
    rect[3] = pts[np.argmax(diffs)]
    return rect


def _round_optional(value: Any, digits: int = 4):
    if value is None:
        return None
    return round(float(value), digits)


def _contour_rectangularity(cv2, contour) -> float:
    area = float(cv2.contourArea(contour))
    rect = cv2.minAreaRect(contour)
    width, height = rect[1]
    box_area = float(width * height)
    if box_area <= 0:
        return 0.0
    return max(0.0, min(1.0, area / box_area))


def _quad_aspect_ratio(rect) -> float:
    import numpy as np

    top = float(np.linalg.norm(rect[1] - rect[0]))
    right = float(np.linalg.norm(rect[2] - rect[1]))
    bottom = float(np.linalg.norm(rect[2] - rect[3]))
    left = float(np.linalg.norm(rect[3] - rect[0]))
    width = (top + bottom) / 2.0
    height = (left + right) / 2.0
    if height <= 0:
        return 0.0
    ratio = width / height
    return ratio if ratio >= 1.0 else 1.0 / ratio


def _points_inside_image(rect, width: int, height: int, margin: float = 0.0) -> bool:
    for x, y in rect:
        if x < -margin or y < -margin:
            return False
        if x > width - 1 + margin or y > height - 1 + margin:
            return False
    return True


def _points_clipped(rect, width: int, height: int, margin: float = 2.0) -> bool:
    for x, y in rect:
        if x <= margin or y <= margin:
            return True
        if x >= width - 1 - margin or y >= height - 1 - margin:
            return True
    return False


def _aspect_plausible(aspect_ratio: float) -> bool:
    return MIN_ASPECT_RATIO <= aspect_ratio <= MAX_ASPECT_RATIO


def _candidate_score(area_ratio: float, rectangularity: float, aspect_ratio: float) -> float:
    aspect_error = abs(aspect_ratio - TARGET_ASPECT_RATIO) / TARGET_ASPECT_RATIO
    return round((area_ratio * 2.0) + rectangularity - min(aspect_error, 1.0), 6)


def _compact_rejections(rejections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rejections, key=lambda item: item.get("area_ratio", 0.0), reverse=True)[
        :DIAGNOSTIC_REJECTION_LIMIT
    ]


def _find_largest_quad(image) -> Tuple[Optional[Any], Dict[str, Any]]:
    import cv2

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 130)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    image_area = float(width * height)
    contour_areas = [float(cv2.contourArea(contour)) for contour in contours]
    largest_contour_area = max(contour_areas) if contour_areas else 0.0
    edge_pixels = int(cv2.countNonZero(edges))
    diagnostics = {
        "image_width": int(width),
        "image_height": int(height),
        "mode": "scan_mat_detector_v2",
        "legacy_mode": "largest_quad_contour_v1",
        "epsilon_values": DETECTOR_EPSILON_RATIOS,
        "edges_found": edge_pixels > 0,
        "edge_pixels": edge_pixels,
        "contour_count": len(contours),
        "large_contour_count": 0,
        "candidate_quad_count": 0,
        "largest_contour_area": round(largest_contour_area, 2),
        "largest_contour_area_ratio": round(largest_contour_area / image_area, 6) if image_area else 0.0,
        "selected_quad_area": None,
        "selected_quad_area_ratio": None,
        "selected_method": None,
        "selected_score": None,
        "selected_rectangularity": None,
        "selected_aspect_ratio": None,
        "fallback_attempted": False,
        "fallback_accepted": False,
        "rejected_candidates": [],
        "corners_detected": False,
        "rectified_available": False,
        "failure_reason": "unknown",
        "suggestions": SCAN_MAT_SUGGESTIONS,
    }
    candidates = []
    rejected_candidates = []
    fallback_candidates = []

    for contour in contours:
        area = float(cv2.contourArea(contour))
        area_ratio = area / image_area if image_area else 0.0
        if area < image_area * MIN_MAT_AREA_RATIO:
            continue
        perimeter = cv2.arcLength(contour, True)
        x, y, w, h = cv2.boundingRect(contour)
        rectangularity = _contour_rectangularity(cv2, contour)
        min_area_rect = cv2.minAreaRect(contour)
        min_rect_width, min_rect_height = min_area_rect[1]
        min_side = min(float(min_rect_width), float(min_rect_height))
        max_side = max(float(min_rect_width), float(min_rect_height))
        min_rect_aspect_ratio = max_side / min_side if min_side > 0 else 0.0
        approx_point_counts: Dict[str, int] = {}
        contour_rejections = []
        accepted_direct = False

        for epsilon_ratio in DETECTOR_EPSILON_RATIOS:
            approx = cv2.approxPolyDP(contour, epsilon_ratio * perimeter, True)
            approx_count = len(approx)
            approx_point_counts[str(epsilon_ratio)] = approx_count
            if approx_count != 4:
                continue

            if not cv2.isContourConvex(approx):
                contour_rejections.append("not_convex")
                continue

            rect = _order_points(approx.reshape(4, 2).astype(float).tolist())
            quad_area = float(cv2.contourArea(rect.astype("float32")))
            quad_area_ratio = quad_area / image_area if image_area else 0.0
            aspect_ratio = _quad_aspect_ratio(rect)
            if quad_area_ratio < MIN_MAT_AREA_RATIO:
                contour_rejections.append("quad_area_too_small")
                continue
            if not _points_inside_image(rect, width, height, margin=1.0):
                contour_rejections.append("points_outside_image")
                continue
            if not _aspect_plausible(aspect_ratio):
                contour_rejections.append("aspect_ratio_not_plausible")
                continue
            if rectangularity < MIN_RECTANGULARITY:
                contour_rejections.append("rectangularity_too_low")
                continue

            candidates.append({
                "method": "approx_poly",
                "area": area,
                "area_ratio": area_ratio,
                "quad_area": quad_area,
                "quad_area_ratio": quad_area_ratio,
                "bbox": [int(x), int(y), int(w), int(h)],
                "points": rect.astype(float).tolist(),
                "epsilon_ratio": epsilon_ratio,
                "approx_point_count": approx_count,
                "approx_point_counts": approx_point_counts.copy(),
                "rectangularity": rectangularity,
                "aspect_ratio": aspect_ratio,
                "score": _candidate_score(quad_area_ratio, rectangularity, aspect_ratio),
            })
            accepted_direct = True
            break

        fallback_box = cv2.boxPoints(min_area_rect)
        fallback_rect = _order_points(fallback_box.astype(float).tolist())
        fallback_clipped = _points_clipped(fallback_rect, width, height)
        fallback_candidate = {
            "method": "min_area_rect_fallback",
            "area": area,
            "area_ratio": area_ratio,
            "bbox": [int(x), int(y), int(w), int(h)],
            "points": fallback_rect.astype(float).tolist(),
            "rectangularity": rectangularity,
            "aspect_ratio": min_rect_aspect_ratio,
            "clipped": fallback_clipped,
            "score": _candidate_score(area_ratio, rectangularity, min_rect_aspect_ratio),
        }
        fallback_candidates.append(fallback_candidate)

        if not accepted_direct:
            primary_reason = (
                "no_four_point_approximation"
                if 4 not in approx_point_counts.values()
                else (contour_rejections[-1] if contour_rejections else "candidate_rejected")
            )
            rejected_candidates.append({
                "reason": primary_reason,
                "area": round(area, 2),
                "area_ratio": round(area_ratio, 6),
                "bbox": [int(x), int(y), int(w), int(h)],
                "rectangularity": _round_optional(rectangularity),
                "aspect_ratio": _round_optional(min_rect_aspect_ratio),
                "approx_point_counts": approx_point_counts,
                "fallback_clipped": fallback_clipped,
            })

    diagnostics["large_contour_count"] = len(fallback_candidates)
    diagnostics["candidate_quad_count"] = len(candidates)
    diagnostics["rejected_candidates"] = _compact_rejections(rejected_candidates)

    if not candidates and fallback_candidates:
        diagnostics["fallback_attempted"] = True
        fallback_candidates.sort(key=lambda item: item["score"], reverse=True)
        best_fallback = fallback_candidates[0]
        fallback_reasons = []
        if best_fallback["area_ratio"] < MIN_MAT_AREA_RATIO:
            fallback_reasons.append("area_too_small")
        if best_fallback["rectangularity"] < MIN_FALLBACK_RECTANGULARITY:
            fallback_reasons.append("rectangularity_too_low")
        if not _aspect_plausible(best_fallback["aspect_ratio"]):
            fallback_reasons.append("aspect_ratio_not_plausible")
        if best_fallback["clipped"]:
            fallback_reasons.append("clipped_against_image_boundary")

        diagnostics["best_fallback"] = {
            "area_ratio": round(best_fallback["area_ratio"], 6),
            "rectangularity": _round_optional(best_fallback["rectangularity"]),
            "aspect_ratio": _round_optional(best_fallback["aspect_ratio"]),
            "score": best_fallback["score"],
            "rejection_reasons": fallback_reasons,
        }

        if not fallback_reasons:
            candidates.append({
                **best_fallback,
                "quad_area": best_fallback["area"],
                "quad_area_ratio": best_fallback["area_ratio"],
            })
            diagnostics["fallback_accepted"] = True

    diagnostics["candidate_quad_count"] = len(candidates)

    if not candidates:
        diagnostics["failure_reason"] = (
            "no_contours_found" if not contours else "no_quadrilateral_candidates"
        )
        return None, {
            "contours_checked": len(contours),
            "candidate_count": 0,
            "rejected_candidates": diagnostics["rejected_candidates"],
            "reason": "No large four-corner contour found.",
            "diagnostics": diagnostics,
        }

    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = candidates[0]
    diagnostics.update({
        "selected_quad_area": round(float(best["quad_area"]), 2),
        "selected_quad_area_ratio": round(float(best["quad_area_ratio"]), 6),
        "selected_method": best["method"],
        "selected_score": best["score"],
        "selected_rectangularity": _round_optional(best["rectangularity"]),
        "selected_aspect_ratio": _round_optional(best["aspect_ratio"]),
        "corners_detected": True,
        "failure_reason": None,
    })
    return _order_points(best["points"]), {
        "contours_checked": len(contours),
        "candidate_count": len(candidates),
        "best": best,
        "diagnostics": diagnostics,
    }


def _grid_estimate(image) -> Dict[str, Any]:
    import cv2
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=90,
        minLineLength=max(40, min(image.shape[:2]) // 8),
        maxLineGap=8,
    )

    if lines is None:
        return {"ok": False, "line_count": 0, "detail": "No grid lines detected."}

    horizontal = []
    vertical = []
    for line in lines[:, 0, :]:
        x1, y1, x2, y2 = [int(v) for v in line]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx > dy * 4:
            horizontal.append((y1 + y2) / 2.0)
        elif dy > dx * 4:
            vertical.append((x1 + x2) / 2.0)

    def cluster(values: List[float], tolerance: float = 6.0) -> List[float]:
        if not values:
            return []
        values = sorted(values)
        groups = [[values[0]]]
        for value in values[1:]:
            if abs(value - groups[-1][-1]) <= tolerance:
                groups[-1].append(value)
            else:
                groups.append([value])
        return [sum(group) / len(group) for group in groups]

    h = cluster(horizontal)
    v = cluster(vertical)

    return {
        "ok": bool(h and v),
        "line_count": int(len(lines)),
        "horizontal_line_count": len(h),
        "vertical_line_count": len(v),
        "detail": "Grid lines detected." if h and v else "Not enough grid lines detected.",
    }


def analyze_scan_mat(image_path: Path, output_dir: Path | None = None) -> Dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except Exception:
        return _cv2_missing()

    if not image_path.exists():
        return {
            "ok": False,
            "mat_detected": False,
            "error": "Image file does not exist.",
            "diagnostics": _failure_diagnostics("image_file_missing"),
        }

    image = cv2.imread(str(image_path))
    if image is None:
        return {
            "ok": False,
            "mat_detected": False,
            "error": "OpenCV could not read image.",
            "diagnostics": _failure_diagnostics("opencv_read_failed"),
        }

    height, width = image.shape[:2]
    rect, debug = _find_largest_quad(image)
    diagnostics = debug.get("diagnostics", _failure_diagnostics("unknown"))
    output_dir = output_dir or image_path.parent / "mat_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    annotated = image.copy()
    annotated_path = output_dir / f"{image_path.stem}_mat_annotated.jpg"

    if rect is None:
        for rejected in diagnostics.get("rejected_candidates", [])[:4]:
            bbox = rejected.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            x, y, w, h = [int(value) for value in bbox]
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 165, 255), 2)
            label = rejected.get("reason", "rejected")
            cv2.putText(
                annotated,
                str(label)[:28],
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 165, 255),
                2,
            )
        cv2.putText(annotated, "Mat not detected", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.imwrite(str(annotated_path), annotated)
        return {
            "ok": False,
            "mat_detected": False,
            "image_name": image_path.name,
            "image_size": {"width": width, "height": height},
            "debug": debug,
            "diagnostics": diagnostics,
            "annotated_path": str(annotated_path),
            "guidance": [
                "Point the camera down at the mat.",
                "Make the mat fill most of the frame.",
                "Keep the mat border visible and reduce glare.",
            ],
        }

    rect_int = rect.astype(int)
    cv2.polylines(annotated, [rect_int], True, (0, 255, 0), 4)
    for idx, (x, y) in enumerate(rect_int):
        cv2.circle(annotated, (int(x), int(y)), 8, (0, 255, 255), -1)
        cv2.putText(annotated, str(idx + 1), (int(x) + 8, int(y) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    method_label = diagnostics.get("selected_method") or "unknown"
    score_label = diagnostics.get("selected_score")
    quality_label = f"Scan Mat: {method_label}"
    if score_label is not None:
        quality_label = f"{quality_label} score={score_label}"
    cv2.putText(annotated, quality_label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
    cv2.imwrite(str(annotated_path), annotated)

    px_per_inch = 60
    warped_width = int(MAT_WIDTH_INCHES * px_per_inch)
    warped_height = int(MAT_HEIGHT_INCHES * px_per_inch)
    dst = np.array([[0, 0], [warped_width - 1, 0], [warped_width - 1, warped_height - 1], [0, warped_height - 1]], dtype="float32")
    transform = cv2.getPerspectiveTransform(rect.astype("float32"), dst)
    warped = cv2.warpPerspective(image, transform, (warped_width, warped_height))
    rectified_path = output_dir / f"{image_path.stem}_mat_rectified.jpg"
    cv2.imwrite(str(rectified_path), warped)
    diagnostics = {
        **diagnostics,
        "rectified_available": rectified_path.is_file(),
        "failure_reason": None if rectified_path.is_file() else "rectification_failed",
    }

    mat_pixel_width = float(np.linalg.norm(rect[1] - rect[0]))
    mat_pixel_height = float(np.linalg.norm(rect[3] - rect[0]))

    return {
        "ok": True,
        "mat_detected": True,
        "image_name": image_path.name,
        "image_size": {"width": width, "height": height},
        "mat": {
            "width_inches": MAT_WIDTH_INCHES,
            "height_inches": MAT_HEIGHT_INCHES,
            "corners": rect.astype(float).round(1).tolist(),
            "approx_pixels_per_inch_x": round(mat_pixel_width / MAT_WIDTH_INCHES, 2),
            "approx_pixels_per_inch_y": round(mat_pixel_height / MAT_HEIGHT_INCHES, 2),
        },
        "grid": _grid_estimate(warped),
        "debug": debug,
        "diagnostics": diagnostics,
        "annotated_path": str(annotated_path),
        "rectified_path": str(rectified_path),
    }


def _failure_diagnostics(failure_reason: str) -> Dict[str, Any]:
    return {
        "image_width": None,
        "image_height": None,
        "mode": "largest_quad_contour_v1",
        "edges_found": False,
        "edge_pixels": None,
        "contour_count": 0,
        "candidate_quad_count": 0,
        "largest_contour_area": None,
        "largest_contour_area_ratio": None,
        "selected_quad_area": None,
        "selected_quad_area_ratio": None,
        "corners_detected": False,
        "rectified_available": False,
        "failure_reason": failure_reason,
        "suggestions": SCAN_MAT_SUGGESTIONS,
    }
