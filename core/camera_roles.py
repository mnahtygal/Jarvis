from __future__ import annotations

import fnmatch
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
        "preferred_card_name": "HD Pro Webcam C920",
        "preferred_bus_info": "usb-a80aa10000.usb-2.3",
        "preferred_by_id_capture_match": "usb-046d_HD_Pro_Webcam_C920_963B013F-video-index0",
        "preferred_by_id_metadata_match": "usb-046d_HD_Pro_Webcam_C920_963B013F-video-index1",
        "role": "workbench",
        "enabled": True,
        "preferred_resolution": {"width": 1920, "height": 1080},
        "preferred_pixel_format": "MJPG",
        "match_names": ["HD Pro Webcam C920", "Logitech HD Pro Webcam C920", "C920"],
    },
    {
        "id": "insta360_link",
        "display_name": "Insta360 Link",
        "detected_v4l2_name": "Insta360 Link: Insta360 Link",
        "preferred_card_name": "Insta360 Link: Insta360 Link",
        "preferred_bus_info": "usb-a80aa10000.usb-2.2.2",
        "preferred_by_id_capture_match": "usb-Amba_Insta360_Link-video-index0",
        "preferred_by_id_metadata_match": "usb-Amba_Insta360_Link-video-index1",
        "role": "face",
        "enabled": True,
        "preferred_resolution": {"width": 1920, "height": 1080},
        "preferred_pixel_format": "MJPG",
        "match_names": ["Insta360 Link: Insta360 Link", "Insta360 Link", "Insta360"],
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
        detail = active.get("resolution_error") if active else None
        suffix = f" {detail}" if detail else ""
        raise ValueError(f"{display_name} is unavailable.{suffix}")

    data["cameras"] = cameras
    data["active_camera_role"] = requested_role
    save_camera_config(data)
    return get_camera_roles_status(config=data)


def discover_v4l2_devices() -> list[dict[str, Any]]:
    """Return every V4L2 node with its node-specific Device Caps."""
    return discover_v4l2_inventory()["devices"]


def discover_v4l2_inventory() -> dict[str, Any]:
    listed_devices, list_error = _discover_from_v4l2_ctl()
    if not listed_devices:
        listed_devices = _discover_from_sysfs()

    by_id_links = _discover_stable_links(Path("/dev/v4l/by-id"))
    by_path_links = _discover_stable_links(Path("/dev/v4l/by-path"))
    devices = []
    errors = [list_error] if list_error else []

    for path in sorted(listed_devices, key=_device_sort_key):
        listed = listed_devices[path]
        details, error = _inspect_v4l2_device(path)
        device = {
            "path": path,
            "name": details.get("card_name") or listed.get("name"),
            "card_name": details.get("card_name") or listed.get("name"),
            "bus_info": details.get("bus_info") or listed.get("bus_info"),
            "driver": details.get("driver"),
            "capabilities": details.get("capabilities", []),
            "device_caps": details.get("device_caps", []),
            "interface_type": details.get("interface_type", "unknown"),
            "by_id": by_id_links.get(path, []),
            "by_path": by_path_links.get(path, []),
        }
        if error:
            device["discovery_error"] = error
            errors.append(f"{path}: {error}")
        devices.append(device)

    return {"devices": devices, "errors": errors}


def resolve_camera(
    identifier: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    status = get_camera_roles_status(config=config)
    requested = (identifier or "").strip()
    if not requested:
        requested = status["active_role"]

    if requested.startswith("/dev/"):
        device = next(
            (candidate for candidate in status["devices"] if candidate.get("path") == requested),
            None,
        )
        if device:
            is_capture = device.get("interface_type") == "capture"
            return {
                "role": None,
                "device": requested if is_capture else None,
                "resolved_device_path": requested if is_capture else None,
                "available": is_capture,
                "display_name": device.get("name") or requested,
                "detected_v4l2_name": device.get("name"),
                "matched_device": deepcopy(device),
                "source": "explicit_device",
                "resolution_method": "explicit_device" if is_capture else "unresolved",
                "resolution_error": (
                    None if is_capture else f"{requested} is not a Video Capture interface."
                ),
            }
        return {
            "role": None,
            "device": None,
            "resolved_device_path": None,
            "available": False,
            "display_name": requested,
            "detected_v4l2_name": None,
            "source": "explicit_device",
            "resolution_method": "unresolved",
            "resolution_error": f"Camera device not found: {requested}",
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
    inventory = discover_v4l2_inventory()
    devices = inventory["devices"]
    groups = _group_physical_cameras(devices)
    cameras = []
    active_role = get_active_camera_role(data)

    for camera in get_configured_cameras(data):
        group, resolution_method, resolution_error = _match_camera_to_group(camera, groups)
        capture = group.get("capture") if group else None
        metadata = group.get("metadata") if group else None
        enabled = bool(camera.get("enabled", True))
        capture_by_id = _first_link(capture, "by_id")
        metadata_by_id = _first_link(metadata, "by_id")
        capture_by_path = _first_link(capture, "by_path")

        enriched = {
            "id": camera.get("id"),
            "display_name": camera.get("display_name"),
            "detected_v4l2_name": camera.get("detected_v4l2_name"),
            "role": camera.get("role"),
            "resolved_device_path": capture.get("path") if capture else None,
            "enabled": enabled,
            "available": bool(enabled and capture),
            "preferred_resolution": camera.get("preferred_resolution"),
            "preferred_pixel_format": camera.get("preferred_pixel_format"),
            "matched_device": deepcopy(capture),
            "capture_device": capture.get("path") if capture else None,
            "metadata_device": metadata.get("path") if metadata else None,
            "capture_by_id": capture_by_id,
            "metadata_by_id": metadata_by_id,
            "by_path": capture_by_path,
            "card_name": capture.get("card_name") if capture else group.get("card_name") if group else None,
            "bus_info": capture.get("bus_info") if capture else group.get("bus_info") if group else None,
            "device_caps": capture.get("device_caps", []) if capture else [],
            "interface_type": capture.get("interface_type") if capture else None,
            "stable_identity": group.get("stable_identity") if group else None,
            "resolution_method": resolution_method,
            "resolution_error": resolution_error,
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
        "discovery_errors": inventory["errors"],
    }


def _run_v4l2_command(command: list[str], timeout: float = 3.0) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return "", "v4l2-ctl is unavailable."
    except subprocess.TimeoutExpired:
        return "", f"v4l2-ctl timed out after {timeout} seconds."
    except Exception as error:
        return "", f"v4l2-ctl failed: {error}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        return "", f"v4l2-ctl failed: {detail}"
    return result.stdout or "", None


def _discover_from_v4l2_ctl() -> tuple[dict[str, dict[str, Any]], str | None]:
    output, error = _run_v4l2_command(["v4l2-ctl", "--list-devices"])
    if error:
        return {}, error

    devices: dict[str, dict[str, Any]] = {}
    current_name = None
    current_bus = None
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            current_name = None
            current_bus = None
            continue
        if not line.startswith((" ", "\t")):
            match = re.match(r"^(?P<name>.+?)(?:\s+\((?P<bus>[^)]+)\))?:$", line)
            current_name = (match.group("name") if match else line).strip()
            current_bus = match.group("bus") if match and match.group("bus") else None
            continue
        path = line.strip()
        if path.startswith("/dev/video"):
            devices[path] = {"path": path, "name": current_name, "bus_info": current_bus}

    return devices, None


def _discover_from_sysfs() -> dict[str, dict[str, Any]]:
    devices = {}
    for path in sorted(Path("/dev").glob("video*"), key=lambda item: _device_sort_key(str(item))):
        name_path = Path("/sys/class/video4linux") / path.name / "name"
        try:
            name = name_path.read_text(encoding="utf-8").strip()
        except Exception:
            name = None
        devices[str(path)] = {"path": str(path), "name": name, "bus_info": None}
    return devices


def _discover_stable_links(directory: Path) -> dict[str, list[str]]:
    links: dict[str, list[str]] = {}
    try:
        entries = sorted(directory.iterdir(), key=lambda path: path.name)
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return links

    for entry in entries:
        try:
            target = str(entry.resolve(strict=True))
        except (FileNotFoundError, OSError, RuntimeError):
            continue
        if not target.startswith("/dev/video"):
            continue
        links.setdefault(target, []).append(str(entry))
    return links


def _inspect_v4l2_device(path: str) -> tuple[dict[str, Any], str | None]:
    output, error = _run_v4l2_command(["v4l2-ctl", "-d", path, "--all"])
    if error:
        return {
            "capabilities": [],
            "device_caps": [],
            "interface_type": "unknown",
        }, error

    device_caps = _parse_capability_block(output, "Device Caps")
    details = {
        "driver": _first_match(output, r"^\s*Driver name\s*:\s*(.+)$"),
        "card_name": _first_match(output, r"^\s*Card type\s*:\s*(.+)$"),
        "bus_info": _first_match(output, r"^\s*Bus info\s*:\s*(.+)$"),
        "capabilities": _parse_capability_block(output, "Capabilities"),
        "device_caps": device_caps,
        "interface_type": _classify_interface(device_caps),
    }
    return details, None


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _parse_capability_block(text: str, label: str) -> list[str]:
    lines = text.splitlines()
    header_pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*.+$")
    for index, line in enumerate(lines):
        if not header_pattern.match(line):
            continue
        values = []
        for candidate in lines[index + 1:]:
            stripped = candidate.strip()
            if not stripped:
                break
            if ":" in stripped:
                break
            values.append(stripped)
        return values
    return []


def _classify_interface(device_caps: list[str]) -> str:
    has_video = any(capability.startswith("Video Capture") for capability in device_caps)
    has_metadata = any(capability.startswith("Metadata Capture") for capability in device_caps)
    if has_video:
        return "capture"
    if has_metadata:
        return "metadata"
    return "unknown"


def _group_physical_cameras(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for device in devices:
        card = _normalize(device.get("card_name") or device.get("name"))
        bus = _normalize(device.get("bus_info"))
        by_id_prefix = _stable_link_prefix(_first_link(device, "by_id"))
        by_path_prefix = _stable_link_prefix(_first_link(device, "by_path"))
        if card and bus:
            key = ("card_bus", card, bus)
        elif by_id_prefix:
            key = ("by_id", by_id_prefix)
        elif by_path_prefix:
            key = ("by_path", by_path_prefix)
        else:
            key = ("node", str(device.get("path")))
        grouped.setdefault(key, []).append(device)

    groups = []
    for nodes in grouped.values():
        nodes = sorted(nodes, key=lambda item: _device_sort_key(str(item.get("path", ""))))
        capture_nodes = [node for node in nodes if node.get("interface_type") == "capture"]
        metadata_nodes = [node for node in nodes if node.get("interface_type") == "metadata"]
        capture = capture_nodes[0] if len(capture_nodes) == 1 else None
        metadata = metadata_nodes[0] if len(metadata_nodes) == 1 else None
        representative = capture or metadata or nodes[0]
        group_error = None
        if len(capture_nodes) > 1:
            group_error = "Multiple Video Capture interfaces matched the same physical camera."
        elif not capture:
            group_error = "No Video Capture interface was found for this camera."
        groups.append({
            "nodes": nodes,
            "capture": capture,
            "metadata": metadata,
            "card_name": representative.get("card_name") or representative.get("name"),
            "bus_info": representative.get("bus_info"),
            "stable_identity": {
                "by_id_prefix": _stable_link_prefix(_first_link(representative, "by_id")),
                "card_name": representative.get("card_name") or representative.get("name"),
                "bus_info": representative.get("bus_info"),
                "by_path_prefix": _stable_link_prefix(_first_link(representative, "by_path")),
            },
            "error": group_error,
        })
    return groups


def _match_camera_to_group(
    camera: dict[str, Any],
    groups: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str, str | None]:
    by_id_hint = camera.get("preferred_by_id_capture_match")
    if by_id_hint:
        matches = [
            group for group in groups
            if _link_matches(_all_group_links(group, "by_id"), str(by_id_hint), interface="capture")
        ]
        result = _unique_group_result(matches, "by_id")
        if result[0] or len(matches) > 1:
            return result

    preferred_card = _normalize(camera.get("preferred_card_name"))
    preferred_bus = _normalize(camera.get("preferred_bus_info"))
    if preferred_card and preferred_bus:
        matches = [
            group for group in groups
            if _normalize(group.get("card_name")) == preferred_card
            and _normalize(group.get("bus_info")) == preferred_bus
        ]
        result = _unique_group_result(matches, "card_name_and_bus_info")
        if result[0] or len(matches) > 1:
            return result

    by_path_hint = camera.get("preferred_by_path_match")
    if by_path_hint:
        matches = [
            group for group in groups
            if _link_matches(_all_group_links(group, "by_path"), str(by_path_hint), interface="capture")
        ]
        result = _unique_group_result(matches, "by_path")
        if result[0] or len(matches) > 1:
            return result

    # Backward compatibility for older profiles: exact, unique card names only.
    exact_names = {
        _normalize(value)
        for value in [
            camera.get("preferred_card_name"),
            camera.get("detected_v4l2_name"),
            camera.get("display_name"),
            *(camera.get("match_names") or []),
        ]
        if value
    }
    matches = [group for group in groups if _normalize(group.get("card_name")) in exact_names]
    result = _unique_group_result(matches, "legacy_hint")
    if result[0] or len(matches) > 1:
        return result

    return None, "unresolved", "Camera is disconnected or no stable identity matched."


def _unique_group_result(
    matches: list[dict[str, Any]],
    method: str,
) -> tuple[dict[str, Any] | None, str, str | None]:
    if len(matches) > 1:
        return None, "unresolved", f"Stable identity matched multiple cameras using {method}."
    if not matches:
        return None, "unresolved", None
    group = matches[0]
    if group.get("error"):
        return group, method, str(group["error"])
    return group, method, None


def _all_group_links(group: dict[str, Any], field: str) -> list[tuple[str, str]]:
    links = []
    for node in group.get("nodes", []):
        for link in node.get(field, []):
            links.append((str(link), str(node.get("interface_type"))))
    return links


def _link_matches(links: list[tuple[str, str]], hint: str, interface: str) -> bool:
    normalized_hint = hint.casefold()
    for link, link_interface in links:
        if link_interface != interface:
            continue
        full = link.casefold()
        name = Path(link).name.casefold()
        if full == normalized_hint or name == normalized_hint:
            return True
        if fnmatch.fnmatch(full, normalized_hint) or fnmatch.fnmatch(name, normalized_hint):
            return True
    return False


def _first_link(device: dict[str, Any] | None, field: str) -> str | None:
    if not device:
        return None
    links = device.get(field) or []
    return str(links[0]) if links else None


def _stable_link_prefix(link: str | None) -> str | None:
    if not link:
        return None
    return re.sub(r"-video-index\d+$", "", Path(link).name, flags=re.IGNORECASE)


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _device_sort_key(path: str) -> tuple[str, int]:
    match = re.search(r"(\d+)$", path)
    return (path[:match.start()] if match else path, int(match.group(1)) if match else -1)
