from __future__ import annotations

import unittest
from unittest.mock import patch

from core import camera_roles
from skills import camera_skill


V4L2_LIST = """\
Insta360 Link (usb-0000:00:14.0-5):
\t/dev/video4
\t/dev/video5

HD Pro Webcam C920 (usb-0000:00:14.0-6):
\t/dev/video8
\t/dev/video9
"""


class Completed:
    returncode = 0
    stdout = V4L2_LIST
    stderr = ""


class CameraRoleTests(unittest.TestCase):
    def test_camera_discovery_parses_v4l2_devices(self) -> None:
        with patch("core.camera_roles.subprocess.run", return_value=Completed()):
            devices = camera_roles.discover_v4l2_devices()

        self.assertEqual(devices[0]["path"], "/dev/video4")
        self.assertEqual(devices[0]["name"], "Insta360 Link")
        self.assertEqual(devices[2]["path"], "/dev/video8")
        self.assertEqual(devices[2]["name"], "HD Pro Webcam C920")

    def test_role_resolution_survives_device_path_changes(self) -> None:
        config = {
            "active_camera_role": "workbench",
            "cameras": camera_roles.DEFAULT_CAMERA_ROLES,
        }
        with patch("core.camera_roles.subprocess.run", return_value=Completed()):
            status = camera_roles.get_camera_roles_status(config=config)

        workbench = next(camera for camera in status["cameras"] if camera["role"] == "workbench")
        face = next(camera for camera in status["cameras"] if camera["role"] == "face")
        self.assertEqual(workbench["resolved_device_path"], "/dev/video8")
        self.assertEqual(face["resolved_device_path"], "/dev/video4")

    def test_missing_camera_reports_unavailable(self) -> None:
        config = {
            "active_camera_role": "workbench",
            "cameras": camera_roles.DEFAULT_CAMERA_ROLES,
        }
        with patch("core.camera_roles.discover_v4l2_devices", return_value=[]):
            status = camera_roles.get_camera_roles_status(config=config)

        self.assertFalse(any(camera["available"] for camera in status["cameras"]))

    def test_switching_camera_role_persists_active_role(self) -> None:
        config = {
            "active_camera_role": "workbench",
            "cameras": camera_roles.DEFAULT_CAMERA_ROLES,
        }
        saved = {}

        def save_config(data):
            saved.update(data)

        with (
            patch("core.camera_roles.load_camera_config", return_value=config),
            patch("core.camera_roles.save_camera_config", side_effect=save_config),
            patch("core.camera_roles.subprocess.run", return_value=Completed()),
        ):
            status = camera_roles.set_active_camera_role("face")

        self.assertEqual(saved["active_camera_role"], "face")
        self.assertEqual(status["active_role"], "face")

    def test_capture_snapshot_accepts_role_without_hardcoded_device(self) -> None:
        resolved = {
            "role": "workbench",
            "resolved_device_path": "/dev/video8",
            "display_name": "Logitech HD Pro Webcam C920",
        }
        with patch("skills.camera_skill.resolve_camera", return_value=resolved):
            with patch("skills.camera_skill.Path.exists", return_value=False):
                result = camera_skill.capture_snapshot(role="workbench")

        self.assertFalse(result["ok"])
        self.assertEqual(result["device"], "/dev/video8")
        self.assertEqual(result["role"], "workbench")


if __name__ == "__main__":
    unittest.main()
