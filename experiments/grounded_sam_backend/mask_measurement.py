"""Adapted component cleanup and calibrated metric-mask measurement."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot
from typing import Any


@dataclass(frozen=True)
class CleanMask:
    raw: Any
    cleaned: Any
    raw_area: int
    cleaned_area: int
    component_decisions: tuple[dict[str, Any], ...]


def validate_and_clean_mask(mask: Any, *, expected_shape: tuple[int, int]) -> CleanMask:
    import cv2
    import numpy as np

    array = np.asarray(mask)
    if array.ndim > 2:
        array = np.squeeze(array)
    if array.ndim != 2 or tuple(array.shape) != expected_shape:
        raise ValueError(f"Mask shape {array.shape} does not match image {expected_shape}.")
    raw = np.where(array, 255, 0).astype(np.uint8)
    raw_area = int(cv2.countNonZero(raw))
    if raw_area == 0:
        raise ValueError("Segmentation mask contains no foreground pixels.")
    if raw_area / float(raw.size) > 0.50:
        raise ValueError("Segmentation mask covers an implausibly large image area.")
    prepared = cv2.morphologyEx(raw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(prepared, connectivity=8)
    if count <= 1:
        raise ValueError("Segmentation mask is empty after cleanup.")
    ordered = sorted(range(1, count), key=lambda label: int(stats[label, cv2.CC_STAT_AREA]), reverse=True)
    primary = ordered[0]
    primary_area = int(stats[primary, cv2.CC_STAT_AREA])
    primary_bbox = _bbox(stats, primary, cv2)
    threshold = max(16, ceil(primary_area * 0.002))
    kept = {primary}
    decisions = []
    for label in ordered:
        area = int(stats[label, cv2.CC_STAT_AREA])
        bbox = _bbox(stats, label, cv2)
        gap = 0.0 if label == primary else _bbox_gap(primary_bbox, bbox)
        if label == primary:
            retain, reason = True, "primary_component"
        elif area < threshold:
            retain, reason = False, "area_below_secondary_threshold"
        elif gap > 24.0:
            retain, reason = False, "too_far_from_primary"
        else:
            retain, reason = True, "nearby_legitimate_component"
            kept.add(label)
        decisions.append({
            "label": label, "area_pixels": area,
            "bbox": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
            "gap_from_primary_pixels": gap, "kept": retain, "reason": reason,
        })
    cleaned = np.where(np.isin(labels, tuple(kept)), 255, 0).astype(np.uint8)
    cleaned_area = int(cv2.countNonZero(cleaned))
    if cleaned_area == 0:
        raise ValueError("Segmentation mask has no retained foreground.")
    return CleanMask(raw, cleaned, raw_area, cleaned_area, tuple(decisions))


def measure_cleaned_mask(cleanup: CleanMask, *, pixels_per_mm: float) -> dict[str, Any]:
    import cv2
    import numpy as np

    if pixels_per_mm <= 0:
        raise ValueError("pixels_per_mm must be positive.")
    points = cv2.findNonZero(cleanup.cleaned)
    if points is None or len(points) < 5:
        raise ValueError("At least five mask points are required for measurement.")
    outside = cv2.minAreaRect(points)
    outside_box = cv2.boxPoints(outside)
    outside_long, outside_short, outside_angle = _rectangle_dimensions(outside, pixels_per_mm)
    contours, _ = cv2.findContours(cleanup.cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    boundary = np.vstack(contours).reshape(-1, 2).astype(np.float64)
    robust_long, robust_short, robust_angle, robust_box = _robust_rectangle(
        boundary, points.reshape(-1, 2).astype(np.float64), pixels_per_mm
    )
    return {
        "unit": "mm",
        "method": "metric_mask_outside_and_trimmed_pca_v1",
        "maximum_occupied_envelope": {
            "long_side_mm": outside_long, "short_side_mm": outside_short,
            "angle_degrees": outside_angle, "box_px": outside_box.tolist(),
        },
        "robust_body": {
            "long_side_mm": robust_long, "short_side_mm": robust_short,
            "angle_degrees": robust_angle, "box_px": robust_box.tolist(),
            "trim_percentile": 1.0,
        },
        "area_mm2": cleanup.cleaned_area / (pixels_per_mm * pixels_per_mm),
    }


def _bbox(stats: Any, label: int, cv2: Any) -> tuple[int, int, int, int]:
    return tuple(int(stats[label, index]) for index in (
        cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT
    ))


def _bbox_gap(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return hypot(max(ax - (bx + bw), bx - (ax + aw), 0), max(ay - (by + bh), by - (ay + ah), 0))


def _rectangle_dimensions(rectangle: Any, scale: float) -> tuple[float, float, float]:
    _, (first, second), angle = rectangle
    if first >= second:
        long_side, short_side, long_angle = first, second, angle
    else:
        long_side, short_side, long_angle = second, first, angle + 90.0
    while long_angle >= 90.0:
        long_angle -= 180.0
    while long_angle < -90.0:
        long_angle += 180.0
    return long_side / scale, short_side / scale, float(long_angle)


def _robust_rectangle(boundary: Any, foreground: Any, scale: float) -> tuple[float, float, float, Any]:
    import numpy as np

    center = boundary.mean(axis=0)
    covariance = np.cov(boundary - center, rowvar=False)
    values, vectors = np.linalg.eigh(covariance)
    axes = vectors[:, np.argsort(values)[::-1]]
    if axes[0, 0] < 0:
        axes[:, 0] *= -1
    if np.linalg.det(axes) < 0:
        axes[:, 1] *= -1
    projected = (foreground - center) @ axes
    lower = np.percentile(projected, 1.0, axis=0)
    upper = np.percentile(projected, 99.0, axis=0)
    spans = upper - lower
    if spans[0] >= spans[1]:
        long_px, short_px, long_axis = spans[0], spans[1], axes[:, 0]
    else:
        long_px, short_px, long_axis = spans[1], spans[0], axes[:, 1]
    projected_box = np.array([
        [lower[0], lower[1]], [upper[0], lower[1]],
        [upper[0], upper[1]], [lower[0], upper[1]],
    ])
    image_box = projected_box @ axes.T + center
    angle = float(np.degrees(np.arctan2(long_axis[1], long_axis[0])))
    while angle >= 90.0:
        angle -= 180.0
    while angle < -90.0:
        angle += 180.0
    return float(long_px / scale), float(short_px / scale), angle, image_box
