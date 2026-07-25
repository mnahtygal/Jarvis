"""Metric measurements from a perspective-corrected segmentation mask."""

from dataclasses import asdict, dataclass

import cv2
import numpy as np


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


def _normalized_rectangle(
    contour: np.ndarray,
    pixels_per_mm: float,
) -> tuple[float, float, float, np.ndarray]:
    rectangle = cv2.minAreaRect(contour)
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
    contour: np.ndarray,
    *,
    pixels_per_mm: float,
    trim_percentile: float,
) -> tuple[float, float, float, np.ndarray]:
    """Measure the central mask distribution in its principal-axis frame.

    Percentile trimming prevents a small number of connector, tab, shadow,
    or mask-edge pixels from expanding the body measurement.
    """

    if not 0.0 <= trim_percentile < 25.0:
        raise ValueError(
            "trim_percentile must be greater than or equal to 0 "
            "and less than 25."
        )

    points = contour.reshape(-1, 2).astype(np.float64)

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

    projected = centered @ axes

    lower = trim_percentile
    upper = 100.0 - trim_percentile

    long_min, long_max = np.percentile(
        projected[:, 0],
        [lower, upper],
    )
    short_min, short_max = np.percentile(
        projected[:, 1],
        [lower, upper],
    )

    length_px = float(long_max - long_min)
    width_px = float(short_max - short_min)

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

    if cleanup_kernel_size < 1 or cleanup_kernel_size % 2 == 0:
        raise ValueError(
            "cleanup_kernel_size must be an odd integer of at least one."
        )

    binary = _validate_binary_mask(mask)

    if cleanup_kernel_size > 1:
        kernel = np.ones(
            (cleanup_kernel_size, cleanup_kernel_size),
            dtype=np.uint8,
        )
        binary = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            kernel,
            iterations=1,
        )

    contour = _largest_external_contour(binary)

    (
        outside_length_mm,
        outside_width_mm,
        outside_angle_degrees,
        outside_box,
    ) = _normalized_rectangle(contour, pixels_per_mm)

    (
        robust_length_mm,
        robust_width_mm,
        robust_angle_degrees,
        robust_box,
    ) = _robust_pca_rectangle(
        contour,
        pixels_per_mm=pixels_per_mm,
        trim_percentile=trim_percentile,
    )

    contour_area_mm2 = (
        float(cv2.contourArea(contour))
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
        foreground_pixels=cv2.countNonZero(binary),
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

    binary = _validate_binary_mask(mask)

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
