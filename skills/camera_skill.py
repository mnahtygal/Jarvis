# skills/camera_skill.py

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import cv2

from core.camera_roles import DEFAULT_CAMERA_ROLE, resolve_camera

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMERA_DEVICE = os.getenv("JARVIS_CAMERA_DEVICE", "")
CAPTURE_DIR = PROJECT_ROOT / "runtime" / "camera"
LOGGER = logging.getLogger(__name__)


def _decode_fourcc(value: float) -> str:
    encoded = int(round(value))
    return "".join(
        chr((encoded >> (8 * index)) & 0xFF)
        for index in range(4)
    ).rstrip("\x00")


def _read_negotiated_mode(capture: Any) -> Dict[str, Any]:
    return {
        "pixel_format": _decode_fourcc(
            capture.get(cv2.CAP_PROP_FOURCC)
        ),
        "width": int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
        "height": int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))),
        "fps": round(float(capture.get(cv2.CAP_PROP_FPS)), 3),
    }


def _requested_mode(camera: Dict[str, Any]) -> Dict[str, Any]:
    resolution = camera.get("preferred_resolution") or {}
    return {
        "pixel_format": camera.get("preferred_pixel_format"),
        "width": resolution.get("width"),
        "height": resolution.get("height"),
        "fps": resolution.get("fps") or camera.get("preferred_fps"),
    }


def _request_capture_mode(
    capture: Any,
    requested_mode: Dict[str, Any],
) -> Dict[str, bool | None]:
    """Apply V4L2 mode requests in driver-sensitive order."""

    results: Dict[str, bool | None] = {
        "pixel_format": None,
        "width": None,
        "height": None,
        "fps": None,
    }

    pixel_format = requested_mode.get("pixel_format")
    if pixel_format:
        normalized_format = str(pixel_format).upper()
        if len(normalized_format) != 4:
            raise ValueError(
                "preferred_pixel_format must contain exactly four characters."
            )
        results["pixel_format"] = bool(
            capture.set(
                cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(*normalized_format),
            )
        )

    width = requested_mode.get("width")
    if width is not None:
        results["width"] = bool(
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        )

    height = requested_mode.get("height")
    if height is not None:
        results["height"] = bool(
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        )

    fps = requested_mode.get("fps")
    if fps is not None:
        results["fps"] = bool(
            capture.set(cv2.CAP_PROP_FPS, float(fps))
        )

    return results


def _mode_mismatches(
    requested: Dict[str, Any],
    negotiated: Dict[str, Any],
    *,
    frame_width: int,
    frame_height: int,
) -> list[str]:
    mismatches = []

    requested_format = requested.get("pixel_format")
    negotiated_format = negotiated.get("pixel_format")
    if (
        requested_format
        and str(requested_format).upper() != str(negotiated_format).upper()
    ):
        mismatches.append(
            f"pixel_format requested={requested_format} "
            f"negotiated={negotiated_format or 'unknown'}"
        )

    for name, frame_value in (
        ("width", frame_width),
        ("height", frame_height),
    ):
        requested_value = requested.get(name)
        negotiated_value = negotiated.get(name)
        if requested_value is None:
            continue
        if int(requested_value) != int(negotiated_value or 0):
            mismatches.append(
                f"{name} requested={requested_value} "
                f"negotiated={negotiated_value}"
            )
        if int(requested_value) != frame_value:
            mismatches.append(
                f"{name} requested={requested_value} "
                f"captured={frame_value}"
            )

    requested_fps = requested.get("fps")
    if requested_fps is not None and abs(
        float(requested_fps) - float(negotiated.get("fps") or 0.0)
    ) > 0.1:
        mismatches.append(
            f"fps requested={requested_fps} "
            f"negotiated={negotiated.get('fps')}"
        )

    return mismatches


