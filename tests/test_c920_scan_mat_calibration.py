from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from core.calibration import (
    get_camera_profile,
    load_camera_profiles,
    validate_rectified_provenance,
)
from core.measurement import _measurement_scale


class C920ScanMatCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = get_camera_profile(
            logical_camera_id="logitech_c920", role="workbench"
        )
        camera = self.profile["camera"]
        self.active_camera = {
            "id": "logitech_c920",
            "role": "workbench",
            "resolved_device_path": "/dev/video2",
            "stable_identity": deepcopy(camera["stable_identity"]),
        }
        self.metadata = {
            "calibration_profile_id": self.profile["id"],
            "calibration_status": "calibrated",
            "logical_camera_id": "logitech_c920",
            "camera_role": "workbench",
            "stable_camera_identity": deepcopy(camera["stable_identity"]),
            "requested_mode": deepcopy(camera["requested_mode"]),
            "negotiated_mode": deepcopy(camera["negotiated_mode"]),
            "mode_status": "requested",
            "mode_mismatches": [],
            "source_image_dimensions": {"width": 1920, "height": 1080},
            "rectified_output_dimensions": {"width": 1440, "height": 1080},
            "geometry_version": "scan_mat_geometry_v1",
            "homography_version": "opencv_perspective_outer_boundary_v1",
        }

    def test_c920_profile_is_selected_for_workbench(self) -> None:
        self.assertEqual(self.profile["id"], "logitech_c920_overhead_scan_mat")
        self.assertEqual(self.profile["camera"]["logical_camera_id"], "logitech_c920")
        self.assertEqual(self.profile["camera"]["role"], "workbench")

    def test_physical_mat_produces_equal_metric_axes(self) -> None:
        calibration = {
            "known_width_mm": 24 * 25.4,
            "known_height_mm": 18 * 25.4,
            "mm_per_pixel_x": 99,
            "mm_per_pixel_y": 99,
        }
        scale = _measurement_scale(calibration, 1440, 1080)
        self.assertAlmostEqual(scale["mm_per_pixel_x"], 25.4 / 60, places=12)
        self.assertAlmostEqual(scale["mm_per_pixel_y"], 25.4 / 60, places=12)
        self.assertAlmostEqual(scale["mm_per_pixel_x"], scale["mm_per_pixel_y"], places=12)

    def test_mismatched_active_camera_is_rejected(self) -> None:
        active = {**self.active_camera, "id": "insta360_link", "role": "face"}
        with patch("core.calibration.get_camera_profile", return_value=self.profile):
            _, mismatches = validate_rectified_provenance(
                self.metadata, active_camera=active
            )
        self.assertTrue(any("active logical camera" in item for item in mismatches))
        self.assertTrue(any("active camera role" in item for item in mismatches))

    def test_mismatched_source_and_rectified_geometry_are_rejected(self) -> None:
        metadata = deepcopy(self.metadata)
        metadata["source_image_dimensions"]["width"] = 1280
        metadata["rectified_output_dimensions"]["height"] = 720
        with patch("core.calibration.get_camera_profile", return_value=self.profile):
            _, mismatches = validate_rectified_provenance(
                metadata, active_camera=self.active_camera
            )
        self.assertTrue(any("source image dimensions.width" in item for item in mismatches))
        self.assertTrue(any("rectified output dimensions.height" in item for item in mismatches))

    def test_stable_identity_survives_device_number_change(self) -> None:
        active = {**self.active_camera, "resolved_device_path": "/dev/video8"}
        metadata = {**self.metadata, "runtime_device": "/dev/video6"}
        with patch("core.calibration.get_camera_profile", return_value=self.profile):
            _, mismatches = validate_rectified_provenance(
                metadata, active_camera=active
            )
        self.assertEqual(mismatches, [])

    def test_active_profile_is_the_c920_station(self) -> None:
        config = load_camera_profiles()
        self.assertEqual(config["active_profile_id"], self.profile["id"])


if __name__ == "__main__":
    unittest.main()
