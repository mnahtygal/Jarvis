from __future__ import annotations

import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMERA_CONFIG_PATH = PROJECT_ROOT / "config" / "camera_profiles.json"
DEFAULT_CAMERA_ROLE = "workbench"

DEFAULT_CAMERA_ROLES = [
    {
        "id": "logitech_c920",
        "display_name": "Logitech HD Pro Webcam C920",
        "detected_v4l2_name": "HD Pro Webcam C920",
        "role": "workbench",
        "enabled": True,
        "preferred_resolution": {"width": 1920, "height": 1080},
        "preferred_pixel_format": "MJPG",
        "match_names": ["HD Pro Webcam C920", "Logitech HD Pro Webcam C920", "C920"],
    },
    {
        "id": "insta360_link",
        "display_name": "Insta360 Link",
        "detected_v4l2_name": "Insta360 Link",
        "role": "face",
        "enabled": True,
        "preferred_resolution": {"width": 1920, "height": 1080},
        "preferred_pixel_format": "MJPG",
        "match_names": ["Insta360 Link", "Insta360"],
    },
]


def load_camera_config() -> dict[str, Any]:
    if CAMERA_CONFIG_PATH.exists():
        with CAMERA_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    return {}


def save_camera_config(data: dict[str, Any]) -> None:
    CAMERA_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = CAMERA_CONFIG_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    temp_path.replace(CAMERA_CONFIG_PATH)


def get_configured_cameras(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = config if config is not None else load_camera_config()
    configured = data.get("cameras")
    if isinstance(configured, list) and configured:
        return [deepcopy(camera) for camera in configured if isinstance(camera, dict)]
    return deepcopy(DEFAULT_CAMERA_ROLES)


def get_active_camera_role(config: dict[str, Any] | None = None) -> str:
    data = config if config is not None else load_camera_config()
    active_role = data.get("active_camera_role")
    return str(active_role or DEFAULT_CAMERA_ROLE)


def set_active_camera_role(role: str) -> dict[str, Any]:
    requested_role = (role or "").strip().lower()
    if not requested_role:
        raise ValueError("camera role is required.")

    data = load_camera_config()
    cameras = get_configured_cameras(data)
    matching = [camera for camera in cameras if camera.get("role") == requested_role]
    if not matching:
        raise ValueError(f"Unknown camera role: {requested_role}")

    status = get_camera_roles_status(config=data)
    active = next(
        (camera for camera in status["cameras"] if camera.get("role") == requested_role),
        None,
    )
    if not active or not active.get("available"):
        display_name = active.get("display_name") if active else requested_role
        raise ValueError(f"{display_name} is unavailable.")

    data["cameras"] = cameras
    data["active_camera_role"] = requested_role
    save_camera_config(data)
    return get_camera_roles_status(config=data)


def discover_v4l2_devices() -> list[dict[str, Any]]:
    devices_by_path = _discover_from_v4l2_ctl()
    if not devices_by_path:
        devices_by_path = _discover_from_sysfs()
    return [devices_by_path[path] for path in sorted(devices_by_path)]


def resolve_camera(identifier: str | None = None, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    status = get_camera_roles_status(config=config)
    requested = (identifier or "").strip()
    if not requested:
        requested = status["active_role"]

    if requested.startswith("/dev/"):
        for device in status["devices"]:
            if device.get("path") == requested:
                return {
                    "role": None,
                    "device": requested,
                    "available": True,
                    "display_name": device.get("name") or requested,
                    "detected_v4l2_name": device.get("name"),
                    "source": "explicit_device",
                }
        return {
            "role": None,
            "device": requested,
            "available": Path(requested).exists(),
            "display_name": requested,
            "detected_v4l2_name": None,
            "source": "explicit_device",
        }

    lower_requested = requested.lower()
    for camera in status["cameras"]:
        names = [
            camera.get("role"),
            camera.get("id"),
            camera.get("display_name"),
            camera.get("detected_v4l2_name"),
        ]
        if any(lower_requested == str(name or "").lower() for name in names):
            return camera

    return None


def get_camera_roles_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    data = config if config is not None else load_camera_config()
    devices = discover_v4l2_devices()
    cameras = []
    active_role = get_active_camera_role(data)

    for camera in get_configured_cameras(data):
        resolved_device = _match_camera_to_device(camera, devices)
        enriched = {
            "id": camera.get("id"),
            "display_name": camera.get("display_name"),
            "detected_v4l2_name": camera.get("detected_v4l2_name"),
            "role": camera.get("role"),
            "resolved_device_path": resolved_device.get("path") if resolved_device else None,
            "enabled": bool(camera.get("enabled", True)),
            "available": bool(camera.get("enabled", True) and resolved_device),
            "preferred_resolution": camera.get("preferred_resolution"),
            "preferred_pixel_format": camera.get("preferred_pixel_format"),
            "matched_device": resolved_device,
        }
        cameras.append(enriched)

    active_camera = next((camera for camera in cameras if camera.get("role") == active_role), None)
    return {
        "ok": True,
        "default_role": DEFAULT_CAMERA_ROLE,
        "active_role": active_role,
        "active_camera": active_camera,
        "cameras": cameras,
        "devices": devices,
    }


def _discover_from_v4l2_ctl() -> dict[str, dict[str, Any]]:
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
    except Exception:
        return {}

    if result.returncode != 0:
        return {}

    devices: dict[str, dict[str, Any]] = {}
    current_name = None
    current_bus = None
    for raw_line in (result.stdout or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            current_name = None
            current_bus = None
            continue
        if not line.startswith((" ", "\t")):
            match = re.match(r"^(?P<name>.+?)(?:\s+\((?P<bus>[^)]+)\))?:$", line)
            current_name = (match.group("name") if match else line).strip()
            current_bus = (match.group("bus") if match and match.group("bus") else None)
            continue
        path = line.strip()
        if path.startswith("/dev/video"):
            devices[path] = {"path": path, "name": current_name, "bus_info": current_bus}

    return devices


def _discover_from_sysfs() -> dict[str, dict[str, Any]]:
    devices = {}
    for path in sorted(Path("/dev").glob("video*")):
        name_path = Path("/sys/class/video4linux") / path.name / "name"
        try:
            name = name_path.read_text(encoding="utf-8").strip()
        except Exception:
            name = None
        devices[str(path)] = {"path": str(path), "name": name, "bus_info": None}
    return devices


def _match_camera_to_device(camera: dict[str, Any], devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    hints = [
        camera.get("detected_v4l2_name"),
        camera.get("display_name"),
        *(camera.get("match_names") or []),
    ]
    normalized_hints = [str(hint).lower() for hint in hints if hint]
    for device in devices:
        device_name = str(device.get("name") or "").lower()
        if any(hint in device_name or device_name in hint for hint in normalized_hints):
            return deepcopy(device)
    return None
