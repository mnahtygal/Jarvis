from pathlib import Path

import cv2
import numpy as np
import pytest

from experiments.grounded_sam.validation import (
    TRIM_PERCENTAGES,
    ValidationSample,
    run_validation,
    write_results,
)


def _write_sample(
    tmp_path: Path,
    *,
    object_name: str,
    mask: np.ndarray,
    length_mm: float,
    width_mm: float,
    rotation_degrees: float,
) -> ValidationSample:
    mask_path = tmp_path / f"{object_name}_mask.png"
    image_path = tmp_path / f"{object_name}_image.png"
    image = np.full((*mask.shape, 3), 80, dtype=np.uint8)
    assert cv2.imwrite(str(mask_path), mask)
    assert cv2.imwrite(str(image_path), image)
    return ValidationSample(
        object_name=object_name,
        caliper_length_mm=length_mm,
        caliper_width_mm=width_mm,
        rotation_degrees=rotation_degrees,
        mask_path=mask_path,
        image_path=image_path,
    )


def _rotated_rectangle_mask(
    *,
    angle_degrees: float,
    length_px: float = 600.0,
    width_px: float = 300.0,
) -> np.ndarray:
    mask = np.zeros((900, 1100), dtype=np.uint8)
    box = cv2.boxPoints(
        ((550.0, 450.0), (length_px, width_px), angle_degrees)
    )
    cv2.fillConvexPoly(mask, np.int32(np.round(box)), 255)
    return mask


@pytest.mark.parametrize("rotation_degrees", [0.0, 23.0, 67.0])
def test_validation_sweeps_rotated_rectangles(
    tmp_path: Path,
    rotation_degrees: float,
):
    sample = _write_sample(
        tmp_path,
        object_name=f"rectangle_{rotation_degrees:g}",
        mask=_rotated_rectangle_mask(angle_degrees=rotation_degrees),
        length_mm=60.0,
        width_mm=30.0,
        rotation_degrees=rotation_degrees,
    )

    results = run_validation(
        [sample],
        pixels_per_mm=10.0,
        cleanup_kernel_size=1,
    )

    rows = results["samples"][0]["measurements"]
    assert [row["trim_percentile"] for row in rows] == list(
        TRIM_PERCENTAGES
    )
    assert rows[0]["outside_envelope"]["length_mm"] == pytest.approx(
        60.0,
        abs=0.2,
    )
    assert rows[0]["outside_envelope"]["width_mm"] == pytest.approx(
        30.0,
        abs=0.2,
    )
    assert results["samples"][0]["rotation_degrees"] == rotation_degrees
    assert (
        results["samples"][0]["best_robust_trim_percentile"]
        in TRIM_PERCENTAGES
    )
    assert results["production_default_changed"] is False


def test_legitimate_protrusion_preserves_outside_envelope(
    tmp_path: Path,
):
    mask = np.zeros((700, 1000), dtype=np.uint8)
    cv2.rectangle(mask, (150, 200), (750, 500), 255, -1)
    cv2.rectangle(mask, (750, 330), (820, 370), 255, -1)
    sample = _write_sample(
        tmp_path,
        object_name="body_with_connector",
        mask=mask,
        length_mm=60.0,
        width_mm=30.0,
        rotation_degrees=0.0,
    )

    results = run_validation(
        [sample],
        pixels_per_mm=10.0,
        cleanup_kernel_size=1,
    )

    sample_result = results["samples"][0]
    zero_trim = sample_result["measurements"][0]
    best_trim = sample_result["best_robust_trim_percentile"]
    best = sample_result["measurements"][int(best_trim)]

    assert zero_trim["outside_envelope"]["length_mm"] == pytest.approx(
        67.0,
        abs=0.2,
    )
    assert best_trim in TRIM_PERCENTAGES
    assert best["robust_body"]["length_mm"] == pytest.approx(60.0, abs=1.0)
    assert (
        best["outside_envelope"]["length_mm"]
        > best["robust_body"]["length_mm"]
    )


def test_writes_machine_readable_json_and_csv(tmp_path: Path):
    sample = _write_sample(
        tmp_path,
        object_name="plain_rectangle",
        mask=_rotated_rectangle_mask(angle_degrees=0.0),
        length_mm=60.0,
        width_mm=30.0,
        rotation_degrees=0.0,
    )
    results = run_validation(
        [sample],
        pixels_per_mm=10.0,
        cleanup_kernel_size=1,
    )
    json_path = tmp_path / "results.json"
    csv_path = tmp_path / "results.csv"

    write_results(results, json_path=json_path, csv_path=csv_path)

    assert '"outside_envelope"' in json_path.read_text(encoding="utf-8")
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "outside_length_absolute_error_mm" in csv_text
    assert "robust_length_absolute_error_percent" in csv_text
    assert len(csv_text.splitlines()) == 12
