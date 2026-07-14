from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from core import camera_roles
from skills import camera_skill


CURRENT_LIST = """\
Insta360 Link: Insta360 Link (usb-a80aa10000.usb-2.2.2):
\t/dev/video2
\t/dev/video3

HD Pro Webcam C920 (usb-a80aa10000.usb-2.3):
\t/dev/video0
\t/dev/video1
"""

REVERSED_LIST = """\
Insta360 Link: Insta360 Link (usb-a80aa10000.usb-2.2.2):
\t/dev/video0
\t/dev/video1

HD Pro Webcam C920 (usb-a80aa10000.usb-2.3):
\t/dev/video2
\t/dev/video3
"""


def device_all(card: str, bus: str, interface: str) -> str:
    device_cap = "Video Capture" if interface == "capture" else "Metadata Capture"
    return f"""\
Driver Info:
\tDriver name      : uvcvideo
\tCard type        : {card}
\tBus info         : {bus}
\tCapabilities     : 0x84a00001
\t\tVideo Capture
\t\tMetadata Capture
\t\tStreaming
\t\tDevice Capabilities
\tDevice Caps      : 0x04200001
\t\t{device_cap}
\t\tStreaming
\tBus info         : {bus}
"""


class Completed:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def subprocess_result(list_output: str, mapping: dict[str, tuple[str, str, str]]):
    def run(command, **_kwargs):
        if command == ["v4l2-ctl", "--list-devices"]:
            return Completed(list_output)
        if command[:2] == ["v4l2-ctl", "-d"]:
            card, bus, interface = mapping[command[2]]
            return Completed(device_all(card, bus, interface))
        raise AssertionError(f"Unexpected command: {command}")

    return run


CURRENT_MAPPING = {
    "/dev/video0": ("HD Pro Webcam C920", "usb-a80aa10000.usb-2.3", "capture"),
    "/dev/video1": ("HD Pro Webcam C920", "usb-a80aa10000.usb-2.3", "metadata"),
    "/dev/video2": ("Insta360 Link: Insta360 Link", "usb-a80aa10000.usb-2.2.2", "capture"),
    "/dev/video3": ("Insta360 Link: Insta360 Link", "usb-a80aa10000.usb-2.2.2", "metadata"),
}

CURRENT_BY_ID = {
    "/dev/video0": ["/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_963B013F-video-index0"],
    "/dev/video1": ["/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_963B013F-video-index1"],
    "/dev/video2": ["/dev/v4l/by-id/usb-Amba_Insta360_Link-video-index0"],
    "/dev/video3": ["/dev/v4l/by-id/usb-Amba_Insta360_Link-video-index1"],
}


def stable_links(by_id=None, by_path=None):
    by_id = by_id or {}
    by_path = by_path or {}

    def discover(directory: Path):
        return by_id if directory.name == "by-id" else by_path

    return discover


def inventory(
    list_output: str = CURRENT_LIST,
    mapping: dict[str, tuple[str, str, str]] | None = None,
    by_id=None,
    by_path=None,
):
    with (
        patch("core.camera_roles.subprocess.run", side_effect=subprocess_result(list_output, mapping or CURRENT_MAPPING)),
        patch("core.camera_roles._discover_stable_links", side_effect=stable_links(by_id, by_path)),
    ):
        return camera_roles.discover_v4l2_inventory()


