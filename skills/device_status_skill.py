# skills/device_status_skill.py

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List

from core.camera_roles import get_camera_roles_status
from core.microphone import get_microphone_status


SAMSON_HINTS = ["samson", "q2u"]
CAMERA_HINTS = ["insta360", "camera", "webcam", "video"]


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
    camera_status = get_camera_roles_status()
    microphone_status = get_microphone_status()

    samson_usb_lines = _matching_lines(lsusb_output, SAMSON_HINTS)
    samson_audio_lines = _matching_lines(pactl_sources_output, SAMSON_HINTS)
    samson_wpctl_lines = _matching_lines(wpctl_output, SAMSON_HINTS)

    camera_usb_lines = _matching_lines(lsusb_output, CAMERA_HINTS)
    active_camera = camera_status.get("active_camera") or {}
    active_camera_device = active_camera.get("resolved_device_path")
    active_camera_present = bool(active_camera_device and Path(active_camera_device).exists())

    mic_detected = bool(microphone_status.get("resolved_microphone"))
    camera_detected = any(camera.get("available") for camera in camera_status.get("cameras", []))

    return {
        "overall": "READY" if mic_detected and camera_detected else "CHECK DEVICES",
        "ready": mic_detected and camera_detected,
        "audio_backend": "PipeWire",
        "dock_note": "Dell dock must be powered; USB devices may disappear if dock power is unplugged.",
        "microphone": {
            "name": "Samson Q2U",
            "detected": mic_detected,
            "preferred_microphone": microphone_status.get("preferred_microphone"),
            "resolved_microphone": microphone_status.get("resolved_microphone"),
            "available": microphone_status.get("available"),
            "using_preferred": microphone_status.get("using_preferred"),
            "fallback_microphone": microphone_status.get("fallback_microphone"),
            "usb_lines": samson_usb_lines,
            "audio_source_lines": samson_audio_lines,
            "wpctl_lines": samson_wpctl_lines,
            "test_command": "timeout 5 pw-record test.wav && pw-play test.wav",
        },
        "camera": {
            "name": active_camera.get("display_name") or "Camera",
            "detected": camera_detected,
            "expected_device": active_camera_device,
            "expected_device_present": active_camera_present,
            "active_role": camera_status.get("active_role"),
            "active_camera": active_camera,
            "cameras": camera_status.get("cameras", []),
            "video_devices": video_devices,
            "usb_lines": camera_usb_lines,
            "test_command": f"ffplay {active_camera_device}" if active_camera_device else "Open Vision Lab camera selector.",
        },
        "raw": {
            "lsusb": lsusb_output,
            "pactl_sources": pactl_sources_output,
        },
    }
