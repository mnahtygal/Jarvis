"""Measure a preserved metric-space Grounded SAM mask."""

import argparse
import json
from pathlib import Path
from typing import Any

import cv2

from .measurement import (
    MeasurementResult,
    create_measurement_diagnostic,
    measure_metric_mask,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure an already perspective-corrected Grounded SAM mask "
            "using an explicit pixels-per-millimeter calibration."
        )
    )
    parser.add_argument("image", type=Path, help="Rectified metric-space image.")
    parser.add_argument("mask", type=Path, help="Rectified binary mask.")
    parser.add_argument(
        "--pixels-per-mm",
        type=float,
        required=True,
        help="Metric warp scale in pixels per millimeter.",
    )
    parser.add_argument(
        "--trim-percentile",
        type=float,
        default=1.0,
        help="Percent trimmed from each PCA-axis tail (default: 1.0).",
    )
    parser.add_argument(
        "--cleanup-kernel-size",
        type=int,
        default=3,
        help="Odd morphological opening kernel size (default: 3).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Destination for measurement metadata.",
    )
    parser.add_argument(
        "--diagnostic-image",
        type=Path,
        required=True,
        help="Destination for the annotated diagnostic image.",
    )
    parser.add_argument(
        "--calibration-source",
        required=True,
        help="Human-readable source of the pixel scale.",
    )
    parser.add_argument(
        "--calibration-quality",
        default="experimental_unverified",
        help="Calibration quality indicator (default: experimental_unverified).",
    )
    parser.add_argument(
        "--raw-image-reference",
        type=Path,
        help="Original camera image associated with the rectified artifact.",
    )
    parser.add_argument(
        "--reference-length-mm",
        type=float,
        help="Optional physical-reference long side for error reporting.",
    )
    parser.add_argument(
        "--reference-width-mm",
        type=float,
        help="Optional physical-reference short side for error reporting.",
    )
    parser.add_argument(
        "--sweep-trim",
        type=float,
        nargs="*",
        default=[],
        metavar="PERCENT",
        help="Additional trim percentiles to evaluate against the same mask.",
    )
    return parser.parse_args()


def _read_image(path: Path, flags: int, label: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")

    image = cv2.imread(str(path), flags)
    if image is None:
        raise ValueError(f"Could not decode {label.lower()}: {path}")

    return image


def _reference_comparison(
    result: MeasurementResult,
    *,
    reference_length_mm: float | None,
    reference_width_mm: float | None,
) -> dict[str, Any] | None:
    if reference_length_mm is None and reference_width_mm is None:
        return None
    if reference_length_mm is None or reference_width_mm is None:
        raise ValueError(
            "Both reference-length-mm and reference-width-mm are required "
            "for physical-reference error reporting."
        )
    if reference_length_mm <= 0 or reference_width_mm <= 0:
        raise ValueError("Physical-reference dimensions must be positive.")

    def comparison(length_mm: float, width_mm: float) -> dict[str, float]:
        length_error = length_mm - reference_length_mm
        width_error = width_mm - reference_width_mm
        return {
            "length_error_mm": length_error,
            "length_error_percent": 100.0 * length_error / reference_length_mm,
            "width_error_mm": width_error,
            "width_error_percent": 100.0 * width_error / reference_width_mm,
        }

    return {
        "source": "user-supplied physical reference",
        "length_mm": reference_length_mm,
        "width_mm": reference_width_mm,
        "outside_error": comparison(
            result.outside_length_mm,
            result.outside_width_mm,
        ),
        "robust_error": comparison(
            result.robust_length_mm,
            result.robust_width_mm,
        ),
    }


def _sweep_entry(result: MeasurementResult) -> dict[str, float]:
    return {
        "trim_percentile": result.trim_percentile,
        "robust_length_mm": result.robust_length_mm,
        "robust_width_mm": result.robust_width_mm,
        "robust_angle_degrees": result.robust_angle_degrees,
    }


def main() -> int:
    args = parse_args()

    image = _read_image(args.image, cv2.IMREAD_COLOR, "Image")
    mask = _read_image(args.mask, cv2.IMREAD_GRAYSCALE, "Mask")

    result = measure_metric_mask(
        mask,
        pixels_per_mm=args.pixels_per_mm,
        trim_percentile=args.trim_percentile,
        cleanup_kernel_size=args.cleanup_kernel_size,
    )
    diagnostic = create_measurement_diagnostic(image, mask, result)

    args.diagnostic_image.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.diagnostic_image), diagnostic):
        raise OSError(
            f"Could not write diagnostic image: {args.diagnostic_image}"
        )

    sweep = []
    for trim_percentile in args.sweep_trim:
        sweep_result = measure_metric_mask(
            mask,
            pixels_per_mm=args.pixels_per_mm,
            trim_percentile=trim_percentile,
            cleanup_kernel_size=args.cleanup_kernel_size,
        )
        sweep.append(_sweep_entry(sweep_result))

    payload = {
        "status": "ok",
        "method": "metric_mask_outside_and_trimmed_pca_v1",
        "units": "millimeters",
        "inputs": {
            "raw_image_reference": (
                str(args.raw_image_reference)
                if args.raw_image_reference is not None
                else None
            ),
            "rectified_image_reference": str(args.image),
            "rectified_mask_reference": str(args.mask),
        },
        "calibration": {
            "source": args.calibration_source,
            "pixels_per_mm": args.pixels_per_mm,
            "quality": args.calibration_quality,
        },
        "parameters": {
            "trim_percentile": args.trim_percentile,
            "cleanup_kernel_size": args.cleanup_kernel_size,
        },
        "measurement": result.to_dict(),
        "physical_reference": _reference_comparison(
            result,
            reference_length_mm=args.reference_length_mm,
            reference_width_mm=args.reference_width_mm,
        ),
        "trim_percentile_sweep": sweep,
        "artifacts": {
            "measurement_json": str(args.output_json),
            "diagnostic_image": str(args.diagnostic_image),
        },
        "precision_warning": (
            "Experimental result; do not treat as precision metrology until "
            "the calibration and segmentation are physically validated."
        ),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    print(
        f"Outside: {result.outside_length_mm:.3f} x "
        f"{result.outside_width_mm:.3f} mm"
    )
    print(
        f"Robust ({result.trim_percentile:g}% trim): "
        f"{result.robust_length_mm:.3f} x "
        f"{result.robust_width_mm:.3f} mm"
    )
    print(f"Measurement JSON: {args.output_json}")
    print(f"Diagnostic image: {args.diagnostic_image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
