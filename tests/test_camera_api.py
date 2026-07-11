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

    def test_snapshot_endpoint_accepts_role_body(self) -> None:
        payload = {"ok": False, "role": "workbench", "device": "/dev/video8", "error": "not found"}
        with patch("api.capture_snapshot", return_value=payload) as capture:
            response = self.client.post("/api/camera/snapshot", json={"role": "workbench"})

        self.assertEqual(response.status_code, 503)
        capture.assert_called_once_with(device=None, role="workbench")
        self.assertEqual(response.get_json()["role"], "workbench")


if __name__ == "__main__":
    unittest.main()
