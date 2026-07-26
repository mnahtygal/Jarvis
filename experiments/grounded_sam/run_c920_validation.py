"""Run Grounding DINO, SAM 2, and metric measurement on C920 fixtures."""

import argparse
import json
import re
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image

from .config import DetectorGuardrails
from .detector import GroundingDinoDetector
from .inference import detect_with_prompts
from .measurement import (
    MeasurementResult,
    clean_metric_mask,
    create_measurement_diagnostic,
    measure_metric_mask,
)
from .provenance import load_and_validate_c920_provenance
from .segmenter import Sam2Segmenter


DETECTOR_MODEL_ID = "IDEA-Research/grounding-dino-base"
SEGMENTER_MODEL_ID = "facebook/sam2-hiera-base-plus"
DEFAULT_PROMPT = "a SIM868 cellular GPS development board"
DEFAULT_TRIM_PERCENTILE = 1.0
CALIPER_LENGTH_MM = 65.24
CALIPER_WIDTH_MM = 32.56
OPENCV_MEAN_MM = (65.7934, 30.5031)
OPENCV_RANGE_MM = (0.8125, 5.4543)


def _object_id(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise argparse.ArgumentTypeError(
            "object ID must contain only lowercase letters, digits, "
            "underscores, and hyphens"
        )
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preserved C920 validation captures through Grounding "
            "DINO, SAM 2, and fixed metric-space measurement."
        )
    )
    parser.add_argument(
        "fixture_dir",
        type=Path,
        help="Directory containing rectified C920 JPEGs and provenance sidecars.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--object-id",
        type=_object_id,
        default="c920_sim868",
        help="Stable identifier used in the aggregate results filename.",
    )
    parser.add_argument(
        "--object-name",
        default="SIM868 cellular GPS development board",
    )
    parser.add_argument(
        "--caliper-length-mm",
        type=float,
        default=CALIPER_LENGTH_MM,
    )
    parser.add_argument(
        "--caliper-width-mm",
        type=float,
        default=CALIPER_WIDTH_MM,
    )
    parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        help=(
            "DINO prompt. Repeat only for a small documented comparison set; "
            f"default: {DEFAULT_PROMPT!r}."
        ),
    )
    parser.add_argument(
        "--trim-percentile",
        type=float,
        default=DEFAULT_TRIM_PERCENTILE,
        help="Robust-body tail trim; does not change the production default.",
    )
    return parser.parse_args()


def _error(measured: float, reference: float) -> dict[str, float]:
    signed = measured - reference
    return {
        "signed_mm": signed,
        "absolute_mm": abs(signed),
        "signed_percent": 100.0 * signed / reference,
        "absolute_percent": 100.0 * abs(signed) / reference,
    }


