"""Metric measurements from a perspective-corrected segmentation mask."""

from dataclasses import asdict, dataclass
from math import ceil, hypot

import cv2
import numpy as np


@dataclass(frozen=True)
class MaskCleanupResult:
    """Cleaned foreground plus auditable connected-component decisions."""

    raw_binary: np.ndarray
    cleaned_binary: np.ndarray
    raw_foreground_pixels: int
    cleaned_foreground_pixels: int
    component_decisions: tuple[dict, ...]


@dataclass(frozen=True)
class MeasurementResult:
    """Outside-envelope and robust-body measurements."""

    pixels_per_mm: float

    outside_length_mm: float
    outside_width_mm: float
    outside_angle_degrees: float

    robust_length_mm: float
    robust_width_mm: float
    robust_angle_degrees: float

    contour_area_mm2: float
    foreground_pixels: int
    raw_foreground_pixels: int
    cleaned_foreground_pixels: int
    component_decisions: tuple[dict, ...]
    trim_percentile: float

    outside_box: np.ndarray
    robust_box: np.ndarray

    def to_dict(self) -> dict:
        result = asdict(self)
        result["outside_box"] = self.outside_box.tolist()
        result["robust_box"] = self.robust_box.tolist()
        return result


def _validate_binary_mask(mask: np.ndarray) -> np.ndarray:
    if mask is None:
        raise ValueError("Mask cannot be None.")

    if mask.ndim != 2:
        raise ValueError(
            f"Expected a single-channel mask; received shape {mask.shape}."
        )

    binary = np.where(mask > 127, 255, 0).astype(np.uint8)

    if cv2.countNonZero(binary) == 0:
        raise ValueError("Mask contains no foreground pixels.")

    return binary


