from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from skills import camera_skill


def encoded_fourcc(value: str) -> float:
    return float(cv2.VideoWriter_fourcc(*value))


class FakeCapture:
    def __init__(
        self,
        *,
        opened: bool = True,
        pixel_format: str = "MJPG",
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
    ) -> None:
        self.opened = opened
        self.pixel_format = pixel_format
        self.width = width
        self.height = height
        self.fps = fps
        self.set_calls: list[tuple[int, float]] = []
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def set(self, property_id: int, value: float) -> bool:
        self.set_calls.append((property_id, value))
        return True

    def get(self, property_id: int) -> float:
        values = {
            cv2.CAP_PROP_FOURCC: encoded_fourcc(self.pixel_format),
            cv2.CAP_PROP_FRAME_WIDTH: float(self.width),
            cv2.CAP_PROP_FRAME_HEIGHT: float(self.height),
            cv2.CAP_PROP_FPS: self.fps,
        }
        return values[property_id]

    def read(self):
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        return True, frame

    def release(self) -> None:
        self.released = True


def resolved_c920(device_path: str) -> dict:
    return {
        "role": "workbench",
        "resolved_device_path": device_path,
        "display_name": "Logitech HD Pro Webcam C920",
        "preferred_pixel_format": "MJPG",
        "preferred_resolution": {
            "width": 1920,
            "height": 1080,
        },
    }


class CameraCaptureModeTests(unittest.TestCase):
    def _capture_with(
        self,
        capture: FakeCapture,
    ) -> tuple[dict, MagicMock, str]:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            device_path = temp_path / "stable-c920-capture"
            device_path.touch()
            capture_dir = temp_path / "captures"

            def write_image(path: str, _frame: np.ndarray) -> bool:
                Path(path).write_bytes(b"mock jpeg")
                return True

            with (
                patch(
                    "skills.camera_skill.resolve_camera",
                    return_value=resolved_c920(str(device_path)),
                ),
                patch("skills.camera_skill.PROJECT_ROOT", temp_path),
                patch("skills.camera_skill.CAPTURE_DIR", capture_dir),
                patch(
                    "skills.camera_skill.cv2.VideoCapture",
                    return_value=capture,
                ) as video_capture,
                patch(
                    "skills.camera_skill.cv2.imwrite",
                    side_effect=write_image,
                ),
            ):
                result = camera_skill.capture_snapshot(role="workbench")
        return result, video_capture, str(device_path)

    def test_requests_mjpg_before_width_and_height(self) -> None:
        capture = FakeCapture()

        result, video_capture, device_path = self._capture_with(capture)

        video_capture.assert_called_once_with(
            device_path,
            cv2.CAP_V4L2,
        )
        self.assertEqual(
            [property_id for property_id, _value in capture.set_calls],
            [
                cv2.CAP_PROP_FOURCC,
                cv2.CAP_PROP_FRAME_WIDTH,
                cv2.CAP_PROP_FRAME_HEIGHT,
            ],
        )
        self.assertEqual(
            capture.set_calls[0][1],
            cv2.VideoWriter_fourcc(*"MJPG"),
        )
        self.assertTrue(capture.released)
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode_status"], "requested")
        self.assertEqual(result["negotiated_mode"]["pixel_format"], "MJPG")
        self.assertEqual(result["negotiated_mode"]["width"], 1920)
        self.assertEqual(result["negotiated_mode"]["height"], 1080)
        self.assertEqual(result["negotiated_mode"]["fps"], 30.0)

    def test_reports_structured_fallback_mode(self) -> None:
        capture = FakeCapture(
            pixel_format="YUYV",
            width=640,
            height=480,
        )

        result, _video_capture, _device_path = self._capture_with(capture)

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode_status"], "fallback")
        self.assertEqual(result["requested_mode"]["pixel_format"], "MJPG")
        self.assertEqual(result["requested_mode"]["width"], 1920)
        self.assertEqual(result["negotiated_mode"]["pixel_format"], "YUYV")
        self.assertEqual(result["negotiated_mode"]["width"], 640)
        self.assertEqual(result["negotiated_mode"]["frame_width"], 640)
        self.assertTrue(result["mode_mismatches"])
        self.assertIn("fallback", result["warning"])

    def test_open_failure_identifies_v4l2_and_stable_node(self) -> None:
        capture = FakeCapture(opened=False)

        result, video_capture, device_path = self._capture_with(capture)

        video_capture.assert_called_once_with(
            device_path,
            cv2.CAP_V4L2,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["device"], device_path)
        self.assertEqual(result["backend"], "opencv_v4l2")
        self.assertIn("stable discovered capture node", result["error"])
        self.assertTrue(capture.released)


if __name__ == "__main__":
    unittest.main()
