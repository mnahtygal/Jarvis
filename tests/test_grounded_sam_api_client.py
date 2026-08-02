import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import urlsplit

import api
import skills.grounded_sam_client as grounded_client
from PIL import Image
from core.grounded_sam_contract import (
    FAILURE_HTTP_STATUS,
    grounded_sam_failure,
    grounded_sam_http_status,
    grounded_sam_result,
)
from skills.grounded_sam_client import (
    GroundedSamClientConfig,
    SavedImageIdError,
    analyze_saved_image_with_grounded_sam,
    get_grounded_sam_health,
    list_grounded_sam_saved_images,
    load_grounded_sam_config,
    normalize_grounded_sam_prompt,
    resolve_grounded_sam_image_id,
    validate_grounded_sam_provenance,
    validate_grounded_sam_worker_url,
    validate_grounded_sam_source,
)


def valid_c920_metadata(*, created_at: str | None = None) -> dict:
    metadata = {
        "calibration_profile_id": "logitech_c920_overhead_scan_mat",
        "logical_camera_id": "logitech_c920",
        "camera_role": "workbench",
        "calibration_status": "calibrated",
        "calibration_confidence": 0.95,
        "mode_status": "requested",
        "geometry_version": "scan_mat_geometry_v1",
        "homography_version": "opencv_perspective_outer_boundary_v1",
        "mode_mismatches": [],
        "requested_mode": {
            "pixel_format": "MJPG", "width": 1920, "height": 1080, "fps": 30.0,
        },
        "negotiated_mode": {
            "pixel_format": "MJPG", "width": 1920, "height": 1080, "fps": 30.0,
        },
        "source_image_dimensions": {"width": 1920, "height": 1080},
        "rectified_output_dimensions": {"width": 1440, "height": 1080},
        "physical_mat": {
            "width_mm": 609.6,
            "height_mm": 457.2,
            "boundary": "physical_outer_boundary",
        },
        "stable_camera_identity": {
            "bus_info": "usb-test",
            "by_id_prefix": "usb-Logitech_C920",
            "by_path_prefix": "pci-test",
            "card_name": "HD Pro Webcam C920",
        },
    }
    if created_at is not None:
        metadata["created_at"] = created_at
    return metadata