def _largest_external_contour(binary: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(
        binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_NONE,
    )

    if not contours:
        raise ValueError("No external contour was found in the mask.")

    contour = max(contours, key=cv2.contourArea)

    if cv2.contourArea(contour) <= 0:
        raise ValueError("Largest contour has zero area.")

    return contour


def _bbox_gap(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> float:
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    horizontal = max(
        first_x - (second_x + second_width),
        second_x - (first_x + first_width),
        0,
    )
    vertical = max(
        first_y - (second_y + second_height),
        second_y - (first_y + first_height),
        0,
    )
    return hypot(horizontal, vertical)


def clean_metric_mask(
    mask: np.ndarray,
    *,
    cleanup_kernel_size: int = 3,
    minimum_component_area_px: int = 16,
    minimum_secondary_area_ratio: float = 0.002,
    maximum_component_gap_px: float = 24.0,
) -> MaskCleanupResult:
    """Reject speckles while retaining nearby legitimate disconnected parts."""

    if cleanup_kernel_size < 1 or cleanup_kernel_size % 2 == 0:
        raise ValueError(
            "cleanup_kernel_size must be an odd integer of at least one."
        )
    if minimum_component_area_px < 1:
        raise ValueError("minimum_component_area_px must be at least one.")
    if not 0.0 <= minimum_secondary_area_ratio < 1.0:
        raise ValueError(
            "minimum_secondary_area_ratio must be in the range [0, 1)."
        )
    if maximum_component_gap_px < 0:
        raise ValueError("maximum_component_gap_px cannot be negative.")

    raw_binary = _validate_binary_mask(mask)
    prepared = raw_binary.copy()
    if cleanup_kernel_size > 1:
        kernel = np.ones(
            (cleanup_kernel_size, cleanup_kernel_size),
            dtype=np.uint8,
        )
        prepared = cv2.morphologyEx(
            prepared,
            cv2.MORPH_OPEN,
            kernel,
            iterations=1,
        )

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        prepared,
        connectivity=8,
    )
    if count <= 1:
        raise ValueError("Mask contains no foreground after cleanup.")

    component_labels = sorted(
        range(1, count),
        key=lambda label: int(stats[label, cv2.CC_STAT_AREA]),
        reverse=True,
    )
    primary_label = component_labels[0]
    primary_area = int(stats[primary_label, cv2.CC_STAT_AREA])
    primary_bbox = tuple(
        int(stats[primary_label, index])
        for index in (
            cv2.CC_STAT_LEFT,
            cv2.CC_STAT_TOP,
            cv2.CC_STAT_WIDTH,
            cv2.CC_STAT_HEIGHT,
        )
    )
    secondary_area_threshold = max(
        minimum_component_area_px,
        ceil(primary_area * minimum_secondary_area_ratio),
    )

    kept_labels = {primary_label}
    decisions = []
    for label in component_labels:
        area = int(stats[label, cv2.CC_STAT_AREA])
        bbox = tuple(
            int(stats[label, index])
            for index in (
                cv2.CC_STAT_LEFT,
                cv2.CC_STAT_TOP,
                cv2.CC_STAT_WIDTH,
                cv2.CC_STAT_HEIGHT,
            )
        )
        gap = 0.0 if label == primary_label else _bbox_gap(primary_bbox, bbox)
        if label == primary_label:
            kept = True
            reason = "primary_component"
        elif area < secondary_area_threshold:
            kept = False
            reason = "area_below_secondary_threshold"
        elif gap > maximum_component_gap_px:
            kept = False
            reason = "too_far_from_primary"
        else:
            kept = True
            reason = "nearby_legitimate_component"
            kept_labels.add(label)
        decisions.append(
            {
                "label": label,
                "area_pixels": area,
                "bbox": {
                    "x": bbox[0],
                    "y": bbox[1],
                    "width": bbox[2],
                    "height": bbox[3],
                },
                "gap_from_primary_pixels": float(gap),
                "kept": kept,
                "reason": reason,
            }
        )

    cleaned = np.where(
        np.isin(labels, tuple(kept_labels)),
        255,
        0,
    ).astype(np.uint8)
    cleaned_count = cv2.countNonZero(cleaned)
    if cleaned_count == 0:
        raise ValueError("Mask contains no retained foreground components.")

    return MaskCleanupResult(
        raw_binary=raw_binary,
        cleaned_binary=cleaned,
        raw_foreground_pixels=cv2.countNonZero(raw_binary),
        cleaned_foreground_pixels=cleaned_count,
        component_decisions=tuple(decisions),
    )


def _normalized_rectangle(
    points: np.ndarray,
    pixels_per_mm: float,
) -> tuple[float, float, float, np.ndarray]:
    rectangle = cv2.minAreaRect(points)
    center, dimensions, angle = rectangle
    side_a_px, side_b_px = dimensions

    if side_a_px >= side_b_px:
        length_px = side_a_px
        width_px = side_b_px
        long_axis_angle = angle
    else:
        length_px = side_b_px
        width_px = side_a_px
        long_axis_angle = angle + 90.0

    while long_axis_angle >= 90.0:
        long_axis_angle -= 180.0

    while long_axis_angle < -90.0:
        long_axis_angle += 180.0

    box = cv2.boxPoints((center, dimensions, angle))

    return (
        length_px / pixels_per_mm,
        width_px / pixels_per_mm,
        long_axis_angle,
        box,
    )


def _robust_pca_rectangle(
    boundary_points: np.ndarray,
    *,
    foreground_points: np.ndarray,
    pixels_per_mm: float,
    trim_percentile: float,
) -> tuple[float, float, float, np.ndarray]:
    """Measure median body cross-sections in the principal-axis frame.

    The PCA orientation comes from all retained external boundaries. Length
    is estimated from long-axis spans across short-axis slices, and width
    from short-axis spans across long-axis slices. Median-like span
    percentiles prevent connectors, tabs, mounting holes, and isolated edge
    defects from defining the main body.
    """

    if not 0.0 <= trim_percentile < 25.0:
        raise ValueError(
            "trim_percentile must be greater than or equal to 0 "
            "and less than 25."
        )

    points = boundary_points.reshape(-1, 2).astype(np.float64)

    if len(points) < 5:
        raise ValueError(
            "At least five contour points are required for robust measurement."
        )

    center = points.mean(axis=0)
    centered = points - center

    covariance = np.cov(centered, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)

    order = np.argsort(eigenvalues)[::-1]
    axes = eigenvectors[:, order]

    # Give the long axis a stable left-to-right direction.
    if axes[0, 0] < 0:
        axes[:, 0] *= -1

    # Preserve a right-handed coordinate system.
    if np.linalg.det(axes) < 0:
        axes[:, 1] *= -1

    projected = (
        foreground_points.reshape(-1, 2).astype(np.float64) - center
    ) @ axes
    span_percentile = 50.0 - trim_percentile

    def cross_sections(
        *,
        grouping_axis: int,
        span_axis: int,
    ) -> tuple[list[float], list[float]]:
        keys = np.rint(projected[:, grouping_axis]).astype(np.int64)
        values = projected[:, span_axis]
        order = np.argsort(keys, kind="stable")
        sorted_keys = keys[order]
        sorted_values = values[order]
        _, starts, counts = np.unique(
            sorted_keys,
            return_index=True,
            return_counts=True,
        )
        minimums = np.minimum.reduceat(sorted_values, starts)
        maximums = np.maximum.reduceat(sorted_values, starts)
        usable = counts >= 2
        spans = (maximums[usable] - minimums[usable]).tolist()
        midpoints = (
            (minimums[usable] + maximums[usable]) / 2.0
        ).tolist()
        if not spans:
            raise ValueError("No usable mask cross-sections were found.")
        return spans, midpoints

    long_spans, long_midpoints = cross_sections(
        grouping_axis=1,
        span_axis=0,
    )
    short_spans, short_midpoints = cross_sections(
        grouping_axis=0,
        span_axis=1,
    )
    length_px = float(np.percentile(long_spans, span_percentile))
    width_px = float(np.percentile(short_spans, span_percentile))
    long_center = float(np.median(long_midpoints))
    short_center = float(np.median(short_midpoints))
    long_min = long_center - length_px / 2.0
    long_max = long_center + length_px / 2.0
    short_min = short_center - width_px / 2.0
    short_max = short_center + width_px / 2.0

    projected_corners = np.array(
        [
            [long_min, short_min],
            [long_max, short_min],
            [long_max, short_max],
            [long_min, short_max],
        ],
        dtype=np.float64,
    )

    image_corners = projected_corners @ axes.T + center

    angle_degrees = float(
        np.degrees(np.arctan2(axes[1, 0], axes[0, 0]))
    )

    return (
        length_px / pixels_per_mm,
        width_px / pixels_per_mm,
        angle_degrees,
        image_corners,
    )


def measure_metric_mask(
    mask: np.ndarray,
    *,
    pixels_per_mm: float,
    trim_percentile: float = 1.0,
    cleanup_kernel_size: int = 3,
) -> MeasurementResult:
    """Measure a mask that has already been warped into metric space."""

    if pixels_per_mm <= 0:
        raise ValueError("pixels_per_mm must be greater than zero.")

    cleanup = clean_metric_mask(
        mask,
        cleanup_kernel_size=cleanup_kernel_size,
    )
    points = cv2.findNonZero(cleanup.cleaned_binary)
    if points is None or len(points) < 5:
        raise ValueError(
            "At least five cleaned foreground pixels are required."
        )
    contours, _ = cv2.findContours(
        cleanup.cleaned_binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_NONE,
    )
    robust_points = np.vstack(contours)
    if len(robust_points) < 5:
        raise ValueError(
            "At least five cleaned boundary points are required."
        )

    (
        outside_length_mm,
        outside_width_mm,
        outside_angle_degrees,
        outside_box,
    ) = _normalized_rectangle(points, pixels_per_mm)

    (
        robust_length_mm,
        robust_width_mm,
        robust_angle_degrees,
        robust_box,
    ) = _robust_pca_rectangle(
        robust_points,
        foreground_points=points,
        pixels_per_mm=pixels_per_mm,
        trim_percentile=trim_percentile,
    )

    contour_area_mm2 = (
        cleanup.cleaned_foreground_pixels
        / (pixels_per_mm * pixels_per_mm)
    )

    return MeasurementResult(
        pixels_per_mm=pixels_per_mm,
        outside_length_mm=outside_length_mm,
        outside_width_mm=outside_width_mm,
        outside_angle_degrees=outside_angle_degrees,
        robust_length_mm=robust_length_mm,
        robust_width_mm=robust_width_mm,
        robust_angle_degrees=robust_angle_degrees,
        contour_area_mm2=contour_area_mm2,
        foreground_pixels=cleanup.cleaned_foreground_pixels,
        raw_foreground_pixels=cleanup.raw_foreground_pixels,
        cleaned_foreground_pixels=cleanup.cleaned_foreground_pixels,
        component_decisions=cleanup.component_decisions,
        trim_percentile=trim_percentile,
        outside_box=outside_box,
        robust_box=robust_box,
    )


def create_measurement_diagnostic(
    image: np.ndarray,
    mask: np.ndarray,
    result: MeasurementResult,
) -> np.ndarray:
    """Draw the outside and robust measurement rectangles."""

    if image is None:
        raise ValueError("Diagnostic image cannot be None.")

    cleanup = clean_metric_mask(mask)
    binary = cleanup.cleaned_binary

    if image.shape[:2] != binary.shape[:2]:
        raise ValueError(
            "Diagnostic image and mask dimensions do not match."
        )

    diagnostic = image.copy()
    overlay = diagnostic.copy()
    overlay[binary > 0] = (0, 0, 255)

    diagnostic = cv2.addWeighted(
        diagnostic,
        0.68,
        overlay,
        0.32,
        0,
    )

    raw_contours, _ = cv2.findContours(
        cleanup.raw_binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    cleaned_contours, _ = cv2.findContours(
        cleanup.cleaned_binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    cv2.drawContours(diagnostic, raw_contours, -1, (0, 0, 255), 1)
    cv2.drawContours(diagnostic, cleaned_contours, -1, (255, 0, 255), 2)

    outside_box = np.int32(np.round(result.outside_box))
    robust_box = np.int32(np.round(result.robust_box))

    # Green: maximum outside envelope.
    cv2.drawContours(
        diagnostic,
        [outside_box],
        -1,
        (0, 255, 0),
        3,
    )

    # Cyan: percentile-trimmed robust body.
    cv2.drawContours(
        diagnostic,
        [robust_box],
        -1,
        (255, 255, 0),
        3,
    )

    cv2.putText(
        diagnostic,
        (
            f"Outside: {result.outside_length_mm:.2f} x "
            f"{result.outside_width_mm:.2f} mm"
        ),
        (18, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.70,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        diagnostic,
        (
            f"Robust: {result.robust_length_mm:.2f} x "
            f"{result.robust_width_mm:.2f} mm"
        ),
        (18, 66),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.70,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    return diagnostic
