"""Repeatable validation of metric-mask measurements against caliper data."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import cv2

from .measurement import MeasurementResult, measure_metric_mask


TRIM_PERCENTAGES = tuple(float(value) for value in range(11))


@dataclass(frozen=True)
class ValidationSample:
    """One known object captured at one rotation."""

    object_name: str
    caliper_length_mm: float
    caliper_width_mm: float
    rotation_degrees: float
    mask_path: Path
    image_path: Path


def _positive_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc
    if number <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return number


def _resolve_path(value: Any, base_dir: Path, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty path.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def load_manifest(
    manifest_path: Path,
) -> tuple[dict[str, Any], list[ValidationSample]]:
    """Load validation settings and samples from a JSON manifest."""

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Validation manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Validation manifest must contain a JSON object.")

    pixels_per_mm = _positive_float(
        payload.get("pixels_per_mm"),
        "pixels_per_mm",
    )
    cleanup_kernel_size = payload.get("cleanup_kernel_size", 3)
    if (
        not isinstance(cleanup_kernel_size, int)
        or cleanup_kernel_size < 1
        or cleanup_kernel_size % 2 == 0
    ):
        raise ValueError(
            "cleanup_kernel_size must be an odd integer of at least one."
        )

    raw_samples = payload.get("samples")
    if not isinstance(raw_samples, list) or not raw_samples:
        raise ValueError("Validation manifest must contain at least one sample.")

    base_dir = manifest_path.resolve().parent
    samples = []
    for index, raw_sample in enumerate(raw_samples):
        prefix = f"samples[{index}]"
        if not isinstance(raw_sample, dict):
            raise ValueError(f"{prefix} must be a JSON object.")

        object_name = raw_sample.get("object_name")
        if not isinstance(object_name, str) or not object_name.strip():
            raise ValueError(f"{prefix}.object_name must be non-empty.")

        try:
            rotation_degrees = float(raw_sample.get("rotation_degrees"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{prefix}.rotation_degrees must be a number."
            ) from exc

        samples.append(
            ValidationSample(
                object_name=object_name.strip(),
                caliper_length_mm=_positive_float(
                    raw_sample.get("caliper_length_mm"),
                    f"{prefix}.caliper_length_mm",
                ),
                caliper_width_mm=_positive_float(
                    raw_sample.get("caliper_width_mm"),
                    f"{prefix}.caliper_width_mm",
                ),
                rotation_degrees=rotation_degrees,
                mask_path=_resolve_path(
                    raw_sample.get("mask_path"),
                    base_dir,
                    f"{prefix}.mask_path",
                ),
                image_path=_resolve_path(
                    raw_sample.get("image_path"),
                    base_dir,
                    f"{prefix}.image_path",
                ),
            )
        )

    settings = {
        "pixels_per_mm": pixels_per_mm,
        "cleanup_kernel_size": cleanup_kernel_size,
        "calibration_source": payload.get(
            "calibration_source",
            "manifest-supplied metric warp scale",
        ),
        "calibration_quality": payload.get(
            "calibration_quality",
            "experimental_unverified",
        ),
    }
    return settings, samples


def _measurement_errors(
    length_mm: float,
    width_mm: float,
    sample: ValidationSample,
) -> dict[str, float]:
    length_error_mm = abs(length_mm - sample.caliper_length_mm)
    width_error_mm = abs(width_mm - sample.caliper_width_mm)
    length_error_percent = (
        100.0 * length_error_mm / sample.caliper_length_mm
    )
    width_error_percent = 100.0 * width_error_mm / sample.caliper_width_mm
    return {
        "length_absolute_error_mm": length_error_mm,
        "width_absolute_error_mm": width_error_mm,
        "length_absolute_error_percent": length_error_percent,
        "width_absolute_error_percent": width_error_percent,
        "mean_absolute_error_mm": mean(
            [length_error_mm, width_error_mm]
        ),
        "mean_absolute_percentage_error": mean(
            [length_error_percent, width_error_percent]
        ),
    }


def _measurement_record(
    sample: ValidationSample,
    result: MeasurementResult,
) -> dict[str, Any]:
    return {
        "trim_percentile": result.trim_percentile,
        "outside_envelope": {
            "length_mm": result.outside_length_mm,
            "width_mm": result.outside_width_mm,
            "angle_degrees": result.outside_angle_degrees,
            "error_against_caliper": _measurement_errors(
                result.outside_length_mm,
                result.outside_width_mm,
                sample,
            ),
        },
        "robust_body": {
            "length_mm": result.robust_length_mm,
            "width_mm": result.robust_width_mm,
            "angle_degrees": result.robust_angle_degrees,
            "error_against_caliper": _measurement_errors(
                result.robust_length_mm,
                result.robust_width_mm,
                sample,
            ),
        },
    }


def evaluate_sample(
    sample: ValidationSample,
    *,
    pixels_per_mm: float,
    cleanup_kernel_size: int,
    trim_percentages: Iterable[float] = TRIM_PERCENTAGES,
) -> dict[str, Any]:
    """Evaluate every requested trim for one image/mask pair."""

    if not sample.mask_path.is_file():
        raise FileNotFoundError(f"Mask not found: {sample.mask_path}")
    if not sample.image_path.is_file():
        raise FileNotFoundError(f"Image not found: {sample.image_path}")

    mask = cv2.imread(str(sample.mask_path), cv2.IMREAD_GRAYSCALE)
    image = cv2.imread(str(sample.image_path), cv2.IMREAD_COLOR)
    if mask is None:
        raise ValueError(f"Could not decode mask: {sample.mask_path}")
    if image is None:
        raise ValueError(f"Could not decode image: {sample.image_path}")
    if mask.shape[:2] != image.shape[:2]:
        raise ValueError(
            f"Image and mask dimensions differ for {sample.object_name}: "
            f"{image.shape[:2]} versus {mask.shape[:2]}."
        )

    measurements = []
    for trim_percentile in trim_percentages:
        result = measure_metric_mask(
            mask,
            pixels_per_mm=pixels_per_mm,
            trim_percentile=float(trim_percentile),
            cleanup_kernel_size=cleanup_kernel_size,
        )
        measurements.append(_measurement_record(sample, result))

    best = min(
        measurements,
        key=lambda row: (
            row["robust_body"]["error_against_caliper"][
                "mean_absolute_percentage_error"
            ],
            row["trim_percentile"],
        ),
    )

    return {
        "object_name": sample.object_name,
        "caliper_length_mm": sample.caliper_length_mm,
        "caliper_width_mm": sample.caliper_width_mm,
        "rotation_degrees": sample.rotation_degrees,
        "mask_path": str(sample.mask_path),
        "image_path": str(sample.image_path),
        "best_robust_trim_percentile": best["trim_percentile"],
        "measurements": measurements,
    }


def _aggregate_by_trim(
    evaluated_samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    aggregates = []
    trim_percentages = [
        row["trim_percentile"]
        for row in evaluated_samples[0]["measurements"]
    ]

    for trim_percentile in trim_percentages:
        rows = [
            next(
                row
                for row in sample["measurements"]
                if row["trim_percentile"] == trim_percentile
            )
            for sample in evaluated_samples
        ]
        aggregate: dict[str, Any] = {
            "trim_percentile": trim_percentile,
            "sample_count": len(rows),
        }
        for measurement_name in ("outside_envelope", "robust_body"):
            errors = [
                row[measurement_name]["error_against_caliper"]
                for row in rows
            ]
            aggregate[
                f"{measurement_name}_mean_absolute_error_mm"
            ] = mean(error["mean_absolute_error_mm"] for error in errors)
            aggregate[
                f"{measurement_name}_mean_absolute_percentage_error"
            ] = mean(
                error["mean_absolute_percentage_error"] for error in errors
            )
        aggregates.append(aggregate)

    return aggregates


def run_validation(
    samples: list[ValidationSample],
    *,
    pixels_per_mm: float,
    cleanup_kernel_size: int = 3,
    calibration_source: str = "manifest-supplied metric warp scale",
    calibration_quality: str = "experimental_unverified",
) -> dict[str, Any]:
    """Run the fixed 0% through 10% validation sweep."""

    if not samples:
        raise ValueError("At least one validation sample is required.")

    evaluated_samples = [
        evaluate_sample(
            sample,
            pixels_per_mm=pixels_per_mm,
            cleanup_kernel_size=cleanup_kernel_size,
        )
        for sample in samples
    ]

    return {
        "schema_version": 1,
        "units": "millimeters",
        "calibration": {
            "pixels_per_mm": pixels_per_mm,
            "source": calibration_source,
            "quality": calibration_quality,
        },
        "trim_percentages": list(TRIM_PERCENTAGES),
        "measurement_semantics": {
            "outside_envelope": (
                "Maximum occupied mask envelope, including legitimate "
                "connectors, tabs, and other protrusions."
            ),
            "robust_body": (
                "Percentile-trimmed estimate of the object's main body."
            ),
            "caliper_reference": (
                "Confirmed physical dimensions supplied in the manifest; "
                "interpret envelope error according to what was calipered."
            ),
        },
        "production_default_changed": False,
        "samples": evaluated_samples,
        "aggregate_by_trim": _aggregate_by_trim(evaluated_samples),
    }


def _csv_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for sample in results["samples"]:
        for measurement in sample["measurements"]:
            row = {
                key: sample[key]
                for key in (
                    "object_name",
                    "caliper_length_mm",
                    "caliper_width_mm",
                    "rotation_degrees",
                    "mask_path",
                    "image_path",
                )
            }
            row["trim_percentile"] = measurement["trim_percentile"]
            for name in ("outside_envelope", "robust_body"):
                values = measurement[name]
                prefix = "outside" if name == "outside_envelope" else "robust"
                row[f"{prefix}_length_mm"] = values["length_mm"]
                row[f"{prefix}_width_mm"] = values["width_mm"]
                row[f"{prefix}_angle_degrees"] = values["angle_degrees"]
                for error_name, error_value in values[
                    "error_against_caliper"
                ].items():
                    row[f"{prefix}_{error_name}"] = error_value
            rows.append(row)
    return rows


def write_results(
    results: dict[str, Any],
    *,
    json_path: Path,
    csv_path: Path,
) -> None:
    """Write structured JSON and flat per-sweep CSV outputs."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    rows = _csv_rows(results)
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def console_summary(results: dict[str, Any]) -> str:
    """Return a concise best-per-sample and aggregate-per-trim summary."""

    lines = ["Best robust-body trim per sample:"]
    for sample in results["samples"]:
        best_trim = sample["best_robust_trim_percentile"]
        best = next(
            row
            for row in sample["measurements"]
            if row["trim_percentile"] == best_trim
        )
        error = best["robust_body"]["error_against_caliper"][
            "mean_absolute_percentage_error"
        ]
        lines.append(
            f"  {sample['object_name']} @ {sample['rotation_degrees']:g} deg: "
            f"{best_trim:g}% trim, {error:.2f}% mean absolute error"
        )

    lines.append("Aggregate mean absolute percentage error by trim:")
    lines.append("  trim | outside envelope | robust body")
    for aggregate in results["aggregate_by_trim"]:
        outside_error = aggregate[
            "outside_envelope_mean_absolute_percentage_error"
        ]
        robust_error = aggregate[
            "robust_body_mean_absolute_percentage_error"
        ]
        lines.append(
            f"  {aggregate['trim_percentile']:>4g}% | "
            f"{outside_error:>15.2f}% | "
            f"{robust_error:>11.2f}%"
        )
    lines.append("Production default trim was not selected or changed.")
    return "\n".join(lines)
