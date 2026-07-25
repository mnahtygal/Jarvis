import cv2
import numpy as np
import pytest

from experiments.grounded_sam.measurement import measure_metric_mask


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
