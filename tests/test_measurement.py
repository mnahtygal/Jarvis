import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

import api
from core.measurement import measure_object_bbox_from_image, rotated_box_physical_dimensions


CALIBRATION = {
    "ready": True,
    "profile_id": "test",
    "profile_name": "Synthetic test",
    "mm_per_pixel_x": 0.5,
    "mm_per_pixel_y": 0.5,
    "pixels_per_mm_x": 2.0,
    "pixels_per_mm_y": 2.0,
    "confidence": 0.95,
    "error": None,
}


class MeasurementEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, name: str, image: np.ndarray) -> Path:
        path = self.root / name
        self.assertTrue(cv2.imwrite(str(path), image))
        return path

    def _rectangle(self, background: int, foreground: int) -> np.ndarray:
        image = np.full((400, 500, 3), background, dtype=np.uint8)
        cv2.rectangle(image, (150, 140), (350, 260), (foreground,) * 3, -1)
        return image

    def test_dark_rectangle_on_light_background(self) -> None:
        path = self._write("dark_mat_rectified.jpg", self._rectangle(235, 25))
        result = measure_object_bbox_from_image(str(path), CALIBRATION)
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["long_side"], 100, delta=3)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["short_side"], 60, delta=3)

    def test_light_rectangle_on_dark_background(self) -> None:
        path = self._write("light_mat_rectified.jpg", self._rectangle(20, 235))
        result = measure_object_bbox_from_image(str(path), CALIBRATION)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["measurement"]["method"], "rotated_contour_measurement_v1")

    def test_rotated_rectangle_and_artifacts(self) -> None:
        image = np.full((400, 500, 3), 235, dtype=np.uint8)
        box = cv2.boxPoints(((250, 200), (180, 80), 28))
        cv2.fillPoly(image, [np.int32(box)], (25, 25, 25))
        path = self._write("rotated_mat_rectified.jpg", image)
        result = measure_object_bbox_from_image(str(path), CALIBRATION)
        self.assertTrue(result["ok"], result)
        measurement = result["measurement"]
        self.assertGreaterEqual(len(measurement["contour_px"]), 4)
        self.assertAlmostEqual(measurement["dimensions_mm"]["long_side"], 90, delta=3)
        self.assertAlmostEqual(abs(measurement["rotated_box_px"]["rotation_degrees"]), 28, delta=3)
        self.assertTrue(Path(measurement["artifacts"]["mask_path"]).is_file())
        self.assertTrue(Path(measurement["artifacts"]["overlay_path"]).is_file())

    def test_non_square_calibration(self) -> None:
        calibration = {**CALIBRATION, "mm_per_pixel_x": 0.5, "mm_per_pixel_y": 1.0}
        path = self._write("anisotropic_mat_rectified.jpg", self._rectangle(235, 25))
        result = measure_object_bbox_from_image(str(path), calibration)
        self.assertTrue(result["ok"], result)
        dimensions = result["measurement"]["dimensions_mm"]
        self.assertAlmostEqual(dimensions["long_side"], 120, delta=4)
        self.assertAlmostEqual(dimensions["short_side"], 100, delta=4)

    def test_small_noise_is_ignored(self) -> None:
        image = self._rectangle(235, 25)
        for point in ((30, 30), (450, 50), (70, 330), (430, 350)):
            cv2.circle(image, point, 2, (20, 20, 20), -1)
        result = measure_object_bbox_from_image(
            str(self._write("noise_mat_rectified.jpg", image)), CALIBRATION
        )
        self.assertTrue(result["ok"], result)
        self.assertGreater(result["diagnostics"]["rejected_candidate_counts"]["below_minimum_area"], 0)

    def test_full_image_border_is_rejected(self) -> None:
        image = np.full((400, 500, 3), 230, dtype=np.uint8)
        cv2.rectangle(image, (1, 1), (498, 398), (20, 20, 20), 8)
        result = measure_object_bbox_from_image(
            str(self._write("frame_mat_rectified.jpg", image)), CALIBRATION
        )
        self.assertFalse(result["ok"])
        self.assertIn(result["diagnostics"]["failure_reason"], {"no_object_found", "object_touching_image_boundary"})

    def test_no_object_found(self) -> None:
        image = np.full((400, 500, 3), 128, dtype=np.uint8)
        result = measure_object_bbox_from_image(
            str(self._write("blank_mat_rectified.jpg", image)), CALIBRATION
        )
        self.assertFalse(result["ok"])
        self.assertIn(result["diagnostics"]["failure_reason"], {"no_object_found", "object_touching_image_boundary"})

    def test_calibration_unavailable_and_missing_image(self) -> None:
        unavailable = {**CALIBRATION, "ready": False}
        result = measure_object_bbox_from_image(str(self.root / "missing.jpg"), unavailable)
        self.assertEqual(result["diagnostics"]["failure_reason"], "calibration_not_ready")
        result = measure_object_bbox_from_image(str(self.root / "missing.jpg"), CALIBRATION)
        self.assertEqual(result["diagnostics"]["failure_reason"], "image_file_missing")

    def test_anisotropic_rotated_edge_math(self) -> None:
        angle = math.radians(30)
        vector = (100 * math.cos(angle), 100 * math.sin(angle))
        perpendicular = (-40 * math.sin(angle), 40 * math.cos(angle))
        box = [(0, 0), vector, (vector[0] + perpendicular[0], vector[1] + perpendicular[1]), perpendicular]
        result = rotated_box_physical_dimensions(box, 0.5, 1.0)
        expected = math.hypot(vector[0] * 0.5, vector[1])
        self.assertAlmostEqual(result["long_side_mm"], expected, places=5)

    def test_api_preserves_legacy_bbox_and_adds_artifact_urls(self) -> None:
        mat_dir = self.root / "mat_analysis"
        mat_dir.mkdir()
        path = mat_dir / "snapshot_mat_rectified.jpg"
        cv2.imwrite(str(path), self._rectangle(235, 25))

        def measure(image_path: str):
            return measure_object_bbox_from_image(image_path, CALIBRATION)

        with patch.object(api, "MAT_ANALYSIS_DIR", mat_dir), patch.object(
            api, "measure_object_bbox_from_image", side_effect=measure
        ):
            response = api.app.test_client().post(
                "/api/measurement/analyze", json={"image_path": str(path)}
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("bbox_mm", payload["measurement"])
        self.assertIn("overlay_url", payload["measurement"]["artifacts"])
        self.assertIn("mask_url", payload["measurement"]["artifacts"])

    def test_api_rejects_non_rectified_path(self) -> None:
        mat_dir = self.root / "mat_analysis"
        mat_dir.mkdir()
        path = self._write("unrelated.jpg", self._rectangle(235, 25))
        with patch.object(api, "MAT_ANALYSIS_DIR", mat_dir):
            response = api.app.test_client().post(
                "/api/measurement/analyze", json={"image_path": str(path)}
            )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