class CameraRoleTests(unittest.TestCase):
    def test_current_enumeration_groups_capture_and_metadata(self) -> None:
        discovered = inventory(by_id=CURRENT_BY_ID)
        config = {"active_camera_role": "workbench", "cameras": camera_roles.DEFAULT_CAMERA_ROLES}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            status = camera_roles.get_camera_roles_status(config=config)

        workbench = next(camera for camera in status["cameras"] if camera["role"] == "workbench")
        face = next(camera for camera in status["cameras"] if camera["role"] == "face")
        self.assertEqual(workbench["capture_device"], "/dev/video0")
        self.assertEqual(workbench["metadata_device"], "/dev/video1")
        self.assertEqual(face["capture_device"], "/dev/video2")
        self.assertEqual(face["metadata_device"], "/dev/video3")
        self.assertEqual(workbench["resolution_method"], "by_id")

    def test_reversed_enumeration_resolves_same_roles(self) -> None:
        mapping = {
            "/dev/video0": CURRENT_MAPPING["/dev/video2"],
            "/dev/video1": CURRENT_MAPPING["/dev/video3"],
            "/dev/video2": CURRENT_MAPPING["/dev/video0"],
            "/dev/video3": CURRENT_MAPPING["/dev/video1"],
        }
        links = {
            "/dev/video0": CURRENT_BY_ID["/dev/video2"],
            "/dev/video1": CURRENT_BY_ID["/dev/video3"],
            "/dev/video2": CURRENT_BY_ID["/dev/video0"],
            "/dev/video3": CURRENT_BY_ID["/dev/video1"],
        }
        discovered = inventory(REVERSED_LIST, mapping, links)
        config = {"active_camera_role": "workbench", "cameras": camera_roles.DEFAULT_CAMERA_ROLES}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            status = camera_roles.get_camera_roles_status(config=config)

        paths = {camera["role"]: camera["capture_device"] for camera in status["cameras"]}
        self.assertEqual(paths, {"workbench": "/dev/video2", "face": "/dev/video0"})

    def test_arbitrary_node_numbers_sort_numerically_and_resolve(self) -> None:
        listing = """\
HD Pro Webcam C920 (usb-a80aa10000.usb-2.3):
\t/dev/video11
\t/dev/video7
"""
        mapping = {
            "/dev/video11": ("HD Pro Webcam C920", "usb-a80aa10000.usb-2.3", "metadata"),
            "/dev/video7": ("HD Pro Webcam C920", "usb-a80aa10000.usb-2.3", "capture"),
        }
        discovered = inventory(listing, mapping)
        self.assertEqual([item["path"] for item in discovered["devices"]], ["/dev/video7", "/dev/video11"])

    def test_device_caps_not_broad_capabilities_classifies_interface(self) -> None:
        discovered = inventory()
        capture, metadata = discovered["devices"][:2]
        self.assertIn("Metadata Capture", capture["capabilities"])
        self.assertEqual(capture["interface_type"], "capture")
        self.assertIn("Video Capture", metadata["capabilities"])
        self.assertEqual(metadata["interface_type"], "metadata")

    def test_by_id_capture_is_preferred_over_stale_bus_info(self) -> None:
        discovered = inventory(by_id=CURRENT_BY_ID)
        profile = dict(camera_roles.DEFAULT_CAMERA_ROLES[0], preferred_bus_info="usb-stale-port")
        config = {"active_camera_role": "workbench", "cameras": [profile]}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            camera = camera_roles.get_camera_roles_status(config=config)["cameras"][0]
        self.assertEqual(camera["resolution_method"], "by_id")
        self.assertEqual(camera["capture_device"], "/dev/video0")

    def test_by_id_metadata_is_recorded_separately(self) -> None:
        discovered = inventory(by_id=CURRENT_BY_ID)
        config = {"active_camera_role": "face", "cameras": [camera_roles.DEFAULT_CAMERA_ROLES[1]]}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            camera = camera_roles.get_camera_roles_status(config=config)["cameras"][0]
        self.assertTrue(camera["capture_by_id"].endswith("video-index0"))
        self.assertTrue(camera["metadata_by_id"].endswith("video-index1"))

    def test_card_name_and_bus_info_fallback_without_by_id(self) -> None:
        discovered = inventory()
        config = {"active_camera_role": "face", "cameras": [camera_roles.DEFAULT_CAMERA_ROLES[1]]}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            camera = camera_roles.get_camera_roles_status(config=config)["cameras"][0]
        self.assertEqual(camera["resolution_method"], "card_name_and_bus_info")
        self.assertEqual(camera["capture_device"], "/dev/video2")

    def test_missing_by_id_directory_returns_empty_mapping(self) -> None:
        with patch.object(Path, "iterdir", side_effect=FileNotFoundError):
            self.assertEqual(camera_roles._discover_stable_links(Path("/missing/by-id")), {})

    def test_by_path_fallback(self) -> None:
        by_path = {"/dev/video2": ["/dev/v4l/by-path/camera-face-video-index0"]}
        discovered = inventory(by_path=by_path)
        profile = dict(
            camera_roles.DEFAULT_CAMERA_ROLES[1],
            preferred_bus_info="usb-stale-port",
            preferred_by_path_match="camera-face-video-index0",
        )
        config = {"active_camera_role": "face", "cameras": [profile]}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            camera = camera_roles.get_camera_roles_status(config=config)["cameras"][0]
        self.assertEqual(camera["resolution_method"], "by_path")

    def test_metadata_only_camera_is_never_selected(self) -> None:
        listing = """HD Pro Webcam C920 (usb-a80aa10000.usb-2.3):\n\t/dev/video1\n"""
        mapping = {"/dev/video1": CURRENT_MAPPING["/dev/video1"]}
        discovered = inventory(listing, mapping)
        config = {"active_camera_role": "workbench", "cameras": [camera_roles.DEFAULT_CAMERA_ROLES[0]]}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            camera = camera_roles.get_camera_roles_status(config=config)["cameras"][0]
        self.assertFalse(camera["available"])
        self.assertIsNone(camera["resolved_device_path"])
        self.assertIn("No Video Capture", camera["resolution_error"])

    def test_disconnected_camera_reports_unavailable(self) -> None:
        empty = {"devices": [], "errors": []}
        config = {"active_camera_role": "workbench", "cameras": camera_roles.DEFAULT_CAMERA_ROLES}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=empty):
            status = camera_roles.get_camera_roles_status(config=config)
        self.assertFalse(any(camera["available"] for camera in status["cameras"]))
        self.assertTrue(all(camera["resolution_method"] == "unresolved" for camera in status["cameras"]))

    def test_duplicate_exact_names_are_ambiguous_without_stable_identity(self) -> None:
        devices = []
        for node, bus in [("/dev/video4", "usb-one"), ("/dev/video8", "usb-two")]:
            devices.append({
                "path": node,
                "name": "Twin Camera",
                "card_name": "Twin Camera",
                "bus_info": bus,
                "driver": "uvcvideo",
                "capabilities": ["Video Capture"],
                "device_caps": ["Video Capture"],
                "interface_type": "capture",
                "by_id": [],
                "by_path": [],
            })
        profile = {"id": "twin", "role": "workbench", "display_name": "Twin Camera", "enabled": True}
        with patch("core.camera_roles.discover_v4l2_inventory", return_value={"devices": devices, "errors": []}):
            camera = camera_roles.get_camera_roles_status(
                config={"active_camera_role": "workbench", "cameras": [profile]},
            )["cameras"][0]
        self.assertFalse(camera["available"])
        self.assertIn("multiple cameras", camera["resolution_error"])

    def test_stale_fixed_profile_path_does_not_override_discovery(self) -> None:
        discovered = inventory(by_id=CURRENT_BY_ID)
        profile = dict(camera_roles.DEFAULT_CAMERA_ROLES[1], device_path="/dev/video0", metadata_device="/dev/video1")
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            camera = camera_roles.get_camera_roles_status(
                config={"active_camera_role": "face", "cameras": [profile]},
            )["cameras"][0]
        self.assertEqual(camera["capture_device"], "/dev/video2")
        self.assertEqual(camera["metadata_device"], "/dev/video3")

    def test_explicit_metadata_node_is_rejected(self) -> None:
        discovered = inventory()
        with patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered):
            camera = camera_roles.resolve_camera("/dev/video1", config={"cameras": camera_roles.DEFAULT_CAMERA_ROLES})
        self.assertFalse(camera["available"])
        self.assertIsNone(camera["device"])

    def test_v4l2_ctl_unavailable_returns_useful_error(self) -> None:
        with (
            patch("core.camera_roles.subprocess.run", side_effect=FileNotFoundError),
            patch("core.camera_roles._discover_from_sysfs", return_value={}),
            patch("core.camera_roles._discover_stable_links", return_value={}),
        ):
            discovered = camera_roles.discover_v4l2_inventory()
        self.assertIn("unavailable", discovered["errors"][0])

    def test_switching_camera_role_persists_active_role(self) -> None:
        discovered = inventory(by_id=CURRENT_BY_ID)
        config = {"active_camera_role": "workbench", "cameras": camera_roles.DEFAULT_CAMERA_ROLES}
        saved = {}
        with (
            patch("core.camera_roles.load_camera_config", return_value=config),
            patch("core.camera_roles.save_camera_config", side_effect=lambda data: saved.update(data)),
            patch("core.camera_roles.discover_v4l2_inventory", return_value=discovered),
        ):
            status = camera_roles.set_active_camera_role("face")
        self.assertEqual(saved["active_camera_role"], "face")
        self.assertEqual(status["active_role"], "face")

    def test_capture_skill_passes_only_resolved_capture_node_to_ffmpeg(self) -> None:
        resolved = {
            "role": "workbench",
            "resolved_device_path": "/dev/video8",
            "display_name": "Logitech HD Pro Webcam C920",
        }
        completed = Completed(returncode=1, stderr="test capture failure")
        with (
            patch("skills.camera_skill.resolve_camera", return_value=resolved),
            patch("skills.camera_skill.Path.exists", side_effect=[True, False]),
            patch("skills.camera_skill.subprocess.run", return_value=completed) as run,
        ):
            result = camera_skill.capture_snapshot(role="workbench")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("-i") + 1], "/dev/video8")
        self.assertEqual(result["device"], "/dev/video8")


if __name__ == "__main__":
    unittest.main()
