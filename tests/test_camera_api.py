from __future__ import annotations

import unittest
from unittest.mock import patch

from api import app


class CameraApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_get_cameras_endpoint_returns_structured_json(self) -> None:
        payload = {
            "ok": True,
            "active_role": "workbench",
            "active_camera": {"role": "workbench", "available": True},
            "cameras": [],
            "devices": [],
        }
        with patch("api.get_camera_roles_status", return_value=payload):
            response = self.client.get("/api/cameras")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["active_role"], "workbench")

    def test_switch_active_camera_endpoint(self) -> None:
        payload = {
            "ok": True,
            "active_role": "face",
            "active_camera": {"role": "face", "available": True},
            "cameras": [],
            "devices": [],
        }
        with patch("api.set_active_camera_role", return_value=payload):
            response = self.client.post("/api/camera/active", json={"role": "face"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["active_role"], "face")

    def test_get_active_camera_preserves_extended_resolution_fields(self) -> None:
        active_camera = {
            "id": "logitech_c920",
            "role": "workbench",
            "available": True,
            "resolved_device_path": "/dev/video0",
            "matched_device": {"path": "/dev/video0", "interface_type": "capture"},
            "capture_device": "/dev/video0",
            "metadata_device": "/dev/video1",
            "capture_by_id": "/dev/v4l/by-id/c920-video-index0",
            "resolution_method": "by_id",
        }
        payload = {
            "ok": True,
            "active_role": "workbench",
            "active_camera": active_camera,
            "cameras": [active_camera],
            "devices": [],
        }
        with patch("api.get_camera_roles_status", return_value=payload):
            response = self.client.get("/api/camera/active")

        result = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result["active_camera"]["resolved_device_path"], "/dev/video0")
        self.assertEqual(result["active_camera"]["metadata_device"], "/dev/video1")
        self.assertEqual(result["active_camera"]["resolution_method"], "by_id")

    def test_snapshot_endpoint_accepts_role_body(self) -> None:
        payload = {"ok": False, "role": "workbench", "device": "/dev/video8", "error": "not found"}
        with patch("api.capture_snapshot", return_value=payload) as capture:
            response = self.client.post("/api/camera/snapshot", json={"role": "workbench"})

        self.assertEqual(response.status_code, 503)
        capture.assert_called_once_with(device=None, role="workbench")
        self.assertEqual(response.get_json()["role"], "workbench")


if __name__ == "__main__":
    unittest.main()
