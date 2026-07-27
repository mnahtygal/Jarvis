from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - exercised only when OpenCV is unavailable.
    cv2 = None
    np = None

from skills.scan_mat_skill import _cv2_missing, analyze_scan_mat
import api


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
        self.assertGreaterEqual(result["diagnostics"]["mat_confidence"], 0.42)
        self.assertIsInstance(result["diagnostics"]["processing_ms"], float)
        self.assertEqual(result["status"], "ready")
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
        top_left, top_right, bottom_right, bottom_left = result["mat"]["corners"]
        self.assertLess(top_left[0], top_right[0])
        self.assertLess(top_left[1], bottom_left[1])
        self.assertGreater(bottom_right[0], bottom_left[0])
        self.assertGreater(bottom_right[1], top_right[1])

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

    def test_concave_invalid_quadrilateral_is_rejected(self) -> None:
        image = self._blank()
        points = np.array(
            [[120, 100], [680, 100], [420, 300], [680, 500], [120, 500]],
            dtype=np.int32,
        )
        cv2.fillPoly(image, [points], (215, 215, 215))
        cv2.polylines(image, [points], True, (20, 20, 20), 5)

        result = analyze_scan_mat(
            self._write_image("concave.jpg", image), self.root / "out"
        )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "no_mat")

    def test_too_small_mat_is_rejected(self) -> None:
        image = self._blank()
        cv2.rectangle(image, (330, 250), (470, 350), (215, 215, 215), -1)
        cv2.rectangle(image, (330, 250), (470, 350), (20, 20, 20), 3)

        result = analyze_scan_mat(
            self._write_image("small.jpg", image), self.root / "out"
        )

        self.assertFalse(result["ok"], result)
        self.assertFalse(result["mat_detected"])

    def test_frame_filling_border_is_rejected(self) -> None:
        image = np.full((600, 800, 3), 210, dtype=np.uint8)
        cv2.rectangle(image, (0, 0), (799, 599), (20, 20, 20), 5)

        result = analyze_scan_mat(
            self._write_image("clipped.jpg", image), self.root / "out"
        )

        self.assertFalse(result["ok"], result)
        self.assertFalse(result["mat_detected"])

    def test_uneven_lighting_mat_is_detected(self) -> None:
        gradient = np.tile(np.linspace(80, 210, 800, dtype=np.uint8), (600, 1))
        image = cv2.merge([gradient, gradient, gradient])
        cv2.rectangle(image, (120, 90), (680, 510), (220, 220, 220), -1)
        cv2.rectangle(image, (120, 90), (680, 510), (20, 20, 20), 5)

        result = analyze_scan_mat(
            self._write_image("uneven_mat.jpg", image), self.root / "out"
        )

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["diagnostics"]["corners_detected"])

    def test_missing_image_fails_without_exception(self) -> None:
        result = analyze_scan_mat(self.root / "missing.jpg", self.root / "out")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid_frame")
        self.assertEqual(result["diagnostics"]["failure_reason"], "image_file_missing")

    def test_opencv_missing_uses_structured_contract(self) -> None:
        result = _cv2_missing(processing_ms=1.25)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "dependency_missing")
        self.assertEqual(result["diagnostics"]["failure_reason"], "opencv_missing")
        self.assertEqual(result["diagnostics"]["processing_ms"], 1.25)

    def test_required_artifact_write_failures_are_non_ready(self) -> None:
        image = self._blank()
        cv2.rectangle(image, (120, 90), (680, 510), (210, 210, 210), -1)
        cv2.rectangle(image, (120, 90), (680, 510), (20, 20, 20), 4)
        path = self._write_image("write_failure.jpg", image)
        original_imwrite = cv2.imwrite

        for failed_suffix, expected_reason in (
            ("_mat_annotated.jpg", "annotated_write_failed"),
            ("_mat_rectified.jpg", "rectified_write_failed"),
        ):
            with self.subTest(failed_suffix=failed_suffix):
                def fail_selected_artifact(output_path, output_image):
                    if str(output_path).endswith(failed_suffix):
                        return False
                    return original_imwrite(str(output_path), output_image)

                with patch.object(
                    cv2,
                    "imwrite",
                    side_effect=fail_selected_artifact,
                ):
                    result = analyze_scan_mat(path, self.root / failed_suffix)

                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "artifact_write_failed")
                self.assertEqual(
                    result["diagnostics"]["failure_reason"],
                    expected_reason,
                )
                if failed_suffix == "_mat_annotated.jpg":
                    self.assertNotIn("annotated_path", result)
                self.assertNotIn("rectified_path", result)

    def test_no_mat_annotated_write_failure_is_non_ready(self) -> None:
        path = self._write_image("blank_write_failure.jpg", self._blank())

        with patch.object(cv2, "imwrite", return_value=False):
            result = analyze_scan_mat(path, self.root / "blank-write-out")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "artifact_write_failed")
        self.assertEqual(
            result["diagnostics"]["failure_reason"],
            "annotated_write_failed",
        )
        self.assertNotIn("annotated_path", result)

    def test_empty_rectification_is_non_ready(self) -> None:
        image = self._blank()
        cv2.rectangle(image, (120, 90), (680, 510), (210, 210, 210), -1)
        cv2.rectangle(image, (120, 90), (680, 510), (20, 20, 20), 4)
        path = self._write_image("empty_rectification.jpg", image)

        with patch.object(cv2, "warpPerspective", return_value=None):
            result = analyze_scan_mat(path, self.root / "empty-out")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "rectification_failed")
        self.assertEqual(
            result["diagnostics"]["failure_reason"],
            "rectification_failed",
        )
        self.assertIn("annotated_path", result)
        self.assertNotIn("rectified_path", result)

    def test_provenance_validation_and_write_failures_are_non_ready(self) -> None:
        image = self._blank()
        cv2.rectangle(image, (120, 90), (680, 510), (210, 210, 210), -1)
        cv2.rectangle(image, (120, 90), (680, 510), (20, 20, 20), 4)
        path = self._write_image("provenance_failure.jpg", image)
        capture_metadata = {
            "camera": {"id": "logitech_c920", "role": "workbench"}
        }

        with patch(
            "skills.scan_mat_skill.build_scan_mat_provenance",
            side_effect=ValueError("synthetic provenance mismatch"),
        ):
            validation = analyze_scan_mat(
                path,
                self.root / "provenance-validation",
                capture_metadata=capture_metadata,
            )

        self.assertFalse(validation["ok"])
        self.assertEqual(validation["status"], "validation_failed")
        self.assertEqual(
            validation["diagnostics"]["failure_reason"],
            "calibration_provenance_validation_failed",
        )
        self.assertNotIn("metadata_path", validation)

        with patch(
            "skills.scan_mat_skill.build_scan_mat_provenance",
            return_value={"schema_version": 1},
        ), patch.object(
            Path,
            "write_text",
            side_effect=OSError("synthetic metadata write failure"),
        ):
            write_failure = analyze_scan_mat(
                path,
                self.root / "provenance-write",
                capture_metadata=capture_metadata,
            )

        self.assertFalse(write_failure["ok"])
        self.assertEqual(write_failure["status"], "artifact_write_failed")
        self.assertEqual(
            write_failure["diagnostics"]["failure_reason"],
            "calibration_provenance_write_failed",
        )
        self.assertNotIn("metadata_path", write_failure)

    def test_scan_mat_api_returns_structured_no_mat_response(self) -> None:
        path = self._write_image("api_blank.jpg", self._blank())
        result = analyze_scan_mat(path, self.root / "out")

        with patch.object(api, "_latest_snapshot_path", return_value=path), patch.object(
            api, "analyze_scan_mat", return_value=result
        ):
            response = api.app.test_client().post("/api/vision/scan-mat")

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "no_mat")
        self.assertEqual(payload["diagnostics"]["failure_reason"], "no_contours_found")

    def test_both_scan_mat_endpoints_use_expected_failure_policy(self) -> None:
        path = self._write_image("api_policy_blank.jpg", self._blank())
        result = analyze_scan_mat(path, self.root / "policy-out")
        capture = {
            "ok": True,
            "file_path": str(path),
            "camera": {"id": "logitech_c920", "role": "workbench"},
        }

        with patch.object(api, "_latest_snapshot_path", return_value=path), patch.object(
            api, "capture_snapshot", return_value=capture
        ), patch.object(api, "analyze_scan_mat", return_value=result):
            direct = api.app.test_client().post("/api/vision/scan-mat")
            captured = api.app.test_client().post(
                "/api/vision/capture-scan-mat"
            )

        self.assertEqual(direct.status_code, 422)
        self.assertEqual(captured.status_code, 422)
        self.assertEqual(direct.get_json()["status"], "no_mat")
        self.assertEqual(captured.get_json()["mat_analysis"]["status"], "no_mat")

    def test_both_scan_mat_endpoints_treat_missing_source_as_422(self) -> None:
        missing_capture = {
            "ok": True,
            "file_path": str(self.root / "missing-capture.jpg"),
        }

        with patch.object(api, "_latest_snapshot_path", return_value=None):
            direct = api.app.test_client().post("/api/vision/scan-mat")

        with patch.object(
            api, "capture_snapshot", return_value=missing_capture
        ), patch.object(api, "_latest_snapshot_path", return_value=None):
            captured = api.app.test_client().post(
                "/api/vision/capture-scan-mat"
            )

        self.assertEqual(direct.status_code, 422)
        self.assertEqual(captured.status_code, 422)
        self.assertEqual(direct.get_json()["status"], "invalid_frame")
        self.assertEqual(captured.get_json()["status"], "invalid_frame")
        self.assertEqual(
            direct.get_json()["diagnostics"]["failure_reason"],
            "image_file_missing",
        )
        self.assertEqual(
            captured.get_json()["diagnostics"]["failure_reason"],
            "image_file_missing",
        )

    def test_scan_mat_dependency_rectification_and_write_failures_are_422(
        self,
    ) -> None:
        path = self._write_image("api_expected_failures.jpg", self._blank())
        cases = (
            _cv2_missing(processing_ms=1.0),
            {
                "ok": False,
                "status": "rectification_failed",
                "mat_detected": True,
                "diagnostics": {"failure_reason": "rectification_failed"},
            },
            {
                "ok": False,
                "status": "artifact_write_failed",
                "mat_detected": True,
                "diagnostics": {"failure_reason": "rectified_write_failed"},
            },
        )

        for result in cases:
            with self.subTest(status=result["status"]), patch.object(
                api, "_latest_snapshot_path", return_value=path
            ), patch.object(api, "analyze_scan_mat", return_value=result):
                response = api.app.test_client().post("/api/vision/scan-mat")

            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()["status"], result["status"])

    def test_both_scan_mat_endpoints_return_500_for_unexpected_failures(self) -> None:
        path = self._write_image("api_unexpected.jpg", self._blank())
        capture = {"ok": True, "file_path": str(path)}

        with patch.object(api, "_latest_snapshot_path", return_value=path), patch.object(
            api, "capture_snapshot", return_value=capture
        ), patch.object(
            api, "analyze_scan_mat", side_effect=RuntimeError("synthetic failure")
        ):
            direct = api.app.test_client().post("/api/vision/scan-mat")
            captured = api.app.test_client().post(
                "/api/vision/capture-scan-mat"
            )

        self.assertEqual(direct.status_code, 500)
        self.assertEqual(captured.status_code, 500)
        self.assertEqual(direct.get_json()["status"], "scan_failed")
        self.assertEqual(captured.get_json()["status"], "scan_failed")

    def test_blank_image_fails_cleanly_without_rectified_path(self) -> None:
        result = analyze_scan_mat(self._write_image("blank.jpg", self._blank()), self.root / "out")

        self.assertFalse(result["ok"])
        self.assertFalse(result["mat_detected"])
        self.assertEqual(result["diagnostics"]["failure_reason"], "no_contours_found")
        self.assertFalse(result["diagnostics"]["rectified_available"])
        self.assertNotIn("rectified_path", result)


if __name__ == "__main__":
    unittest.main()
