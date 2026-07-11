from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - exercised only when OpenCV is unavailable.
    cv2 = None
    np = None

from skills.scan_mat_skill import analyze_scan_mat


@unittest.skipIf(cv2 is None or np is None, "OpenCV and numpy are required")
class ScanMatSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_image(self, name: str, image) -> Path:
        path = self.root / name
        self.assertTrue(cv2.imwrite(str(path), image))
        return path

    def _blank(self, width: int = 800, height: int = 600):
        return np.zeros((height, width, 3), dtype=np.uint8)

    def test_clean_synthetic_rectangle_succeeds(self) -> None:
        image = self._blank()
        cv2.rectangle(image, (120, 90), (680, 510), (210, 210, 210), -1)
        cv2.rectangle(image, (120, 90), (680, 510), (20, 20, 20), 4)

        result = analyze_scan_mat(self._write_image("clean.jpg", image), self.root / "out")

        self.assertTrue(result["ok"])
        self.assertTrue(result["mat_detected"])
        self.assertEqual(result["diagnostics"]["selected_method"], "approx_poly")
        self.assertIsNone(result["diagnostics"]["failure_reason"])
        self.assertTrue(Path(result["rectified_path"]).is_file())

    def test_perspective_quadrilateral_succeeds(self) -> None:
        image = self._blank()
        points = np.array([[155, 130], [650, 80], [705, 500], [95, 540]], dtype=np.int32)
        cv2.fillConvexPoly(image, points, (215, 215, 215))
        cv2.polylines(image, [points], True, (20, 20, 20), 5)

        result = analyze_scan_mat(self._write_image("perspective.jpg", image), self.root / "out")

        self.assertTrue(result["ok"])
        self.assertTrue(result["mat_detected"])
        self.assertTrue(result["diagnostics"]["corners_detected"])
        self.assertEqual(len(result["mat"]["corners"]), 4)

    def test_noisy_broken_border_succeeds(self) -> None:
        image = self._blank()
        cv2.rectangle(image, (120, 90), (680, 510), (205, 205, 205), -1)
        for x in range(160, 660, 80):
            cv2.line(image, (x, 95), (x, 505), (150, 150, 150), 1)
        for y in range(130, 500, 60):
            cv2.line(image, (125, y), (675, y), (150, 150, 150), 1)
        cv2.line(image, (120, 90), (360, 90), (25, 25, 25), 5)
        cv2.line(image, (410, 90), (680, 90), (25, 25, 25), 5)
        cv2.line(image, (680, 90), (680, 510), (25, 25, 25), 5)
        cv2.line(image, (680, 510), (120, 510), (25, 25, 25), 5)
        cv2.line(image, (120, 510), (120, 90), (25, 25, 25), 5)
        noise = np.random.default_rng(7).integers(0, 18, image.shape, dtype=np.uint8)
        image = cv2.add(image, noise)

        result = analyze_scan_mat(self._write_image("noisy.jpg", image), self.root / "out")

        self.assertTrue(result["ok"])
        self.assertTrue(result["mat_detected"])
        self.assertIsNone(result["diagnostics"]["failure_reason"])

    def test_room_like_random_shapes_do_not_false_detect(self) -> None:
        image = np.full((600, 800, 3), 35, dtype=np.uint8)
        cv2.circle(image, (380, 280), 115, (180, 180, 180), -1)
        cv2.ellipse(image, (520, 300), (95, 170), 12, 0, 360, (125, 125, 125), -1)
        cv2.line(image, (30, 560), (760, 45), (220, 220, 220), 9)
        cv2.circle(image, (185, 145), 70, (95, 95, 95), -1)

        result = analyze_scan_mat(self._write_image("room_like.jpg", image), self.root / "out")

        self.assertFalse(result["ok"])
        self.assertFalse(result["mat_detected"])
        self.assertIn(
            result["diagnostics"]["failure_reason"],
            {"no_contours_found", "no_quadrilateral_candidates"},
        )
        self.assertNotIn("rectified_path", result)

    def test_blank_image_fails_cleanly_without_rectified_path(self) -> None:
        result = analyze_scan_mat(self._write_image("blank.jpg", self._blank()), self.root / "out")

        self.assertFalse(result["ok"])
        self.assertFalse(result["mat_detected"])
        self.assertEqual(result["diagnostics"]["failure_reason"], "no_contours_found")
        self.assertFalse(result["diagnostics"]["rectified_available"])
        self.assertNotIn("rectified_path", result)


if __name__ == "__main__":
    unittest.main()
