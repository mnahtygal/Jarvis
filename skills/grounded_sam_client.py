"""Lightweight Jarvis client for the isolated Grounded SAM worker."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.grounded_sam_contract import (
    BACKEND_NAME,
    BACKEND_VERSION,
    grounded_sam_failure,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "vision_backends.json"


@dataclass(frozen=True)
class GroundedSamClientConfig:
    enabled: bool
    worker_url: str
    request_timeout_seconds: float
    prompt_max_length: int
    allowed_input_root: Path
    artifact_root: Path


def load_grounded_sam_config(path: Path = CONFIG_PATH) -> GroundedSamClientConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = (payload.get("backends") or {}).get(BACKEND_NAME) or {}

    def project_path(value: Any, default: str) -> Path:
        candidate = Path(str(value or default)).expanduser()
        return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate

    return GroundedSamClientConfig(
        enabled=raw.get("enabled") is True,
        worker_url=str(raw.get("worker_url") or "http://127.0.0.1:8092").rstrip("/"),
        request_timeout_seconds=float(raw.get("request_timeout_seconds") or 180.0),
        prompt_max_length=int(raw.get("prompt_max_length") or 256),
        allowed_input_root=project_path(raw.get("allowed_input_root"), "runtime/camera/mat_analysis"),
        artifact_root=project_path(raw.get("artifact_root"), "runtime/camera/mat_analysis/grounded_sam"),
    )


def normalize_grounded_sam_prompt(value: Any, *, maximum_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError("A text prompt is required for Grounded SAM.")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise ValueError("Grounded SAM prompt contains unsupported control characters.")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("A nonempty text prompt is required for Grounded SAM.")
    if len(normalized) > maximum_length:
        raise ValueError(f"Grounded SAM prompt must not exceed {maximum_length} characters.")
    return normalized


def validate_grounded_sam_source(raw_path: Any, *, allowed_root: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise FileNotFoundError("A saved source image path is required.")
    requested = Path(raw_path.strip())
    if not requested.is_absolute():
        requested = PROJECT_ROOT / requested
    resolved = requested.resolve()
    try:
        resolved.relative_to(allowed_root.resolve())
    except ValueError as exc:
        raise ValueError("Source image path is outside the allowed Jarvis artifact root.") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"Saved source image does not exist: {resolved}")
    if not resolved.name.endswith("_mat_rectified.jpg"):
        raise ValueError("Grounded SAM requires a saved *_mat_rectified.jpg artifact.")
    try:
        from PIL import Image

        with Image.open(resolved) as image:
            image.verify()
    except Exception as exc:
        raise OSError(f"Saved source image is unreadable: {resolved}") from exc
    return resolved


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except HTTPError as exc:
        try:
            value = json.loads(exc.read().decode("utf-8"))
        except Exception:
            raise URLError(f"Grounded SAM worker returned HTTP {exc.code}.") from exc
    if not isinstance(value, dict):
        raise ValueError("Grounded SAM worker returned a non-object response.")
    return value


def analyze_saved_image_with_grounded_sam(
    image_path: Any,
    prompt: Any,
    *,
    config: GroundedSamClientConfig | None = None,
) -> dict[str, Any]:
    settings = config or load_grounded_sam_config()
    if not settings.enabled:
        return grounded_sam_failure(
            "backend_disabled",
            "Grounded SAM is disabled in config/vision_backends.json.",
        )
    try:
        normalized_prompt = normalize_grounded_sam_prompt(
            prompt, maximum_length=settings.prompt_max_length
        )
    except ValueError as exc:
        return grounded_sam_failure("invalid_prompt", str(exc))
    try:
        source = validate_grounded_sam_source(
            image_path, allowed_root=settings.allowed_input_root
        )
    except FileNotFoundError as exc:
        return grounded_sam_failure(
            "source_image_missing", str(exc), prompt=normalized_prompt
        )
    except (OSError, ValueError) as exc:
        return grounded_sam_failure(
            "source_image_unreadable", str(exc), prompt=normalized_prompt
        )

    from core.measurement import get_active_calibration

    calibration = get_active_calibration(source)
    if not calibration.get("ready"):
        reason = (
            "calibration_provenance_mismatch"
            if calibration.get("validation_mismatches")
            else "calibration_invalid"
        )
        return grounded_sam_failure(
            reason,
            str(calibration.get("error") or "Saved image calibration is invalid."),
            source_image={"path": str(source)},
            prompt=normalized_prompt,
            calibration=calibration,
        )

    payload = {
        "image_path": str(source),
        "provenance_path": calibration.get("provenance_path"),
        "prompt": normalized_prompt,
        "artifact_root": str(settings.artifact_root),
    }
    try:
        result = _post_json(
            f"{settings.worker_url}/v1/analyze",
            payload,
            settings.request_timeout_seconds,
        )
    except (socket.timeout, TimeoutError) as exc:
        return grounded_sam_failure(
            "request_timeout",
            f"Grounded SAM request exceeded {settings.request_timeout_seconds:g} seconds.",
            source_image={"path": str(source)},
            prompt=normalized_prompt,
            calibration=calibration,
        )
    except (URLError, OSError) as exc:
        return grounded_sam_failure(
            "worker_unavailable",
            f"Grounded SAM worker is unavailable: {exc}",
            source_image={"path": str(source)},
            prompt=normalized_prompt,
            calibration=calibration,
        )
    except Exception:
        return grounded_sam_failure(
            "internal_error",
            "Grounded SAM worker returned an invalid response.",
            source_image={"path": str(source)},
            prompt=normalized_prompt,
            calibration=calibration,
        )
    # The worker contract is authoritative, but never permit backend relabeling.
    if result.get("backend") != BACKEND_NAME:
        return grounded_sam_failure(
            "internal_error",
            "Grounded SAM worker returned the wrong backend identity.",
            prompt=normalized_prompt,
            calibration=calibration,
        )
    return result


def get_grounded_sam_health(
    *, config: GroundedSamClientConfig | None = None
) -> dict[str, Any]:
    settings = config or load_grounded_sam_config()
    base = {
        "backend": BACKEND_NAME,
        "backend_version": BACKEND_VERSION,
        "experimental": True,
        "enabled": settings.enabled,
        "worker_reachable": False,
        "dependencies_available": None,
        "model_state": "unavailable" if not settings.enabled else "unloaded",
        "last_load_error": None,
        "busy": False,
    }
    if not settings.enabled:
        return base
    try:
        request = Request(f"{settings.worker_url}/v1/health", method="GET")
        with urlopen(request, timeout=min(settings.request_timeout_seconds, 3.0)) as response:
            payload = json.load(response)
        if isinstance(payload, dict):
            return {**base, **payload, "enabled": True, "worker_reachable": True}
    except Exception as exc:
        return {**base, "last_load_error": f"Worker unavailable: {type(exc).__name__}"}
    return base
