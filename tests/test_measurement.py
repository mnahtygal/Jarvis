import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

import api
from core.calibration import apply_calibration_to_active_profile
from core.measurement import (
    MAX_OBJECT_CANDIDATES,
    MIN_CANDIDATE_SCORE,
    SegmentationResult,
    _apply_enclosing_structure_penalties,
    _candidate_score_is_acceptable,
    _candidates_represent_same_object,
    _score_candidate,
    _segment_object_masks,
    _measurement_scale,
    measure_object_bbox_from_image,
    rotated_box_physical_dimensions,
)


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

    def _candidate_grid_segmentation(
        self,
        count: int,
        width: int = 1200,
        height: int = 1200,
    ) -> SegmentationResult:
        margin = 30
        mask = np.zeros((height, width), dtype=np.uint8)
        for index in range(count):
            column = index % 9
            row = index // 9
            x = 45 + column * 125
            y = 45 + row * 125
            cv2.rectangle(mask, (x, y), (x + 60, y + 60), 255, -1)
        return SegmentationResult(
            masks=[("clahe_otsu_inverted", mask)],
            usable_margin_px=margin,
            usable_area_px=(width - 2 * margin) * (height - 2 * margin),
            grid_line_pixels=0,
        )

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

    def test_rectified_mat_dimensions_override_raw_frame_pixel_scale(self) -> None:
        calibration = {
            **CALIBRATION,
            "mm_per_pixel_x": 0.9,
            "mm_per_pixel_y": 1.2,
            "known_width_mm": 250.0,
            "known_height_mm": 200.0,
        }
        path = self._write("scaled_mat_rectified.jpg", self._rectangle(235, 25))

        result = measure_object_bbox_from_image(str(path), calibration)

        self.assertTrue(result["ok"], result)
        dimensions = result["measurement"]["dimensions_mm"]
        self.assertAlmostEqual(dimensions["long_side"], 100, delta=3)
        self.assertAlmostEqual(dimensions["short_side"], 60, delta=3)
        self.assertEqual(
            result["diagnostics"]["calibration_source"],
            "rectified_mat_dimensions",
        )
        self.assertAlmostEqual(result["measurement"]["mm_per_pixel_x"], 0.5)

    def test_canonical_rectified_size_uses_mat_geometry_scale(self) -> None:
        scale = _measurement_scale(CALIBRATION, 1440, 1080)

        self.assertEqual(scale["source"], "canonical_rectified_mat_geometry")
        self.assertAlmostEqual(scale["mm_per_pixel_x"], 25.4 / 60.0, places=8)
        self.assertAlmostEqual(scale["mm_per_pixel_y"], 25.4 / 60.0, places=8)

    def test_future_calibration_save_preserves_known_mat_dimensions(self) -> None:
        calibration = {
            "known_width_mm": 609.6,
            "known_height_mm": 457.2,
            "pixel_to_mm_x": 0.4,
            "pixel_to_mm_y": 0.4,
            "mm_per_pixel_x": 0.4,
            "mm_per_pixel_y": 0.4,
            "pixels_per_mm_x": 2.5,
            "pixels_per_mm_y": 2.5,
            "confidence": 0.95,
        }
        with patch(
            "core.calibration.update_active_camera_profile",
            side_effect=lambda updates: updates,
        ):
            updated = apply_calibration_to_active_profile(calibration)

        self.assertEqual(updated["calibration"]["known_width_mm"], 609.6)
        self.assertEqual(updated["calibration"]["known_height_mm"], 457.2)

    def test_small_noise_is_ignored(self) -> None:
        image = self._rectangle(235, 25)
        for point in ((30, 30), (450, 50), (70, 330), (430, 350)):
            cv2.circle(image, point, 2, (20, 20, 20), -1)
        result = measure_object_bbox_from_image(
            str(self._write("noise_mat_rectified.jpg", image)), CALIBRATION
        )
        self.assertTrue(result["ok"], result)
        self.assertGreater(result["diagnostics"]["rejected_candidate_counts"]["below_minimum_area"], 0)

    def test_grid_lines_without_object_are_suppressed(self) -> None:
        image = np.full((400, 500, 3), 235, dtype=np.uint8)
        for x in range(25, 500, 25):
            cv2.line(image, (x, 0), (x, 399), (170, 170, 170), 1)
        for y in range(25, 400, 25):
            cv2.line(image, (0, y), (499, y), (170, 170, 170), 1)

        result = measure_object_bbox_from_image(
            str(self._write("grid_only_mat_rectified.jpg", image)), CALIBRATION
        )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "no_object")
        self.assertGreater(result["diagnostics"]["grid_line_pixels_suppressed"], 0)

    def test_colored_object_on_dark_bright_grid_mat(self) -> None:
        image = np.full((400, 500, 3), 20, dtype=np.uint8)
        for x in range(25, 500, 25):
            cv2.line(image, (x, 0), (x, 399), (180, 180, 180), 1)
        for y in range(25, 400, 25):
            cv2.line(image, (0, y), (499, y), (180, 180, 180), 1)
        box = cv2.boxPoints(((250, 200), (180, 80), 18))
        cv2.fillPoly(image, [np.int32(box)], (130, 65, 20))

        result = measure_object_bbox_from_image(
            str(self._write("color_dark_grid_mat_rectified.jpg", image)), CALIBRATION
        )

        self.assertTrue(result["ok"], result)
        self.assertIn(
            "hsv_chroma_connected",
            result["diagnostics"]["threshold_strategies_attempted"],
        )
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["long_side"], 90, delta=4)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["short_side"], 40, delta=4)

    def test_uneven_lighting_still_finds_dark_object(self) -> None:
        gradient = np.tile(np.linspace(165, 245, 500, dtype=np.uint8), (400, 1))
        image = cv2.merge([gradient, gradient, gradient])
        cv2.rectangle(image, (160, 145), (340, 255), (30, 30, 30), -1)

        result = measure_object_bbox_from_image(
            str(self._write("uneven_mat_rectified.jpg", image)), CALIBRATION
        )

        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["long_side"], 90, delta=4)
        self.assertIn("adaptive_inverted", result["diagnostics"]["threshold_strategies_attempted"])

    def test_legitimate_narrow_object_is_measured(self) -> None:
        image = np.full((400, 500, 3), 235, dtype=np.uint8)
        cv2.rectangle(image, (145, 194), (355, 206), (25, 25, 25), -1)

        result = measure_object_bbox_from_image(
            str(self._write("narrow_mat_rectified.jpg", image)), CALIBRATION
        )

        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["long_side"], 105, delta=4)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["short_side"], 6, delta=2)

    def test_object_near_usable_boundary_is_measured(self) -> None:
        image = np.full((400, 500, 3), 235, dtype=np.uint8)
        cv2.rectangle(image, (18, 145), (158, 255), (25, 25, 25), -1)

        result = measure_object_bbox_from_image(
            str(self._write("near_edge_mat_rectified.jpg", image)), CALIBRATION
        )

        self.assertTrue(result["ok"], result)
        self.assertGreater(result["diagnostics"]["selected_border_distance_px"], 1)

    def test_valid_object_wins_over_larger_border_contour(self) -> None:
        image = np.full((400, 500, 3), 235, dtype=np.uint8)
        cv2.rectangle(image, (1, 1), (498, 398), (20, 20, 20), 6)
        cv2.rectangle(image, (170, 150), (330, 250), (30, 30, 30), -1)

        result = measure_object_bbox_from_image(
            str(self._write("border_and_object_mat_rectified.jpg", image)), CALIBRATION
        )

        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["long_side"], 80, delta=4)

    def test_multiple_candidates_selects_stronger_center_object(self) -> None:
        image = np.full((400, 500, 3), 235, dtype=np.uint8)
        cv2.rectangle(image, (160, 145), (340, 255), (25, 25, 25), -1)
        cv2.rectangle(image, (55, 55), (105, 90), (25, 25, 25), -1)

        result = measure_object_bbox_from_image(
            str(self._write("multiple_mat_rectified.jpg", image)), CALIBRATION
        )

        self.assertTrue(result["ok"], result)
        self.assertGreaterEqual(result["diagnostics"]["candidate_count"], 2)
        self.assertAlmostEqual(result["measurement"]["dimensions_mm"]["long_side"], 90, delta=4)

    def test_rotated_dimensions_remain_stable(self) -> None:
        measured = []
        for angle in (0, 15, 30, 45, 75, 89):
            image = np.full((400, 500, 3), 235, dtype=np.uint8)
            box = cv2.boxPoints(((250, 200), (180, 70), angle))
            cv2.fillPoly(image, [np.int32(box)], (25, 25, 25))
            result = measure_object_bbox_from_image(
                str(self._write(f"angle_{angle}_mat_rectified.jpg", image)), CALIBRATION
            )
            self.assertTrue(result["ok"], (angle, result))
            measured.append(result["measurement"]["dimensions_mm"])

        for dimensions in measured:
            self.assertAlmostEqual(dimensions["long_side"], 90, delta=3)
            self.assertAlmostEqual(dimensions["short_side"], 35, delta=3)

    def test_segmentation_is_bounded_and_produces_usable_masks(self) -> None:
        image = self._rectangle(235, 25)
        segmentation = _segment_object_masks(image, cv2, np)

        self.assertEqual(len(segmentation.masks), 6)
        self.assertGreater(segmentation.usable_margin_px, 0)
        self.assertTrue(all(mask.shape == image.shape[:2] for _, mask in segmentation.masks))
        self.assertTrue(any(cv2.countNonZero(mask) > 0 for _, mask in segmentation.masks))

    def test_cross_strategy_candidates_group_and_gain_consensus_bonus(self) -> None:
        image = np.full((400, 500, 3), 235, dtype=np.uint8)
        mask = np.zeros((400, 500), dtype=np.uint8)
        cv2.rectangle(mask, (150, 140), (350, 260), 255, -1)
        segmentation = SegmentationResult(
            masks=[
                ("clahe_otsu_inverted", mask.copy()),
                ("adaptive_inverted", mask.copy()),
            ],
            usable_margin_px=10,
            usable_area_px=182400,
            grid_line_pixels=0,
        )
        path = self._write("consensus_mat_rectified.jpg", image)

        with patch(
            "core.measurement._segment_object_masks",
            return_value=segmentation,
        ):
            result = measure_object_bbox_from_image(str(path), CALIBRATION)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["diagnostics"]["candidate_count"], 1)
        self.assertEqual(result["diagnostics"]["selected_strategy_count"], 2)
        self.assertEqual(
            result["diagnostics"]["selected_strategies"],
            ["clahe_otsu_inverted", "adaptive_inverted"],
        )
        self.assertAlmostEqual(
            result["diagnostics"]["candidate_scores"][0]["consensus_bonus"],
            0.04,
        )

    def test_overlapping_distinct_contours_are_not_grouped(self) -> None:
        first_contour = np.array(
            [[[100, 100]], [[200, 100]], [[200, 130]], [[130, 130]],
             [[130, 200]], [[100, 200]]],
            dtype=np.int32,
        )
        second_contour = np.array(
            [[[100, 100]], [[130, 100]], [[130, 170]], [[200, 170]],
             [[200, 200]], [[100, 200]]],
            dtype=np.int32,
        )
        shared_bbox = {"x": 100, "y": 100, "width": 101, "height": 101}

        grouped = _candidates_represent_same_object(
            {"bbox": shared_bbox, "contour": first_contour},
            {"bbox": shared_bbox, "contour": second_contour},
            cv2,
            np,
        )

        self.assertFalse(grouped)

    def test_candidate_score_threshold_is_inclusive(self) -> None:
        self.assertTrue(_candidate_score_is_acceptable(MIN_CANDIDATE_SCORE))
        self.assertFalse(
            _candidate_score_is_acceptable(MIN_CANDIDATE_SCORE - 0.0001)
        )

    def test_lone_candidate_below_score_threshold_is_low_confidence(self) -> None:
        image = np.full((400, 500, 3), 128, dtype=np.uint8)
        mask = np.zeros((400, 500), dtype=np.uint8)
        cv2.rectangle(mask, (13, 13), (50, 35), 255, -1)
        segmentation = SegmentationResult(
            masks=[("local_background_difference", mask)],
            usable_margin_px=10,
            usable_area_px=182400,
            grid_line_pixels=0,
        )
        path = self._write("low_score_mat_rectified.jpg", image)

        with patch(
            "core.measurement._segment_object_masks",
            return_value=segmentation,
        ):
            result = measure_object_bbox_from_image(str(path), CALIBRATION)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "low_confidence")
        self.assertEqual(
            result["diagnostics"]["failure_reason"],
            "candidate_score_below_threshold",
        )
        self.assertLess(
            result["diagnostics"]["selected_candidate_score"],
            MIN_CANDIDATE_SCORE,
        )

    def test_candidate_cutoff_allows_64_but_rejects_65(self) -> None:
        image = np.full((1200, 1200, 3), 128, dtype=np.uint8)
        path = self._write("candidate_limit_mat_rectified.jpg", image)

        with patch(
            "core.measurement._segment_object_masks",
            return_value=self._candidate_grid_segmentation(MAX_OBJECT_CANDIDATES),
        ):
            at_limit = measure_object_bbox_from_image(str(path), CALIBRATION)

        self.assertEqual(
            at_limit["diagnostics"]["candidate_count"],
            MAX_OBJECT_CANDIDATES,
        )
        self.assertFalse(
            at_limit["diagnostics"].get("background_structure_detected", False)
        )

        with patch(
            "core.measurement._segment_object_masks",
            return_value=self._candidate_grid_segmentation(
                MAX_OBJECT_CANDIDATES + 1
            ),
        ):
            excessive = measure_object_bbox_from_image(str(path), CALIBRATION)

        self.assertFalse(excessive["ok"], excessive)
        self.assertEqual(excessive["status"], "no_object")
        self.assertEqual(
            excessive["diagnostics"]["candidate_count"],
            MAX_OBJECT_CANDIDATES + 1,
        )
        self.assertTrue(excessive["diagnostics"]["background_structure_detected"])

    def test_contour_px_preserves_full_contour_and_adds_capped_simplification(
        self,
    ) -> None:
        image = np.full((600, 600, 3), 235, dtype=np.uint8)
        mask = np.zeros((600, 600), dtype=np.uint8)
        cv2.circle(mask, (300, 300), 130, 255, -1)
        segmentation = SegmentationResult(
            masks=[("clahe_otsu_inverted", mask)],
            usable_margin_px=15,
            usable_area_px=570 * 570,
            grid_line_pixels=0,
        )
        path = self._write("contour_compatibility_mat_rectified.jpg", image)

        with patch(
            "core.measurement._segment_object_masks",
            return_value=segmentation,
        ):
            result = measure_object_bbox_from_image(str(path), CALIBRATION)

        self.assertTrue(result["ok"], result)
        contour = result["measurement"]["contour_px"]
        simplified = result["measurement"]["simplified_contour_px"]
        self.assertEqual(
            len(contour),
            result["diagnostics"]["selected_contour_point_count"],
        )
        self.assertLessEqual(len(simplified), 256)
        self.assertLess(len(simplified), len(contour))

    def test_diffuse_enclosing_region_is_demoted_without_trimming_object(self) -> None:
        outer = {
            "area_ratio": 0.05,
            "bbox": {"x": 300, "y": 250, "width": 700, "height": 500},
            "extent": 0.34,
            "solidity": 0.58,
            "score": 0.65,
        }
        inner = {
            "area_ratio": 0.005,
            "bbox": {"x": 640, "y": 490, "width": 160, "height": 80},
            "extent": 0.66,
            "solidity": 0.73,
            "score": 0.61,
        }

        _apply_enclosing_structure_penalties([outer, inner])

        self.assertEqual(outer["enclosing_structure_penalty"], 0.08)
        self.assertAlmostEqual(outer["score"], 0.57)
        self.assertEqual(inner["enclosing_structure_penalty"], 0.0)
        self.assertEqual(inner["bbox"]["width"], 160)

    def test_thin_line_and_degenerate_candidates_are_rejected(self) -> None:
        thin = np.array([[[40, 200]], [[460, 200]], [[460, 202]], [[40, 202]]], dtype=np.int32)
        candidate, reason = _score_candidate(thin, "test", 500, 400, 182400, 10, cv2)
        self.assertIsNone(candidate)
        self.assertEqual(reason, "grid_line_like")

        degenerate = np.array([[[100, 100]], [[200, 100]], [[300, 100]]], dtype=np.int32)
        candidate, reason = _score_candidate(degenerate, "test", 500, 400, 182400, 10, cv2)
        self.assertIsNone(candidate)
        self.assertIn(reason, {"below_minimum_area", "invalid_geometry"})

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

    def test_calibration_geometry_mismatch_is_structured(self) -> None:
        calibration = {
            **CALIBRATION,
            "rectified_output_dimensions": {"width": 1440, "height": 1080},
        }
        path = self._write(
            "geometry_mismatch_mat_rectified.jpg",
            self._rectangle(235, 25),
        )

        result = measure_object_bbox_from_image(str(path), calibration)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "calibration_invalid")
        self.assertEqual(
            result["diagnostics"]["failure_reason"],
            "calibration_geometry_mismatch",
        )

    def test_measurement_artifact_write_failures_are_structured(self) -> None:
        path = self._write(
            "write_failure_mat_rectified.jpg",
            self._rectangle(235, 25),
        )
        original_imwrite = cv2.imwrite

        for failed_suffix, expected_reason in (
            ("_measurement_mask.png", "mask_write_failure"),
            ("_measurement_overlay.jpg", "overlay_write_failure"),
        ):
            with self.subTest(failed_suffix=failed_suffix):
                def fail_selected_artifact(output_path, image):
                    if str(output_path).endswith(failed_suffix):
                        return False
                    return original_imwrite(str(output_path), image)

                with patch.object(
                    cv2,
                    "imwrite",
                    side_effect=fail_selected_artifact,
                ):
                    result = measure_object_bbox_from_image(
                        str(path), CALIBRATION
                    )

                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "measurement_failed")
                self.assertEqual(
                    result["diagnostics"]["failure_reason"],
                    expected_reason,
                )
                self.assertNotIn("measurement", result)

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
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["calibrated"])
        self.assertEqual(payload["unit"], "mm")
        self.assertGreater(payload["measurement"]["confidence"], 0)
        self.assertIsInstance(payload["diagnostics"]["processing_ms"], float)

    def test_api_rejects_non_rectified_path(self) -> None:
        mat_dir = self.root / "mat_analysis"
        mat_dir.mkdir()
        path = self._write("unrelated.jpg", self._rectangle(235, 25))
        with patch.object(api, "MAT_ANALYSIS_DIR", mat_dir):
            response = api.app.test_client().post(
                "/api/measurement/analyze", json={"image_path": str(path)}
            )
        self.assertEqual(response.status_code, 400)

    def test_api_no_object_is_structured_and_not_server_error(self) -> None:
        mat_dir = self.root / "mat_analysis"
        mat_dir.mkdir()
        path = mat_dir / "blank_mat_rectified.jpg"
        cv2.imwrite(str(path), np.full((400, 500, 3), 128, dtype=np.uint8))

        def measure(image_path: str):
            return measure_object_bbox_from_image(image_path, CALIBRATION)

        with patch.object(api, "MAT_ANALYSIS_DIR", mat_dir), patch.object(
            api, "measure_object_bbox_from_image", side_effect=measure
        ):
            response = api.app.test_client().post(
                "/api/measurement/analyze", json={"image_path": str(path)}
            )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertEqual(payload["status"], "no_object")
        self.assertEqual(payload["diagnostics"]["failure_reason"], "no_object_found")

    def test_api_unreadable_rectified_image_is_expected_failure(self) -> None:
        mat_dir = self.root / "mat_analysis"
        mat_dir.mkdir()
        path = mat_dir / "broken_mat_rectified.jpg"
        path.write_bytes(b"not an image")

        def measure(image_path: str):
            return measure_object_bbox_from_image(image_path, CALIBRATION)

        with patch.object(api, "MAT_ANALYSIS_DIR", mat_dir), patch.object(
            api, "measure_object_bbox_from_image", side_effect=measure
        ):
            response = api.app.test_client().post(
                "/api/measurement/analyze", json={"image_path": str(path)}
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["status"], "invalid_frame")

    def test_api_calibration_geometry_mismatch_is_expected_failure(self) -> None:
        mat_dir = self.root / "mat_analysis"
        mat_dir.mkdir()
        path = mat_dir / "geometry_mat_rectified.jpg"
        cv2.imwrite(str(path), self._rectangle(235, 25))
        result = {
            "ok": False,
            "status": "calibration_invalid",
            "calibrated": True,
            "unit": "mm",
            "error": "Rectified image geometry does not match its calibration profile.",
            "diagnostics": {
                "failure_reason": "calibration_geometry_mismatch",
            },
        }

        with patch.object(api, "MAT_ANALYSIS_DIR", mat_dir), patch.object(
            api, "measure_object_bbox_from_image", return_value=result
        ):
            response = api.app.test_client().post(
                "/api/measurement/analyze", json={"image_path": str(path)}
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["status"], "calibration_invalid")


if __name__ == "__main__":
    unittest.main()
