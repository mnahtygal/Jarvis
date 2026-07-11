from __future__ import annotations

import unittest
from unittest.mock import patch

from core import microphone
from core.router import _try_camera_role_command


SAMSON_SOURCE = {
    "id": "42",
    "name": "alsa_input.usb-Samson_Technologies_Samson_Q2U_Microphone-00.iec958-stereo",
    "description": "Samson Q2U Microphone",
}
CAMERA_SOURCE = {
    "id": "43",
    "name": "alsa_input.usb-046d_HD_Pro_Webcam_C920.analog-stereo",
    "description": "Logitech C920 microphone",
}
FALLBACK_SOURCE = {
    "id": "44",
    "name": "alsa_input.pci-0000_00_1f.3.analog-stereo",
    "description": "Built-in audio",
}


class MicrophoneAndCameraVoiceTests(unittest.TestCase):
    def test_microphone_resolution_prefers_samson(self) -> None:
        source = microphone.resolve_preferred_microphone([CAMERA_SOURCE, SAMSON_SOURCE])
        self.assertEqual(source, SAMSON_SOURCE)

    def test_microphone_fallback_avoids_camera_microphones(self) -> None:
        source = microphone.resolve_fallback_microphone([CAMERA_SOURCE, FALLBACK_SOURCE])
        self.assertEqual(source, FALLBACK_SOURCE)

    def test_microphone_status_uses_samson_when_available(self) -> None:
        with (
            patch("core.microphone.list_audio_sources", return_value=[CAMERA_SOURCE, SAMSON_SOURCE]),
            patch.dict("core.microphone.os.environ", {}, clear=True),
        ):
            status = microphone.get_microphone_status()

        self.assertTrue(status["available"])
        self.assertTrue(status["using_preferred"])
        self.assertEqual(status["resolved_microphone"], SAMSON_SOURCE["name"])

    def test_voice_switch_to_workbench_camera(self) -> None:
        status = {
            "active_role": "workbench",
            "active_camera": {"available": True, "display_name": "Logitech HD Pro Webcam C920"},
        }
        with patch("core.router.set_active_camera_role", return_value=status):
            response = _try_camera_role_command("switch to workbench camera")

        self.assertEqual(response, "Workbench camera selected.")

    def test_voice_switch_to_face_camera(self) -> None:
        status = {
            "active_role": "face",
            "active_camera": {"available": True, "display_name": "Insta360 Link"},
        }
        with patch("core.router.set_active_camera_role", return_value=status):
            response = _try_camera_role_command("look at me")

        self.assertEqual(response, "Face camera selected.")

    def test_voice_reports_active_camera(self) -> None:
        status = {
            "active_role": "workbench",
            "active_camera": {"available": True, "display_name": "Logitech HD Pro Webcam C920"},
        }
        with patch("core.router.get_camera_roles_status", return_value=status):
            response = _try_camera_role_command("what camera are you using")

        self.assertEqual(response, "The workbench camera is active.")


if __name__ == "__main__":
    unittest.main()
