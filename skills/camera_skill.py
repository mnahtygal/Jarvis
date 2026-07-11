# skills/camera_skill.py

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from core.camera_roles import DEFAULT_CAMERA_ROLE, resolve_camera

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMERA_DEVICE = os.getenv("JARVIS_CAMERA_DEVICE", "")
CAPTURE_DIR = PROJECT_ROOT / "runtime" / "camera"


def capture_snapshot(
    device: str | None = None,
    role: str | None = None,
    timeout_seconds: int = 8,
) -> Dict[str, Any]:
    """Capture one JPEG frame from the configured camera using ffmpeg."""
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

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "video4linux2",
        "-i",
        str(resolved_device),
        "-frames:v",
        "1",
        str(output_path),
    ]

    started_at = time.perf_counter()

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "error": f"Camera capture timed out after {timeout_seconds} seconds.",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "error": "ffmpeg is not installed or is not on PATH.",
        }
    except Exception as error:
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "error": str(error),
        }

    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    size_bytes = output_path.stat().st_size if output_path.exists() else 0

    if result.returncode != 0 or size_bytes <= 0:
        output_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "device": str(resolved_device),
            "role": camera.get("role") or role,
            "camera": camera,
            "elapsed_seconds": elapsed_seconds,
            "returncode": result.returncode,
            "error": (result.stderr or "Camera capture failed.").strip(),
        }

    return {
        "ok": True,
        "device": str(resolved_device),
        "role": camera.get("role") or role,
        "camera": camera,
        "elapsed_seconds": elapsed_seconds,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "file_path": str(output_path),
        "relative_path": str(output_path.relative_to(PROJECT_ROOT)),
        "size_bytes": size_bytes,
    }
