import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from experiments.grounded_sam.measurement import (
    clean_metric_mask,
    measure_metric_mask,
)


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "c920_sim868_20260726"
)


def test_measures_axis_aligned_rectangle():
    mask = np.zeros((500, 900), dtype=np.uint8)
    cv2.rectangle(mask, (100, 100), (751, 401), 255, -1)

    result = measure_metric_mask(
        mask,
        pixels_per_mm=10.0,
        trim_percentile=0.0,
        cleanup_kernel_size=1,
    )

    assert result.outside_length_mm == pytest.approx(65.1, abs=0.15)
    assert result.outside_width_mm == pytest.approx(30.1, abs=0.15)
    assert result.robust_length_mm == pytest.approx(65.1, abs=0.15)
    assert result.robust_width_mm == pytest.approx(30.1, abs=0.15)


def test_rejects_empty_mask():
    mask = np.zeros((200, 200), dtype=np.uint8)

    with pytest.raises(ValueError, match="no foreground"):
        measure_metric_mask(mask, pixels_per_mm=10.0)


def test_rejects_invalid_pixels_per_mm():
    mask = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(mask, (20, 20), (100, 100), 255, -1)

    with pytest.raises(ValueError, match="greater than zero"):
        measure_metric_mask(mask, pixels_per_mm=0.0)


def test_percentile_measurement_reduces_thin_protrusion_effect():
    mask = np.zeros((500, 900), dtype=np.uint8)

    cv2.rectangle(mask, (120, 100), (770, 400), 255, -1)

    # Narrow protrusion extending beyond the main body.
    cv2.rectangle(mask, (770, 230), (820, 270), 255, -1)

    result = measure_metric_mask(
        mask,
        pixels_per_mm=10.0,
        trim_percentile=7.0,
        cleanup_kernel_size=1,
    )

    assert result.robust_length_mm < result.outside_length_mm
    assert result.robust_length_mm == pytest.approx(65.0, abs=1.0)
    assert result.robust_width_mm == pytest.approx(30.0, abs=1.0)


def test_rejects_isolated_speckles_but_keeps_primary_body():
    mask = np.zeros((500, 900), dtype=np.uint8)
    cv2.rectangle(mask, (150, 150), (750, 400), 255, -1)
    mask[20, 20] = 255
    cv2.circle(mask, (850, 450), 2, 255, -1)

    cleanup = clean_metric_mask(mask, cleanup_kernel_size=1)
    result = measure_metric_mask(
        mask,
        pixels_per_mm=10.0,
        trim_percentile=0.0,
        cleanup_kernel_size=1,
    )

    rejected = [
        decision
        for decision in cleanup.component_decisions
        if not decision["kept"]
    ]
    assert len(rejected) == 2
    assert {row["reason"] for row in rejected} == {
        "area_below_secondary_threshold"
    }
    assert result.outside_length_mm == pytest.approx(60.0, abs=0.2)
    assert result.outside_width_mm == pytest.approx(25.0, abs=0.2)


def test_keeps_disconnected_legitimate_protrusion_near_body():
    mask = np.zeros((500, 900), dtype=np.uint8)
    cv2.rectangle(mask, (150, 150), (700, 400), 255, -1)
    cv2.rectangle(mask, (710, 230), (760, 320), 255, -1)

    cleanup = clean_metric_mask(
        mask,
        cleanup_kernel_size=1,
        maximum_component_gap_px=12.0,
    )
    result = measure_metric_mask(
        mask,
        pixels_per_mm=10.0,
        trim_percentile=5.0,
        cleanup_kernel_size=1,
    )

    kept = [
        decision
        for decision in cleanup.component_decisions
        if decision["kept"]
    ]
    assert len(kept) == 2
    assert kept[1]["reason"] == "nearby_legitimate_component"
    assert result.outside_length_mm == pytest.approx(61.0, abs=0.2)
    assert result.robust_length_mm < result.outside_length_mm


def test_principal_axis_measurement_handles_rotated_mask():
    mask = np.zeros((900, 1100), dtype=np.uint8)
    box = cv2.boxPoints(((550, 450), (650, 320), 31))
    cv2.fillConvexPoly(mask, np.int32(np.round(box)), 255)

    result = measure_metric_mask(
        mask,
        pixels_per_mm=10.0,
        trim_percentile=0.0,
        cleanup_kernel_size=1,
    )

    assert result.outside_length_mm == pytest.approx(65.0, abs=0.25)
    assert result.outside_width_mm == pytest.approx(32.0, abs=0.25)
    assert abs(result.robust_angle_degrees) == pytest.approx(31.0, abs=0.3)


def test_missing_dark_edge_section_keeps_both_body_sections():
    mask = np.zeros((500, 900), dtype=np.uint8)
    cv2.rectangle(mask, (150, 150), (445, 400), 255, -1)
    cv2.rectangle(mask, (454, 150), (750, 400), 255, -1)

    cleanup = clean_metric_mask(
        mask,
        cleanup_kernel_size=1,
        maximum_component_gap_px=12.0,
    )
    result = measure_metric_mask(
        mask,
        pixels_per_mm=10.0,
        trim_percentile=1.0,
        cleanup_kernel_size=1,
    )

    assert sum(row["kept"] for row in cleanup.component_decisions) == 2
    assert result.outside_length_mm == pytest.approx(60.0, abs=0.2)
    assert result.robust_length_mm == pytest.approx(60.0, abs=0.5)


def test_saved_c920_sam_masks_produce_deterministic_measurements():
    expected = json.loads(
        (
            FIXTURE_DIR / "expected_grounded_sam_measurements.json"
        ).read_text(encoding="utf-8")
    )

    for sample in expected["samples"]:
        mask_path = (
            FIXTURE_DIR
            / (
                f"snapshot_20260726_{sample['stamp']}_mat_rectified"
                "_sam2_raw_mask.png"
            )
        )
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        assert mask is not None

        first = measure_metric_mask(
            mask,
            pixels_per_mm=expected["pixels_per_mm"],
            trim_percentile=expected["trim_percentile"],
        )
        second = measure_metric_mask(
            mask,
            pixels_per_mm=expected["pixels_per_mm"],
            trim_percentile=expected["trim_percentile"],
        )

        assert first.to_dict() == second.to_dict()
        assert first.outside_length_mm == pytest.approx(
            sample["outside_length_mm"],
            abs=1e-9,
        )
        assert first.outside_width_mm == pytest.approx(
            sample["outside_width_mm"],
            abs=1e-9,
        )
        assert first.robust_length_mm == pytest.approx(
            sample["robust_length_mm"],
            abs=1e-9,
        )
        assert first.robust_width_mm == pytest.approx(
            sample["robust_width_mm"],
            abs=1e-9,
        )