def _draw_full_diagnostic(
    image: np.ndarray,
    raw_mask: np.ndarray,
    result: MeasurementResult,
    detector_box: tuple[float, float, float, float],
    detector_score: float,
    sam_score: float,
) -> np.ndarray:
    diagnostic = create_measurement_diagnostic(image, raw_mask, result)
    x1, y1, x2, y2 = (int(round(value)) for value in detector_box)
    cv2.rectangle(diagnostic, (x1, y1), (x2, y2), (0, 165, 255), 2)
    labels = [
        f"DINO {detector_score:.3f} | SAM2 {sam_score:.3f}",
        (
            f"Envelope {result.outside_length_mm:.2f} x "
            f"{result.outside_width_mm:.2f} mm"
        ),
        (
            f"Robust {result.robust_length_mm:.2f} x "
            f"{result.robust_width_mm:.2f} mm | "
            f"trim {result.trim_percentile:g}%"
        ),
    ]
    for index, label in enumerate(labels):
        y = 98 + index * 30
        cv2.putText(
            diagnostic,
            label,
            (18, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.67,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            diagnostic,
            label,
            (18, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.67,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
    return diagnostic


def _aggregate(
    rows: list[dict[str, Any]],
    key: str,
    *,
    reference_length_mm: float,
    reference_width_mm: float,
) -> dict[str, Any]:
    length_values = [row[key]["length_mm"] for row in rows]
    width_values = [row[key]["width_mm"] for row in rows]

    def summarize(values: list[float], reference: float) -> dict[str, Any]:
        average = mean(values)
        return {
            "individual_mm": values,
            "mean_mm": average,
            "minimum_mm": min(values),
            "maximum_mm": max(values),
            "range_mm": max(values) - min(values),
            "sample_standard_deviation_mm": stdev(values),
            "error_against_caliper": _error(average, reference),
        }

    return {
        "length": summarize(length_values, reference_length_mm),
        "width": summarize(width_values, reference_width_mm),
    }


def _artifact_pairs(fixture_dir: Path) -> list[tuple[Path, Path]]:
    images = sorted(fixture_dir.glob("*_mat_rectified.jpg"))
    pairs = [
        (image, image.with_suffix(".metadata.json"))
        for image in images
    ]
    if len(pairs) != 3:
        raise ValueError(
            f"Expected exactly three rectified C920 fixtures; found {len(pairs)}."
        )
    return pairs


def main() -> int:
    args = parse_args()
    prompts = tuple(args.prompts or [DEFAULT_PROMPT])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    detector = GroundingDinoDetector(
        model_id=DETECTOR_MODEL_ID,
        device=device,
        guardrails=DetectorGuardrails(),
        box_threshold=0.20,
        text_threshold=0.15,
    )
    segmenter = Sam2Segmenter(
        model_id=SEGMENTER_MODEL_ID,
        device=device,
    )
    rows = []

    for image_path, metadata_path in _artifact_pairs(args.fixture_dir):
        bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError(f"Could not decode fixture: {image_path}")
        height, width = bgr.shape[:2]
        provenance, calibration = load_and_validate_c920_provenance(
            metadata_path,
            rectified_width=width,
            rectified_height=height,
        )
        pil_image = Image.open(image_path).convert("RGB")
        detection = detect_with_prompts(
            detector=detector,
            image=pil_image,
            prompts=prompts,
        )
        if detection.selected is None:
            raise RuntimeError(
                f"No accepted Grounding DINO candidate for {image_path.name}."
            )
        segmentation = segmenter.segment(
            image=pil_image,
            candidate=detection.selected,
        )
        raw_mask = (
            segmentation.mask.detach().cpu().numpy().astype(np.uint8) * 255
        )
        cleanup = clean_metric_mask(raw_mask)
        measurement_started = perf_counter()
        measurement = measure_metric_mask(
            raw_mask,
            pixels_per_mm=calibration.pixels_per_mm_x,
            trim_percentile=args.trim_percentile,
        )
        measurement_seconds = perf_counter() - measurement_started

        stem = image_path.stem
        raw_mask_path = args.output_dir / f"{stem}_sam2_raw_mask.png"
        cleaned_mask_path = args.output_dir / f"{stem}_sam2_cleaned_mask.png"
        overlay_path = args.output_dir / f"{stem}_grounded_sam_diagnostic.png"
        diagnostics_path = args.output_dir / f"{stem}_grounded_sam.json"
        cv2.imwrite(str(raw_mask_path), raw_mask)
        cv2.imwrite(str(cleaned_mask_path), cleanup.cleaned_binary)
        diagnostic = _draw_full_diagnostic(
            bgr,
            raw_mask,
            measurement,
            detection.selected.box,
            detection.selected.score,
            segmentation.score,
        )
        cv2.imwrite(str(overlay_path), diagnostic)

        envelope = {
            "length_mm": measurement.outside_length_mm,
            "width_mm": measurement.outside_width_mm,
            "angle_degrees": measurement.outside_angle_degrees,
            "box": measurement.outside_box.tolist(),
            "errors_against_caliper": {
                "length": _error(
                    measurement.outside_length_mm,
                    args.caliper_length_mm,
                ),
                "width": _error(
                    measurement.outside_width_mm,
                    args.caliper_width_mm,
                ),
            },
        }
        robust = {
            "length_mm": measurement.robust_length_mm,
            "width_mm": measurement.robust_width_mm,
            "angle_degrees": measurement.robust_angle_degrees,
            "trim_percentile": measurement.trim_percentile,
            "box": measurement.robust_box.tolist(),
            "errors_against_caliper": {
                "length": _error(
                    measurement.robust_length_mm,
                    args.caliper_length_mm,
                ),
                "width": _error(
                    measurement.robust_width_mm,
                    args.caliper_width_mm,
                ),
            },
        }
        row = {
            "sample": stem,
            "source_image_path": str(
                args.fixture_dir
                / image_path.name.replace("_mat_rectified", "")
            ),
            "rectified_image_path": str(image_path),
            "provenance_sidecar_path": str(metadata_path),
            "prompt_set": list(prompts),
            "prompt_selection_rule": (
                "highest-confidence accepted DINO candidate; caliper "
                "dimensions are not used for prompt or box selection"
            ),
            "selected_prompt": detection.selected.prompt,
            "dino_confidence": detection.selected.score,
            "dino_box": detection.selected.box,
            "sam2_confidence": segmentation.score,
            "raw_mask_area_pixels": cleanup.raw_foreground_pixels,
            "cleaned_mask_area_pixels": cleanup.cleaned_foreground_pixels,
            "connected_component_decisions": list(
                cleanup.component_decisions
            ),
            "principal_axis_angle_degrees": (
                measurement.robust_angle_degrees
            ),
            "maximum_occupied_envelope": envelope,
            "robust_board_body": robust,
            "timings_seconds": {
                "dino": detection.inference_seconds,
                "sam2": segmentation.inference_seconds,
                "measurement": measurement_seconds,
            },
            "calibration": calibration.to_dict(),
            "capture_provenance": {
                "stable_camera_identity": provenance.get(
                    "stable_camera_identity"
                ),
                "requested_mode": provenance.get("requested_mode"),
                "negotiated_mode": provenance.get("negotiated_mode"),
                "source_image_dimensions": provenance.get(
                    "source_image_dimensions"
                ),
                "rectified_output_dimensions": provenance.get(
                    "rectified_output_dimensions"
                ),
                "corners": provenance.get("corners"),
                "homography": provenance.get("homography"),
            },
            "artifacts": {
                "raw_mask": str(raw_mask_path),
                "cleaned_mask": str(cleaned_mask_path),
                "diagnostic_overlay": str(overlay_path),
                "sample_json": str(diagnostics_path),
            },
        }
        diagnostics_path.write_text(
            json.dumps(row, indent=2),
            encoding="utf-8",
        )
        rows.append(row)

    envelope_summary = _aggregate(
        rows,
        "maximum_occupied_envelope",
        reference_length_mm=args.caliper_length_mm,
        reference_width_mm=args.caliper_width_mm,
    )
    robust_summary = _aggregate(
        rows,
        "robust_board_body",
        reference_length_mm=args.caliper_length_mm,
        reference_width_mm=args.caliper_width_mm,
    )
    payload = {
        "schema_version": 1,
        "status": "completed",
        "object": {
            "id": args.object_id,
            "name": args.object_name,
        },
        "device": str(device),
        "models": {
            "detector": DETECTOR_MODEL_ID,
            "segmenter": SEGMENTER_MODEL_ID,
        },
        "prompt_set": list(prompts),
        "caliper_ground_truth_mm": {
            "length": args.caliper_length_mm,
            "width": args.caliper_width_mm,
        },
        "robust_trim_percentile": args.trim_percentile,
        "production_default_changed": False,
        "samples": rows,
        "aggregate": {
            "maximum_occupied_envelope": envelope_summary,
            "robust_board_body": robust_summary,
        },
    }
    if args.object_id == "c920_sim868":
        payload["opencv_baseline"] = {
            "mean_mm": {
                "length": OPENCV_MEAN_MM[0],
                "width": OPENCV_MEAN_MM[1],
            },
            "range_mm": {
                "length": OPENCV_RANGE_MM[0],
                "width": OPENCV_RANGE_MM[1],
            },
        }
        payload["comparison"] = {
            "envelope_width_range_improvement_mm": (
                OPENCV_RANGE_MM[1]
                - envelope_summary["width"]["range_mm"]
            ),
            "robust_width_range_improvement_mm": (
                OPENCV_RANGE_MM[1]
                - robust_summary["width"]["range_mm"]
            ),
        }
    aggregate_path = args.output_dir / f"{args.object_id}_grounded_sam_results.json"
    aggregate_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload["aggregate"], indent=2))
    print(f"Results: {aggregate_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
