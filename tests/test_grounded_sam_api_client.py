import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import api
from core.grounded_sam_contract import (
    FAILURE_HTTP_STATUS,
    grounded_sam_failure,
    grounded_sam_http_status,
    grounded_sam_result,
)
from skills.grounded_sam_client import (
    GroundedSamClientConfig,
    analyze_saved_image_with_grounded_sam,
    get_grounded_sam_health,
    normalize_grounded_sam_prompt,
    validate_grounded_sam_source,
)


class GroundedSamApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = api.app.test_client()

    def _opencv_result(self):
        return {"ok": True, "status": "ready", "measurement": {"unit": "mm"}}

    def test_omitted_backend_retains_opencv_path(self) -> None:
        with patch.object(api, "_resolve_measurement_image_path", return_value=Path("/safe.jpg")), \
             patch.object(api, "measure_object_bbox_from_image", return_value=self._opencv_result()) as opencv, \
             patch.object(api, "analyze_saved_image_with_grounded_sam") as grounded:
            response = self.client.post("/api/measurement/analyze", json={"image_path": "safe.jpg"})
        self.assertEqual(response.status_code, 200)
        opencv.assert_called_once()
        grounded.assert_not_called()

    def test_explicit_opencv_retains_opencv_path(self) -> None:
        with patch.object(api, "_resolve_measurement_image_path", return_value=Path("/safe.jpg")), \
             patch.object(api, "measure_object_bbox_from_image", return_value=self._opencv_result()) as opencv, \
             patch.object(api, "analyze_saved_image_with_grounded_sam") as grounded:
            response = self.client.post(
                "/api/measurement/analyze",
                json={"backend": "opencv", "image_path": "safe.jpg"},
            )
        self.assertEqual(response.status_code, 200)
        opencv.assert_called_once()
        grounded.assert_not_called()

    def test_explicit_grounded_sam_never_falls_back(self) -> None:
        result = grounded_sam_failure("backend_disabled", "disabled")
        with patch.object(api, "analyze_saved_image_with_grounded_sam", return_value=result) as grounded, \
             patch.object(api, "measure_object_bbox_from_image") as opencv:
            response = self.client.post(
                "/api/measurement/analyze",
                json={"backend": "grounded_sam", "image_path": "saved.jpg", "prompt": "gear"},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["failure_reason"], "backend_disabled")
        grounded.assert_called_once_with("saved.jpg", "gear")
        opencv.assert_not_called()

    def test_invalid_backend_is_structured(self) -> None:
        response = self.client.post(
            "/api/measurement/analyze", json={"backend": "magic", "image_path": "x"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["failure_reason"], "invalid_backend")

    def test_health_route_does_not_analyze(self) -> None:
        health = {"backend": "grounded_sam", "model_state": "unloaded"}
        with patch.object(api, "get_grounded_sam_health", return_value=health), \
             patch.object(api, "analyze_saved_image_with_grounded_sam") as analyze:
            response = self.client.get("/api/status/grounded-sam")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["model_state"], "unloaded")
        analyze.assert_not_called()


class GroundedSamClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = GroundedSamClientConfig(
            enabled=True,
            worker_url="http://127.0.0.1:8092",
            request_timeout_seconds=0.25,
            prompt_max_length=12,
            allowed_input_root=self.root,
            artifact_root=self.root / "artifacts",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_prompt_normalization_and_boundaries(self) -> None:
        self.assertEqual(normalize_grounded_sam_prompt("  small\n gear ", maximum_length=20), "small gear")
        for value in (None, "", "   "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_grounded_sam_prompt(value, maximum_length=20)
        with self.assertRaises(ValueError):
            normalize_grounded_sam_prompt("123456", maximum_length=5)
        with self.assertRaises(ValueError):
            normalize_grounded_sam_prompt("gear\x00part", maximum_length=20)

    def test_missing_and_unreadable_saved_images(self) -> None:
        missing = analyze_saved_image_with_grounded_sam(
            str(self.root / "missing_mat_rectified.jpg"), "gear", config=self.config
        )
        self.assertEqual(missing["failure_reason"], "source_image_missing")
        broken = self.root / "broken_mat_rectified.jpg"
        broken.write_bytes(b"not-an-image")
        unreadable = analyze_saved_image_with_grounded_sam(str(broken), "gear", config=self.config)
        self.assertEqual(unreadable["failure_reason"], "source_image_unreadable")

    def test_unsafe_and_unsupported_paths_are_rejected(self) -> None:
        outside = Path(self.temporary.name).parent / "outside_mat_rectified.jpg"
        with self.assertRaises(ValueError):
            validate_grounded_sam_source(str(outside), allowed_root=self.root)
        unsupported = self.root / "snapshot.png"
        unsupported.write_bytes(b"x")
        with self.assertRaises(ValueError):
            validate_grounded_sam_source(str(unsupported), allowed_root=self.root)

    def _transport_result(self, side_effect):
        source = self.root / "sample_mat_rectified.jpg"
        source.write_bytes(b"mocked")
        calibration = {"ready": True, "provenance_path": str(source.with_suffix(".metadata.json"))}
        with patch("skills.grounded_sam_client.validate_grounded_sam_source", return_value=source), \
             patch("core.measurement.get_active_calibration", return_value=calibration), \
             patch("skills.grounded_sam_client._post_json", side_effect=side_effect):
            return analyze_saved_image_with_grounded_sam(str(source), "gear", config=self.config)

    def test_worker_unavailable_and_timeout(self) -> None:
        unavailable = self._transport_result(URLError("refused"))
        self.assertEqual(unavailable["failure_reason"], "worker_unavailable")
        timeout = self._transport_result(TimeoutError())
        self.assertEqual(timeout["failure_reason"], "request_timeout")

    def test_disabled_health_does_not_contact_worker(self) -> None:
        disabled = GroundedSamClientConfig(**{**self.config.__dict__, "enabled": False})
        with patch("skills.grounded_sam_client.urlopen") as request:
            health = get_grounded_sam_health(config=disabled)
        self.assertFalse(health["enabled"])
        self.assertEqual(health["model_state"], "unavailable")
        request.assert_not_called()


class GroundedSamContractTests(unittest.TestCase):
    def test_http_status_mapping_is_stable(self) -> None:
        for reason, expected in FAILURE_HTTP_STATUS.items():
            with self.subTest(reason=reason):
                self.assertEqual(grounded_sam_http_status(grounded_sam_failure(reason, "x")), expected)

    def test_response_serializes_and_omits_unwritten_artifact_paths(self) -> None:
        result = grounded_sam_result(
            ok=True, status="ready", prompt="gear", diagnostics={"synthetic": True}
        )
        encoded = json.dumps(result)
        self.assertIn('"backend": "grounded_sam"', encoded)
        self.assertEqual(result["artifacts"], {})
        self.assertTrue(result["experimental"])
        self.assertTrue(result["diagnostics"]["synthetic"])

    def test_ordinary_api_import_does_not_import_grounded_sam_worker_stack(self) -> None:
        script = (
            "import json,sys; import api; "
            "print(json.dumps({name: name in sys.modules for name in "
            "['groundingdino','sam2','experiments.grounded_sam_backend.pipeline']}))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script], check=True, capture_output=True, text=True
        )
        self.assertFalse(any(json.loads(completed.stdout.strip()).values()))

    def test_lightweight_client_import_does_not_import_heavy_dependencies(self) -> None:
        script = (
            "import json,sys; import skills.grounded_sam_client; "
            "print(json.dumps({name: name in sys.modules for name in "
            "['torch','transformers','groundingdino','sam2']}))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script], check=True, capture_output=True, text=True
        )
        self.assertFalse(any(json.loads(completed.stdout.strip()).values()))


if __name__ == "__main__":
    unittest.main()
