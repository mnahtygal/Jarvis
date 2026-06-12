# skills/device_status_skill.py

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List


SAMSON_HINTS = ["samson", "q2u"]
CAMERA_HINTS = ["insta360", "camera", "webcam", "video"]
EXPECTED_CAMERA_DEVICE = "/dev/video1"


def _run_command(command: List[str], timeout: float = 3.0) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.stdout or "").strip()
    except Exception as error:
        return f"ERROR: {error}"


def _contains_any(value: str, hints: List[str]) -> bool:
    lower_value = value.lower()
    return any(hint in lower_value for hint in hints)


def _matching_lines(text: str, hints: List[str]) -> List[str]:
    lines = []
    for line in text.splitlines():
        if _contains_any(line, hints):
            lines.append(line.strip())
    return lines


def get_device_dashboard_status() -> Dict[str, Any]:
    lsusb_output = _run_command(["lsusb"])
    pactl_sources_output = _run_command(["pactl", "list", "short", "sources"])
    wpctl_output = _run_command(["wpctl", "status"])
    video_devices = sorted(str(path) for path in Path("/dev").glob("video*"))

    samson_usb_lines = _matching_lines(lsusb_output, SAMSON_HINTS)
    samson_audio_lines = _matching_lines(pactl_sources_output, SAMSON_HINTS)
    samson_wpctl_lines = _matching_lines(wpctl_output, SAMSON_HINTS)

    camera_usb_lines = _matching_lines(lsusb_output, CAMERA_HINTS)
    expected_camera_present = Path(EXPECTED_CAMERA_DEVICE).exists()

    mic_detected = bool(samson_usb_lines or samson_audio_lines or samson_wpctl_lines)
    camera_detected = expected_camera_present or bool(camera_usb_lines) or bool(video_devices)

    return {
        "overall": "READY" if mic_detected and camera_detected else "CHECK DEVICES",
        "ready": mic_detected and camera_detected,
        "audio_backend": "PipeWire",
        "dock_note": "Dell dock must be powered; USB devices may disappear if dock power is unplugged.",
        "microphone": {
            "name": "Samson Q2U",
            "detected": mic_detected,
            "usb_lines": samson_usb_lines,
            "audio_source_lines": samson_audio_lines,
            "wpctl_lines": samson_wpctl_lines,
            "test_command": "timeout 5 pw-record test.wav && pw-play test.wav",
        },
        "camera": {
            "name": "Insta360 Link",
            "detected": camera_detected,
            "expected_device": EXPECTED_CAMERA_DEVICE,
            "expected_device_present": expected_camera_present,
            "video_devices": video_devices,
            "usb_lines": camera_usb_lines,
            "test_command": f"ffplay {EXPECTED_CAMERA_DEVICE}",
        },
        "raw": {
            "lsusb": lsusb_output,
            "pactl_sources": pactl_sources_output,
        },
    }
