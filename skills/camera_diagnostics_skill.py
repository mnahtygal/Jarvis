# skills/camera_diagnostics_skill.py

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.camera_roles import DEFAULT_CAMERA_ROLE, get_camera_roles_status


INSTA360_USB_ID = "2e1a:4c01"
EXTENSION_UNIT_ID = 9
EXTENSION_UNIT_GUID = "faf1672d-b71b-4793-8c91-7b1c9b7f95f8"
EXTENSION_UNIT_CONTROLS = 11

CONTROL_NAMES = [
    "pan_absolute",
    "tilt_absolute",
    "zoom_absolute",
]


def _run_command(command: List[str], timeout: float = 3.0) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "text": stdout if stdout else stderr,
        }
    except FileNotFoundError as error:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(error),
            "text": f"ERROR: {error}",
        }
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or "").strip() if isinstance(error.stdout, str) else ""
        stderr = (error.stderr or "").strip() if isinstance(error.stderr, str) else ""
        return {
            "ok": False,
            "returncode": None,
            "stdout": stdout,
            "stderr": stderr or f"Timed out after {timeout} seconds.",
            "text": stdout or stderr or f"ERROR: timed out after {timeout} seconds.",
        }
    except Exception as error:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(error),
            "text": f"ERROR: {error}",
        }


def _first_match(text: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _parse_device_info(v4l2_all: str) -> Dict[str, Optional[str]]:
    return {
        "driver": _first_match(v4l2_all, r"^\s*Driver name\s*:\s*(.+)$"),
        "card": _first_match(v4l2_all, r"^\s*Card type\s*:\s*(.+)$"),
        "bus_info": _first_match(v4l2_all, r"^\s*Bus info\s*:\s*(.+)$"),
    }


def _parse_format(v4l2_all: str) -> Dict[str, Any]:
    width = _first_match(v4l2_all, r"^\s*Width/Height\s*:\s*(\d+)/\d+")
    height = _first_match(v4l2_all, r"^\s*Width/Height\s*:\s*\d+/(\d+)")
    pixel_format = _first_match(v4l2_all, r"^\s*Pixel Format\s*:\s*'([^']+)'")
    fps = _first_match(v4l2_all, r"^\s*Frames per second\s*:\s*(.+)$")

    return {
        "width": int(width) if width else None,
        "height": int(height) if height else None,
        "pixel_format": pixel_format,
        "fps": fps,
    }


def _parse_control_line(line: str) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for key in ["min", "max", "step", "default", "value"]:
        match = re.search(rf"\b{key}=(-?\d+)", line)
        if match:
            values[key] = int(match.group(1))
    return values


def _parse_controls(v4l2_ctrls: str) -> Dict[str, Dict[str, Any]]:
    controls: Dict[str, Dict[str, Any]] = {}
    for control_name in CONTROL_NAMES:
        controls[control_name] = {
            "present": False,
            "value": None,
            "min": None,
            "max": None,
            "step": None,
        }

    for line in v4l2_ctrls.splitlines():
        stripped = line.strip()
        for control_name in CONTROL_NAMES:
            if not stripped.startswith(control_name):
                continue

            parsed = _parse_control_line(stripped)
            controls[control_name] = {
                "present": True,
                "value": parsed.get("value"),
                "min": parsed.get("min"),
                "max": parsed.get("max"),
                "step": parsed.get("step"),
            }

    return controls


def _detect_extension_unit(lsusb_output: str, command_result: Dict[str, Any]) -> Dict[str, Any]:
    lower_output = lsusb_output.lower()
    guid_detected = EXTENSION_UNIT_GUID.lower() in lower_output
    unit_detected = bool(re.search(r"\bbunitid\s+9\b", lower_output))
    controls_detected = bool(re.search(r"\bbnrinctrls\s+11\b", lower_output))
    detected = guid_detected or (unit_detected and controls_detected)

    detail = None
    if not command_result.get("ok"):
        detail = (
            command_result.get("stderr")
            or command_result.get("text")
            or "lsusb extension probe did not complete successfully."
        )

    return {
        "detected": detected,
        "unit_id": EXTENSION_UNIT_ID,
        "guid": EXTENSION_UNIT_GUID,
        "controls": EXTENSION_UNIT_CONTROLS,
        "detail": detail,
    }


def get_camera_diagnostics_status() -> Dict[str, Any]:
    camera_status = get_camera_roles_status()
    active_camera = camera_status.get("active_camera") or {}
    capture_device = active_camera.get("resolved_device_path") or ""
    capture_present = bool(capture_device and Path(capture_device).exists())

    capture_all_result = (
        _run_command(["v4l2-ctl", "-d", capture_device, "--all"])
        if capture_device
        else {"ok": False, "text": ""}
    )
    controls_result = (
        _run_command(["v4l2-ctl", "-d", capture_device, "--list-ctrls"])
        if capture_device
        else {"ok": False, "text": ""}
    )
    extension_probe_result = _run_command(["lsusb", "-v", "-d", INSTA360_USB_ID], timeout=5.0)

    capture_all = capture_all_result.get("text", "")
    controls_text = controls_result.get("text", "")
    extension_probe = extension_probe_result.get("text", "")

    device_info = _parse_device_info(capture_all)
    controls = _parse_controls(controls_text)
    standard_controls_present = all(
        controls[control_name]["present"]
        for control_name in ["pan_absolute", "tilt_absolute"]
    )
    extension_unit = _detect_extension_unit(extension_probe, extension_probe_result)

    ready = capture_present and bool(device_info.get("driver"))

    return {
        "overall": "READY" if ready else "CHECK CAMERA",
        "ready": ready,
        "active_role": camera_status.get("active_role"),
        "default_role": DEFAULT_CAMERA_ROLE,
        "active_camera": active_camera,
        "cameras": camera_status.get("cameras", []),
        "capture_device": {
            "path": capture_device or None,
            "present": capture_present,
            "role": active_camera.get("role") or "video_capture",
            "driver": device_info.get("driver"),
            "card": device_info.get("card"),
            "bus_info": device_info.get("bus_info"),
            "format": _parse_format(capture_all),
        },
        "metadata_device": {
            "path": None,
            "present": False,
            "role": "metadata_capture",
            "driver": None,
            "card": None,
            "bus_info": None,
        },
        "controls": controls,
        "gimbal": {
            "standard_controls_present": standard_controls_present,
            "standard_controls_move_physical_gimbal": False,
            "status": "extension_unit_required",
            "note": (
                "V4L2 pan/tilt controls accept values but do not physically move "
                "the Insta360 Link gimbal on Thor."
            ),
        },
        "extension_unit": extension_unit,
        "raw": {
            "v4l2_all": capture_all,
            "v4l2_ctrls": controls_text,
            "metadata_v4l2_all": "",
            "extension_probe": extension_probe,
        },
    }
