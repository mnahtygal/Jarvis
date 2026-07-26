import json
from copy import deepcopy
from pathlib import Path

import pytest

from experiments.grounded_sam.provenance import (
    CalibrationProvenanceError,
    validate_c920_provenance,
)


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "c920_sim868_20260726"
)
METADATA_PATH = (
    FIXTURE_DIR
    / "snapshot_20260726_105242_mat_rectified.metadata.json"
)


def _metadata():
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def test_accepts_completed_c920_calibration_provenance():
    calibration = validate_c920_provenance(
        _metadata(),
        rectified_width=1440,
        rectified_height=1080,
    )

    assert calibration.profile_id == "logitech_c920_overhead_scan_mat"
    assert calibration.logical_camera_id == "logitech_c920"
    assert calibration.mm_per_pixel_x == pytest.approx(25.4 / 60.0)
    assert calibration.mm_per_pixel_x == pytest.approx(
        calibration.mm_per_pixel_y
    )


@pytest.mark.parametrize(
    ("field", "bad_value", "message"),
    [
        ("logical_camera_id", "insta360_link", "logical_camera_id"),
        ("calibration_profile_id", "wrong_profile", "calibration_profile_id"),
        ("geometry_version", "old_geometry", "geometry_version"),
    ],
)
def test_rejects_calibration_identity_mismatches(
    field,
    bad_value,
    message,
):
    metadata = deepcopy(_metadata())
    metadata[field] = bad_value

    with pytest.raises(CalibrationProvenanceError, match=message):
        validate_c920_provenance(
            metadata,
            rectified_width=1440,
            rectified_height=1080,
        )


def test_rejects_source_and_rectified_geometry_mismatches():
    metadata = deepcopy(_metadata())
    metadata["source_image_dimensions"]["width"] = 1280

    with pytest.raises(
        CalibrationProvenanceError,
        match="source_image_dimensions.width.*actual_rectified_width",
    ):
        validate_c920_provenance(
            metadata,
            rectified_width=1280,
            rectified_height=1080,
        )


def test_runtime_device_number_is_not_a_calibration_key():
    metadata = deepcopy(_metadata())
    metadata["runtime_device"] = "/dev/video99"

    calibration = validate_c920_provenance(
        metadata,
        rectified_width=1440,
        rectified_height=1080,
    )

    assert calibration.logical_camera_id == "logitech_c920"
