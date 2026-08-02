import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from experiments.grounded_sam_backend.candidate import evaluate_candidate, select_candidate
from experiments.grounded_sam_backend.config import DetectorGuardrails, WorkerModelConfig
from experiments.grounded_sam_backend.lifecycle import LoadedModels, ModelLoadFailure, ModelRegistry
from experiments.grounded_sam_backend.mask_measurement import validate_and_clean_mask
from experiments.grounded_sam_backend.pipeline import _write_artifacts, dependency_probe
from experiments.grounded_sam_backend.provenance import ProvenanceMismatch, load_validated_provenance
from experiments.grounded_sam_backend.worker import GroundedSamWorker
from tools.grounded_sam_worker import validate_worker_host


def loaded_models() -> LoadedModels:
    return LoadedModels(value={"synthetic": True}, device="cpu", dtype="float32", dependency_versions={})


class ModelLifecycleTests(unittest.TestCase):
    def test_lazy_load_and_model_reuse(self) -> None:
        calls = []

        def loader():
            calls.append("load")
            return loaded_models()

        registry = ModelRegistry(loader)
        self.assertEqual(registry.state, "unloaded")
        self.assertEqual(calls, [])
        first, first_cache_hit = registry.get_or_load()
        second, second_cache_hit = registry.get_or_load()
        self.assertIs(first, second)
        self.assertFalse(first_cache_hit)
        self.assertTrue(second_cache_hit)
        self.assertEqual(calls, ["load"])
        self.assertEqual(registry.state, "ready")

    def test_failed_load_is_visible_and_retryable(self) -> None:
        calls = []

        def loader():
            calls.append("load")
            if len(calls) == 1:
                raise ModelLoadFailure("model_load_failed", "synthetic failure")
            return loaded_models()

        registry = ModelRegistry(loader)
        with self.assertRaises(ModelLoadFailure):
            registry.get_or_load()
        self.assertEqual(registry.state, "load_failed")
        self.assertIn("synthetic failure", registry.health()["last_load_error"])
        model, cache_hit = registry.get_or_load()
        self.assertIsNotNone(model)
        self.assertFalse(cache_hit)
        self.assertEqual(registry.load_attempts, 2)
        self.assertEqual(registry.state, "ready")

    def test_dependency_or_model_unavailable_state(self) -> None:
        for reason in ("dependency_missing", "model_unavailable"):
            with self.subTest(reason=reason):
                registry = ModelRegistry(lambda: (_ for _ in ()).throw(ModelLoadFailure(reason, "missing")))
                with self.assertRaises(ModelLoadFailure):
                    registry.get_or_load()
                self.assertEqual(registry.state, "unavailable")


class WorkerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.image = self.root / "sample_mat_rectified.jpg"
        self.image.write_bytes(b"worker-preflight-only")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _worker(self, loader, analyzer=lambda **_kwargs: {"ok": True, "backend": "grounded_sam"}):
        return GroundedSamWorker(
            registry=ModelRegistry(loader), analyzer=analyzer,
            allowed_input_root=self.root, artifact_root=self.root / "artifacts",
            dependency_probe=lambda: {"available": True, "versions": {"torch": "mock"}},
        )

    def _payload(self):
        return {"image_path": str(self.image), "prompt": "small gear"}

    def test_analyze_triggers_lazy_load_and_reports_cache_hit(self) -> None:
        calls = []
        timings = []

        def analyzer(**kwargs):
            timings.append(kwargs["model_load_timing_ms"])
            return {"ok": True, "backend": "grounded_sam"}

        worker = self._worker(lambda: calls.append("load") or loaded_models(), analyzer)
        self.assertTrue(worker.analyze(self._payload())["ok"])
        self.assertTrue(worker.analyze(self._payload())["ok"])
        self.assertEqual(calls, ["load"])
        self.assertFalse(timings[0]["cache_hit"])
        self.assertTrue(timings[1]["cache_hit"])

    def test_bad_input_does_not_load_models(self) -> None:
        calls = []
        worker = self._worker(lambda: calls.append("load") or loaded_models())
        self.assertEqual(worker.analyze({"prompt": "gear"})["failure_reason"], "source_image_missing")
        self.assertEqual(worker.analyze({"image_path": str(self.image), "prompt": " "})["failure_reason"], "invalid_prompt")
        self.assertEqual(
            worker.analyze({"image_path": str(self.image), "prompt": "x" * 257})["failure_reason"],
            "invalid_prompt",
        )
        self.assertEqual(calls, [])

    def test_single_request_busy_behavior(self) -> None:
        worker = self._worker(loaded_models)
        self.assertTrue(worker.registry.acquire_request())
        try:
            result = worker.analyze(self._payload())
        finally:
            worker.registry.release_request()
        self.assertEqual(result["failure_reason"], "worker_busy")

    def test_health_does_not_load_models(self) -> None:
        calls = []
        worker = self._worker(lambda: calls.append("load") or loaded_models())
        health = worker.health()
        self.assertEqual(calls, [])
        self.assertEqual(health["model_state"], "unloaded")
        self.assertTrue(health["dependencies_available"])
        self.assertFalse(health["busy"])

    def test_load_failure_response_is_retryable(self) -> None:
        worker = self._worker(lambda: (_ for _ in ()).throw(ModelLoadFailure("model_unavailable", "not cached")))
        result = worker.analyze(self._payload())
        self.assertEqual(result["failure_reason"], "model_unavailable")
        self.assertTrue(result["diagnostics"]["retryable"])

    def test_worker_script_resolves_project_imports(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(project_root / "tools" / "grounded_sam_worker.py"), "--help"],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Grounded SAM", completed.stdout)

    def test_worker_host_accepts_only_loopback(self) -> None:
        for host in ("localhost", "127.0.0.1", "127.2.3.4", "::1"):
            with self.subTest(host=host):
                self.assertEqual(validate_worker_host(host), host)
        for host in ("0.0.0.0", "192.168.1.5", "example.com", "localhost.example.com"):
            with self.subTest(host=host), self.assertRaises(argparse.ArgumentTypeError):
                validate_worker_host(host)


class DetectorAndMaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guardrails = DetectorGuardrails()

    def _candidate(self, box, confidence):
        return evaluate_candidate(
            box=box, confidence=confidence, label="gear", prompt="gear",
            image_width=1000, image_height=800, guardrails=self.guardrails,
        )

    def test_no_acceptable_detector_candidate(self) -> None:
        rejected = self._candidate((0, 0, 999, 799), 0.99)
        selection = select_candidate([rejected], guardrails=self.guardrails)
        self.assertIsNone(selection.selected)
        self.assertFalse(selection.ambiguous)
        self.assertIn("area_too_large", rejected.rejection_reasons)

    def test_ambiguous_detector_candidates(self) -> None:
        first = self._candidate((100, 100, 250, 250), 0.80)
        second = self._candidate((500, 400, 650, 550), 0.79)
        selection = select_candidate([first, second], guardrails=self.guardrails)
        self.assertTrue(selection.ambiguous)
        self.assertIsNone(selection.selected)

    def test_invalid_and_empty_masks(self) -> None:
        with self.assertRaises(ValueError):
            validate_and_clean_mask(np.zeros((30, 40), dtype=np.uint8), expected_shape=(30, 40))
        with self.assertRaises(ValueError):
            validate_and_clean_mask(np.ones((30, 40), dtype=np.uint8), expected_shape=(30, 40))
        with self.assertRaises(ValueError):
            validate_and_clean_mask(np.ones((10, 10), dtype=np.uint8), expected_shape=(30, 40))

    def test_artifact_failure_reports_only_successful_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw = np.zeros((20, 20), dtype=np.uint8)
            raw[5:15, 5:15] = 255
            cleanup = validate_and_clean_mask(raw, expected_shape=(20, 20))
            image = Image.new("RGB", (20, 20), "white")
            with patch("cv2.imwrite", return_value=False):
                artifacts, error = _write_artifacts(image, cleanup, Path(directory), "synthetic")
            self.assertEqual(artifacts, {})
            self.assertIn("Could not write", error)


class ProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.image = self.root / "saved_mat_rectified.jpg"
        self.sidecar = self.image.with_suffix(".metadata.json")
        self.metadata = {
            "calibration_profile_id": "logitech_c920_overhead_scan_mat",
            "logical_camera_id": "logitech_c920",
            "camera_role": "workbench",
            "calibration_status": "calibrated",
            "mode_status": "requested",
            "geometry_version": "scan_mat_geometry_v1",
            "homography_version": "opencv_perspective_outer_boundary_v1",
            "mode_mismatches": [],
            "requested_mode": {"pixel_format": "MJPG", "width": 1920, "height": 1080, "fps": 30.0},
            "negotiated_mode": {"pixel_format": "MJPG", "width": 1920, "height": 1080, "fps": 30.0},
            "source_image_dimensions": {"width": 1920, "height": 1080},
            "rectified_output_dimensions": {"width": 1440, "height": 1080},
            "physical_mat": {"width_mm": 609.6, "height_mm": 457.2, "boundary": "physical_outer_boundary"},
            "stable_camera_identity": {
                "bus_info": "usb-test", "by_id_prefix": "usb-Logitech_C920",
                "by_path_prefix": "pci-test", "card_name": "HD Pro Webcam C920",
            },
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write(self):
        self.sidecar.write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_valid_c920_provenance(self) -> None:
        self._write()
        metadata, calibration = load_validated_provenance(
            self.image, self.sidecar, image_width=1440, image_height=1080
        )
        self.assertEqual(metadata["logical_camera_id"], "logitech_c920")
        self.assertTrue(calibration["ready"])
        self.assertAlmostEqual(calibration["pixels_per_mm_x"], 1440 / 609.6)

    def test_valid_c920_provenance_accepts_json_float_roundoff(self) -> None:
        self.metadata["physical_mat"]["width_mm"] = 609.5999999999999
        self._write()
        metadata, calibration = load_validated_provenance(
            self.image, self.sidecar, image_width=1440, image_height=1080
        )
        self.assertEqual(metadata["physical_mat"]["width_mm"], 609.5999999999999)
        self.assertTrue(calibration["ready"])

    def test_numeric_provenance_rejects_boolean_values(self) -> None:
        self.metadata["physical_mat"]["width_mm"] = True
        self._write()
        with self.assertRaises(ProvenanceMismatch):
            load_validated_provenance(
                self.image, self.sidecar, image_width=1440, image_height=1080
            )

    def test_calibration_and_provenance_mismatch(self) -> None:
        self.metadata["logical_camera_id"] = "insta360_link"
        self._write()
        with self.assertRaises(ProvenanceMismatch):
            load_validated_provenance(self.image, self.sidecar, image_width=1440, image_height=1080)

    def test_dependency_probe_is_metadata_only(self) -> None:
        with patch("importlib.metadata.version", return_value="test") as version:
            result = dependency_probe()
        self.assertTrue(result["available"])
        self.assertEqual(version.call_count, 5)


if __name__ == "__main__":
    unittest.main()