def capture_snapshot(
    device: str | None = None,
    role: str | None = None,
    timeout_seconds: int = 8,
) -> Dict[str, Any]:
    """Capture one JPEG frame through the explicit OpenCV V4L2 backend."""
    requested = device or role or DEFAULT_CAMERA_DEVICE or DEFAULT_CAMERA_ROLE
    camera = resolve_camera(requested)
    if camera is None:
        return {
            "ok": False,
            "device": requested,
            "role": role,
            "error": f"Camera not configured: {requested}",
        }

    resolved_device = camera.get("resolved_device_path") or camera.get("device")
    if not resolved_device:
        return {
            "ok": False,
            "device": None,
            "role": camera.get("role") or role,
            "camera": camera,
            "error": f"Camera unavailable: {camera.get('display_name') or requested}",
        }

    camera_path = Path(str(resolved_device))
    if not camera_path.exists():
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "error": f"Camera device not found: {resolved_device}",
        }

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = CAPTURE_DIR / f"snapshot_{timestamp}.jpg"

    requested_capture_mode = _requested_mode(camera)
    started_at = time.perf_counter()

    try:
        capture = cv2.VideoCapture(
            str(resolved_device),
            cv2.CAP_V4L2,
        )
    except Exception as error:
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "backend": "opencv_v4l2",
            "requested_mode": requested_capture_mode,
            "error": f"Could not open camera through V4L2: {error}",
        }

    if not capture.isOpened():
        capture.release()
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "backend": "opencv_v4l2",
            "requested_mode": requested_capture_mode,
            "error": (
                "OpenCV could not open the stable discovered capture node "
                f"through V4L2: {resolved_device}"
            ),
        }

    try:
        property_requests = _request_capture_mode(
            capture,
            requested_capture_mode,
        )
        negotiated_mode = _read_negotiated_mode(capture)
        frame_ok, frame = capture.read()
    except Exception as error:
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "backend": "opencv_v4l2",
            "requested_mode": requested_capture_mode,
            "error": f"Camera mode negotiation failed: {error}",
        }
    finally:
        capture.release()

    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    if not frame_ok or frame is None:
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "backend": "opencv_v4l2",
            "requested_mode": requested_capture_mode,
            "property_requests": property_requests,
            "negotiated_mode": negotiated_mode,
            "elapsed_seconds": elapsed_seconds,
            "error": "V4L2 camera opened but did not return a frame.",
        }

    frame_height, frame_width = frame.shape[:2]
    negotiated_mode = {
        **negotiated_mode,
        "frame_width": int(frame_width),
        "frame_height": int(frame_height),
    }
    mismatches = _mode_mismatches(
        requested_capture_mode,
        negotiated_mode,
        frame_width=frame_width,
        frame_height=frame_height,
    )
    mode_status = "fallback" if mismatches else "requested"

    log_message = (
        "Camera %s negotiated %s %sx%s @ %s FPS; frame=%sx%s; "
        "requested=%s; status=%s"
    )
    log_args = (
        resolved_device,
        negotiated_mode["pixel_format"] or "unknown",
        negotiated_mode["width"],
        negotiated_mode["height"],
        negotiated_mode["fps"],
        frame_width,
        frame_height,
        requested_capture_mode,
        mode_status,
    )
    if mismatches:
        LOGGER.warning(log_message + "; mismatches=%s", *log_args, mismatches)
    else:
        LOGGER.info(log_message, *log_args)

    if not cv2.imwrite(str(output_path), frame):
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "backend": "opencv_v4l2",
            "requested_mode": requested_capture_mode,
            "property_requests": property_requests,
            "negotiated_mode": negotiated_mode,
            "mode_status": mode_status,
            "mode_mismatches": mismatches,
            "error": f"Could not write captured frame: {output_path}",
        }

    size_bytes = output_path.stat().st_size if output_path.exists() else 0
    if size_bytes <= 0:
        output_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "backend": "opencv_v4l2",
            "requested_mode": requested_capture_mode,
            "property_requests": property_requests,
            "negotiated_mode": negotiated_mode,
            "mode_status": mode_status,
            "mode_mismatches": mismatches,
            "error": "Captured frame artifact is empty.",
        }

    warning = None
    if mismatches:
        warning = (
            "Requested camera mode was unavailable; captured using the "
            "negotiated fallback mode."
        )

    return {
        "ok": True,
        "device": str(resolved_device),
        "role": camera.get("role") or role,
        "camera": camera,
        "backend": "opencv_v4l2",
        "requested_mode": requested_capture_mode,
        "property_requests": property_requests,
        "negotiated_mode": negotiated_mode,
        "mode_status": mode_status,
        "mode_mismatches": mismatches,
        "warning": warning,
        "timeout_seconds": timeout_seconds,
        "elapsed_seconds": elapsed_seconds,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "file_path": str(output_path),
        "relative_path": str(output_path.relative_to(PROJECT_ROOT)),
        "size_bytes": size_bytes,
    }