def write_saved_image(root: Path, name: str, metadata: dict) -> Path:
    image_path = root / name
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1440, 1080), "white").save(image_path)
    image_path.with_suffix(".metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    return image_path


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

    def test_inventory_endpoint_returns_only_browser_safe_fields(self) -> None:
        images = [{"image_id": "gsi_" + "a" * 64, "display_name": "saved"}]
        with patch.object(api, "list_grounded_sam_saved_images", return_value=images):
            response = self.client.get("/api/vision/grounded-sam/saved-images")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["images"], images)
        self.assertNotIn("path", json.dumps(response.get_json()))

    def test_opaque_id_analysis_redacts_paths_and_translates_nested_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mat_root = Path(directory) / "mat_analysis"
            artifact_root = mat_root / "grounded_sam"
            artifact_root.mkdir(parents=True)
            raw_mask = artifact_root / "raw.png"
            overlay = artifact_root / "overlay.png"
            raw_mask.write_bytes(b"raw")
            overlay.write_bytes(b"overlay")
            source = mat_root / "saved_mat_rectified.jpg"
            source.write_bytes(b"source")
            result = grounded_sam_result(
                ok=True,
                status="ready",
                source_image={"path": str(source), "provenance_path": str(source) + ".json"},
                calibration={"provenance_path": str(source) + ".json"},
                artifacts={
                    "raw_mask_path": str(raw_mask),
                    "cleaned_mask_path": str(artifact_root / "missing.png"),
                    "diagnostic_overlay_path": str(overlay),
                },
            )
            image_id = "gsi_" + "1" * 64
            with patch.object(api, "MAT_ANALYSIS_DIR", mat_root), patch.object(
                api, "resolve_grounded_sam_image_id", return_value=source
            ), patch.object(
                api, "analyze_saved_image_with_grounded_sam", return_value=result
            ) as analyze, patch.object(api, "measure_object_bbox_from_image") as opencv:
                response = self.client.post(
                    "/api/measurement/analyze",
                    json={"backend": "grounded_sam", "image_id": image_id, "prompt": "gear"},
                )
                raw_url = response.get_json()["artifacts"]["raw_mask_url"]
                served = self.client.get(urlsplit(raw_url).path)
                self.assertEqual(served.status_code, 200)
                self.assertEqual(served.data, b"raw")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        encoded = json.dumps(payload)
        self.assertNotIn(directory, encoded)
        self.assertNotIn("_path", encoded)
        self.assertEqual(payload["source_image"]["image_id"], image_id)
        self.assertIn("/grounded_sam/raw.png", payload["artifacts"]["raw_mask_url"])
        self.assertIn("/grounded_sam/overlay.png", payload["artifacts"]["diagnostic_overlay_url"])
        self.assertNotIn("cleaned_mask_url", payload["artifacts"])
        analyze.assert_called_once_with(str(source), "gear")
        opencv.assert_not_called()

    def test_outside_artifact_is_not_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mat_root = Path(directory) / "mat_analysis"
            mat_root.mkdir()
            outside = Path(directory) / "outside.png"
            outside.write_bytes(b"outside")
            result = grounded_sam_result(
                ok=False,
                status="artifact_write_failed",
                failure_reason="artifact_write_failed",
                error=f"Could not write {outside}",
                artifacts={"raw_mask_path": str(outside)},
            )
            with patch.object(api, "MAT_ANALYSIS_DIR", mat_root):
                with api.app.test_request_context():
                    payload = api._grounded_sam_browser_response(result)
        self.assertNotIn("raw_mask_url", payload["artifacts"])
        self.assertNotIn("raw_mask_path", payload["artifacts"])
        self.assertNotIn(directory, json.dumps(payload))

    def test_opaque_no_object_and_ambiguity_never_fall_back(self) -> None:
        image_id = "gsi_" + "2" * 64
        for reason in ("no_detector_candidate", "ambiguous_detector_candidates"):
            with self.subTest(reason=reason), patch.object(
                api, "resolve_grounded_sam_image_id", return_value=Path("/safe.jpg")
            ), patch.object(
                api,
                "analyze_saved_image_with_grounded_sam",
                return_value=grounded_sam_failure(reason, "selection failed"),
            ), patch.object(api, "measure_object_bbox_from_image") as opencv:
                response = self.client.post(
                    "/api/measurement/analyze",
                    json={"backend": "grounded_sam", "image_id": image_id, "prompt": "gear"},
                )
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()["failure_reason"], reason)
            opencv.assert_not_called()

    def test_malformed_and_unknown_opaque_ids_are_structured(self) -> None:
        cases = (
            SavedImageIdError("source_image_unreadable", "malformed"),
            SavedImageIdError("source_image_missing", "unknown or stale"),
        )
        for error in cases:
            with self.subTest(reason=error.failure_reason), patch.object(
                api, "resolve_grounded_sam_image_id", side_effect=error
            ), patch.object(api, "measure_object_bbox_from_image") as opencv:
                response = self.client.post(
                    "/api/measurement/analyze",
                    json={"backend": "grounded_sam", "image_id": "bad", "prompt": "gear"},
                )
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()["failure_reason"], error.failure_reason)
            opencv.assert_not_called()


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
             patch("skills.grounded_sam_client.validate_grounded_sam_provenance", return_value=calibration), \
             patch("skills.grounded_sam_client._post_json", side_effect=side_effect):
            return analyze_saved_image_with_grounded_sam(str(source), "gear", config=self.config)

    def test_worker_unavailable_and_timeout(self) -> None:
        unavailable = self._transport_result(URLError("refused"))
        self.assertEqual(unavailable["failure_reason"], "worker_unavailable")
        timeout = self._transport_result(TimeoutError())
        self.assertEqual(timeout["failure_reason"], "request_timeout")

    def test_saved_image_provenance_does_not_use_active_camera_state(self) -> None:
        source = write_saved_image(
            self.root, "independent_mat_rectified.jpg", valid_c920_metadata()
        )
        with patch("core.measurement.get_active_calibration") as active_calibration:
            calibration = validate_grounded_sam_provenance(source)
        self.assertTrue(calibration["ready"])
        self.assertEqual(calibration["logical_camera_id"], "logitech_c920")
        active_calibration.assert_not_called()

    def test_disabled_health_does_not_contact_worker(self) -> None:
        disabled = GroundedSamClientConfig(**{**self.config.__dict__, "enabled": False})
        with patch("skills.grounded_sam_client.urlopen") as request:
            health = get_grounded_sam_health(config=disabled)
        self.assertFalse(health["enabled"])
        self.assertEqual(health["model_state"], "unavailable")
        request.assert_not_called()

    def test_loopback_worker_urls_only(self) -> None:
        accepted = (
            "http://127.0.0.1:8092",
            "http://127.1.2.3:8092/",
            "http://localhost:8092",
            "http://[::1]:8092",
        )
        for value in accepted:
            with self.subTest(value=value):
                self.assertTrue(validate_grounded_sam_worker_url(value).startswith("http://"))
        rejected = (
            "https://127.0.0.1:8092",
            "http://0.0.0.0:8092",
            "http://192.168.1.5:8092",
            "http://example.com:8092",
            "http://localhost.example.com:8092",
            "http://user@localhost:8092",
            "http://localhost:8092/v1",
            "file:///tmp/worker",
        )
        for value in rejected:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_grounded_sam_worker_url(value)

    def test_config_loader_rejects_non_loopback_worker_url(self) -> None:
        config_path = self.root / "vision_backends.json"
        config_path.write_text(json.dumps({
            "backends": {
                "grounded_sam": {
                    "enabled": False,
                    "worker_url": "http://192.168.1.5:8092",
                    "allowed_input_root": str(self.root),
                    "artifact_root": str(self.root / "artifacts"),
                }
            }
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_grounded_sam_config(config_path)

    def test_non_loopback_direct_config_never_contacts_worker(self) -> None:
        unsafe = GroundedSamClientConfig(
            **{**self.config.__dict__, "worker_url": "http://192.168.1.5:8092"}
        )
        with patch("skills.grounded_sam_client.urlopen") as request:
            health = get_grounded_sam_health(config=unsafe)
        self.assertEqual(health["model_state"], "unavailable")
        self.assertIn("loopback", health["last_load_error"])
        request.assert_not_called()


class GroundedSamSavedImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "mat_analysis"
        self.root.mkdir()
        self.config = GroundedSamClientConfig(
            enabled=False,
            worker_url="http://127.0.0.1:8092",
            request_timeout_seconds=1.0,
            prompt_max_length=256,
            allowed_input_root=self.root,
            artifact_root=self.root / "grounded_sam",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_inventory_filters_invalid_entries_and_sorts_newest_first(self) -> None:
        old = write_saved_image(
            self.root,
            "old_mat_rectified.jpg",
            valid_c920_metadata(created_at="2026-01-01T00:00:00+00:00"),
        )
        new = write_saved_image(
            self.root,
            "nested/new_mat_rectified.jpg",
            valid_c920_metadata(created_at="2026-02-01T00:00:00Z"),
        )
        write_saved_image(
            self.root, "insta_mat_rectified.jpg", {
                **valid_c920_metadata(), "logical_camera_id": "insta360_link",
            }
        )
        broken = self.root / "broken_mat_rectified.jpg"
        Image.new("RGB", (1440, 1080), "white").save(broken)
        broken.with_suffix(".metadata.json").write_text("{broken", encoding="utf-8")
        Image.new("RGB", (1440, 1080), "white").save(
            self.root / "missing_mat_rectified.jpg"
        )
        inventory = list_grounded_sam_saved_images(config=self.config)
        self.assertEqual(len(inventory), 2)
        self.assertEqual(
            [entry["captured_at"] for entry in inventory],
            ["2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z"],
        )
        self.assertTrue(all(entry["provenance_state"] == "validated" for entry in inventory))
        self.assertNotIn(old.name, json.dumps(inventory))
        self.assertNotIn(new.name, json.dumps(inventory))
        self.assertNotIn(str(self.root), json.dumps(inventory))

    def test_invalid_timestamp_uses_documented_mtime_fallback(self) -> None:
        image = write_saved_image(
            self.root,
            "fallback_mat_rectified.jpg",
            valid_c920_metadata(created_at="not-a-time"),
        )
        timestamp = datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp()
        image.touch()
        os.utime(image, (timestamp, timestamp))
        inventory = list_grounded_sam_saved_images(config=self.config)
        self.assertEqual(inventory[0]["timestamp_source"], "filesystem_mtime")
        self.assertEqual(inventory[0]["captured_at"], "2026-03-01T00:00:00Z")

    def test_out_of_boundary_symlink_is_excluded(self) -> None:
        outside_root = Path(self.temporary.name) / "outside"
        outside_root.mkdir()
        outside = write_saved_image(
            outside_root, "outside_mat_rectified.jpg", valid_c920_metadata()
        )
        (self.root / "linked_mat_rectified.jpg").symlink_to(outside)
        (self.root / "linked_mat_rectified.metadata.json").symlink_to(
            outside.with_suffix(".metadata.json")
        )
        self.assertEqual(list_grounded_sam_saved_images(config=self.config), [])

    def test_opaque_id_resolves_and_stale_or_forged_ids_fail(self) -> None:
        image = write_saved_image(
            self.root, "saved_mat_rectified.jpg", valid_c920_metadata()
        )
        image_id = list_grounded_sam_saved_images(config=self.config)[0]["image_id"]
        self.assertEqual(resolve_grounded_sam_image_id(image_id, config=self.config), image)
        metadata_path = image.with_suffix(".metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["created_at"] = "2026-04-01T00:00:00Z"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaises(SavedImageIdError) as stale:
            resolve_grounded_sam_image_id(image_id, config=self.config)
        self.assertEqual(stale.exception.failure_reason, "source_image_missing")
        with self.assertRaises(SavedImageIdError):
            resolve_grounded_sam_image_id("gsi_" + "f" * 64, config=self.config)
        with self.assertRaises(SavedImageIdError) as malformed:
            resolve_grounded_sam_image_id("../../etc/passwd", config=self.config)
        self.assertEqual(malformed.exception.failure_reason, "source_image_unreadable")

    def test_opaque_id_collision_is_rejected_as_ambiguous(self) -> None:
        write_saved_image(
            self.root, "first_mat_rectified.jpg", valid_c920_metadata()
        )
        write_saved_image(
            self.root, "second_mat_rectified.jpg", valid_c920_metadata()
        )
        colliding_id = "gsi_" + "c" * 64
        with patch.object(grounded_client, "_saved_image_id", return_value=colliding_id):
            with self.assertRaises(SavedImageIdError) as ambiguous:
                resolve_grounded_sam_image_id(colliding_id, config=self.config)
        self.assertEqual(ambiguous.exception.failure_reason, "source_image_unreadable")
        self.assertIn("ambiguous", str(ambiguous.exception))


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
