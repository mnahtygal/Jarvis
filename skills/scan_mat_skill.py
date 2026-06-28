# skills/scan_mat_skill.py

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAT_WIDTH_INCHES = 24.0
MAT_HEIGHT_INCHES = 18.0


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
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.08:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            candidates.append({
                "area": area,
                "area_ratio": area / image_area,
                "bbox": [int(x), int(y), int(w), int(h)],
                "points": approx.reshape(4, 2).astype(float).tolist(),
            })

    if not candidates:
        return None, {
            "contours_checked": len(contours),
            "candidate_count": 0,
            "reason": "No large four-corner contour found.",
        }

    candidates.sort(key=lambda item: item["area"], reverse=True)
    best = candidates[0]
    return _order_points(best["points"]), {
        "contours_checked": len(contours),
        "candidate_count": len(candidates),
        "best": best,
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
        return {"ok": False, "mat_detected": False, "error": "Image file does not exist."}

    image = cv2.imread(str(image_path))
    if image is None:
        return {"ok": False, "mat_detected": False, "error": "OpenCV could not read image."}

    height, width = image.shape[:2]
    rect, debug = _find_largest_quad(image)
    output_dir = output_dir or image_path.parent / "mat_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    annotated = image.copy()
    annotated_path = output_dir / f"{image_path.stem}_mat_annotated.jpg"

    if rect is None:
        cv2.putText(annotated, "Mat not detected", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.imwrite(str(annotated_path), annotated)
        return {
            "ok": False,
            "mat_detected": False,
            "image_name": image_path.name,
            "image_size": {"width": width, "height": height},
            "debug": debug,
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
    cv2.imwrite(str(annotated_path), annotated)

    px_per_inch = 60
    warped_width = int(MAT_WIDTH_INCHES * px_per_inch)
    warped_height = int(MAT_HEIGHT_INCHES * px_per_inch)
    dst = np.array([[0, 0], [warped_width - 1, 0], [warped_width - 1, warped_height - 1], [0, warped_height - 1]], dtype="float32")
    transform = cv2.getPerspectiveTransform(rect.astype("float32"), dst)
    warped = cv2.warpPerspective(image, transform, (warped_width, warped_height))
    rectified_path = output_dir / f"{image_path.stem}_mat_rectified.jpg"
    cv2.imwrite(str(rectified_path), warped)

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
        "annotated_path": str(annotated_path),
        "rectified_path": str(rectified_path),
    }
