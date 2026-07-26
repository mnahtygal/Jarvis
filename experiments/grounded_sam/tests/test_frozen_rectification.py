import json
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np
import pytest

from experiments.grounded_sam.frozen_rectification import (
    rectify_with_frozen_homography,
    validate_capture_against_reference,
)
from experiments.grounded_sam.provenance import CalibrationProvenanceError


FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "c920_sim868_20260726"
)


def _reference():
    return json.loads(
        (
            FIXTURE_DIR
            / "snapshot_20260726_105242_mat_rectified.metadata.json"
        ).read_text(encoding="utf-8")
    )


def _capture():
    return json.loads(
        (FIXTURE_DIR / "sample_1_scan_response.json").read_text(
            encoding="utf-8"
        )
    )["capture"]


def test_runtime_device_number_change_does_not_reject_capture():
    capture = deepcopy(_capture())
    capture["device"] = "/dev/video99"
    capture["camera"]["resolved_device_path"] = "/dev/video99"

    validate_capture_against_reference(capture, _reference())


def test_capture_mode_mismatch_is_rejected():
    capture = deepcopy(_capture())
    capture["negotiated_mode"]["width"] = 1280

    with pytest.raises(
        CalibrationProvenanceError,
        match="negotiated_mode",
    ):
        validate_capture_against_reference(capture, _reference())


def test_frozen_homography_produces_canonical_dimensions():
    source = cv2.imread(
        str(FIXTURE_DIR / "snapshot_20260726_105242.jpg"),
        cv2.IMREAD_COLOR,
    )
    assert source is not None

    rectified = rectify_with_frozen_homography(source, _reference())

    assert rectified.shape == (1080, 1440, 3)


def test_source_geometry_mismatch_is_rejected():
    source = np.zeros((720, 1280, 3), dtype=np.uint8)

    with pytest.raises(
        CalibrationProvenanceError,
        match="Source geometry mismatch",
    ):
        rectify_with_frozen_homography(source, _reference())
