"""Lightweight Jarvis client for the isolated Grounded SAM worker."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from core.grounded_sam_contract import (
    BACKEND_NAME,
    BACKEND_VERSION,
    grounded_sam_failure,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "vision_backends.json"
SAVED_IMAGE_ID_PATTERN = re.compile(r"^gsi_[0-9a-f]{64}$")


class SavedImageIdError(ValueError):
    def __init__(self, failure_reason: str, message: str) -> None:
        super().__init__(message)
        self.failure_reason = failure_reason


@dataclass(frozen=True)
class GroundedSamClientConfig:
    enabled: bool
    worker_url: str
    request_timeout_seconds: float
    prompt_max_length: int
    allowed_input_root: Path
    artifact_root: Path


def is_loopback_host(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def validate_grounded_sam_worker_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Grounded SAM worker_url must be a nonempty HTTP URL.")
    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Grounded SAM worker_url is malformed.") from exc
    if parsed.scheme != "http":
        raise ValueError("Grounded SAM worker_url must use the http scheme.")
    if not parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise ValueError("Grounded SAM worker_url must not contain credentials.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Grounded SAM worker_url must not contain a path, query, or fragment.")
    if not is_loopback_host(parsed.hostname):
        raise ValueError("Grounded SAM worker_url must use a loopback-only host.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Grounded SAM worker_url port is invalid.")
    return urlunsplit(("http", parsed.netloc, "", "", ""))


def load_grounded_sam_config(path: Path = CONFIG_PATH) -> GroundedSamClientConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = (payload.get("backends") or {}).get(BACKEND_NAME) or {}

    def project_path(value: Any, default: str) -> Path:
        candidate = Path(str(value or default)).expanduser()
        return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate

    allowed_input_root = project_path(
        raw.get("allowed_input_root"), "runtime/camera/mat_analysis"
    ).resolve()
    artifact_root = project_path(
        raw.get("artifact_root"), "runtime/camera/mat_analysis/grounded_sam"
    ).resolve()
    try:
        artifact_root.relative_to(allowed_input_root)
    except ValueError as exc:
        raise ValueError(
            "Grounded SAM artifact_root must be beneath allowed_input_root."
        ) from exc

    return GroundedSamClientConfig(
        enabled=raw.get("enabled") is True,
        worker_url=validate_grounded_sam_worker_url(
            raw.get("worker_url") or "http://127.0.0.1:8092"
        ),
        request_timeout_seconds=float(raw.get("request_timeout_seconds") or 180.0),
        prompt_max_length=int(raw.get("prompt_max_length") or 256),
        allowed_input_root=allowed_input_root,
        artifact_root=artifact_root,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _saved_image_id(
    image_path: Path, metadata_path: Path, *, allowed_root: Path
) -> str:
    relative = image_path.relative_to(allowed_root).as_posix()
    identity = "\0".join((relative, _sha256(image_path), _sha256(metadata_path)))
    return f"gsi_{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def _inventory_timestamp(metadata: dict[str, Any], image_path: Path) -> tuple[datetime, str]:
    created_at = metadata.get("created_at")
    if isinstance(created_at, str):
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc), "provenance_created_at"
        except ValueError:
            pass
    return datetime.fromtimestamp(image_path.stat().st_mtime, timezone.utc), "filesystem_mtime"


def _validated_saved_image_entry(
    candidate: Path, *, allowed_root: Path
) -> tuple[dict[str, Any], datetime] | None:
    root = allowed_root.resolve()
    metadata_candidate = candidate.with_suffix(".metadata.json")
    if candidate.is_symlink() or metadata_candidate.is_symlink():
        return None
    try:
        image_path = candidate.resolve(strict=True)
        image_path.relative_to(root)
        metadata_path = metadata_candidate.resolve(strict=True)
        metadata_path.relative_to(root)
    except (FileNotFoundError, OSError, ValueError):
        return None
    if not image_path.name.endswith("_mat_rectified.jpg"):
        return None
    try:
        from PIL import Image
        from experiments.grounded_sam_backend.provenance import load_validated_provenance

        with Image.open(image_path) as image:
            width, height = image.size
            image.verify()
        metadata, calibration = load_validated_provenance(
            image_path,
            metadata_path,
            image_width=width,
            image_height=height,
        )
        image_id = _saved_image_id(image_path, metadata_path, allowed_root=root)
        timestamp, timestamp_source = _inventory_timestamp(metadata, image_path)
    except Exception:
        return None
    captured_at = timestamp.isoformat().replace("+00:00", "Z")
    entry = {
        "image_id": image_id,
        "display_name": f"C920 rectified scan · {captured_at}",
        "captured_at": captured_at,
        "timestamp_source": timestamp_source,
        "width": width,
        "height": height,
        "logical_camera_id": metadata.get("logical_camera_id"),
        "camera_role": metadata.get("camera_role"),
        "calibration_profile_id": metadata.get("calibration_profile_id"),
        "calibration_confidence": calibration.get("confidence"),
        "geometry_version": metadata.get("geometry_version"),
        "homography_version": metadata.get("homography_version"),
        "provenance_state": "validated",
    }
    return entry, timestamp


def list_grounded_sam_saved_images(
    *, config: GroundedSamClientConfig | None = None
) -> list[dict[str, Any]]:
    settings = config or load_grounded_sam_config()
    root = settings.allowed_input_root.resolve()
    if not root.is_dir():
        return []
    entries = []
    for candidate in root.rglob("*_mat_rectified.jpg"):
        validated = _validated_saved_image_entry(candidate, allowed_root=root)
        if validated is not None:
            entries.append(validated)
    entries.sort(key=lambda item: (item[1], item[0]["image_id"]), reverse=True)
    return [entry for entry, _timestamp in entries]


def resolve_grounded_sam_image_id(
    image_id: Any, *, config: GroundedSamClientConfig | None = None
) -> Path:
    if not isinstance(image_id, str) or not SAVED_IMAGE_ID_PATTERN.fullmatch(image_id):
        raise SavedImageIdError(
            "source_image_unreadable", "Grounded SAM saved image ID is malformed."
        )
    settings = config or load_grounded_sam_config()
    matches = []
    root = settings.allowed_input_root.resolve()
    if root.is_dir():
        for candidate in root.rglob("*_mat_rectified.jpg"):
            validated = _validated_saved_image_entry(candidate, allowed_root=root)
            if validated is not None and validated[0]["image_id"] == image_id:
                matches.append(candidate.resolve())
    if not matches:
        raise SavedImageIdError(
            "source_image_missing", "Grounded SAM saved image ID is unknown or stale."
        )
    if len(matches) != 1:
        raise SavedImageIdError(
            "source_image_unreadable", "Grounded SAM saved image ID is ambiguous."
        )
    return validate_grounded_sam_source(str(matches[0]), allowed_root=root)


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


def validate_grounded_sam_provenance(image_path: Path) -> dict[str, Any]:
    from PIL import Image
    from experiments.grounded_sam_backend.provenance import load_validated_provenance

    metadata_path = image_path.with_suffix(".metadata.json")
    with Image.open(image_path) as image:
        width, height = image.size
        image.verify()
    _metadata, calibration = load_validated_provenance(
        image_path,
        metadata_path,
        image_width=width,
        image_height=height,
    )
    return calibration


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
    try:
        worker_url = validate_grounded_sam_worker_url(settings.worker_url)
    except ValueError:
        return grounded_sam_failure(
            "worker_unavailable", "Grounded SAM worker configuration is not loopback-only."
        )
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

    try:
        calibration = validate_grounded_sam_provenance(source)
    except FileNotFoundError as exc:
        return grounded_sam_failure(
            "calibration_invalid",
            str(exc),
            source_image={"path": str(source)},
            prompt=normalized_prompt,
        )
    except Exception as exc:
        return grounded_sam_failure(
            "calibration_provenance_mismatch",
            str(exc) or "Saved image calibration provenance is invalid.",
            source_image={"path": str(source)},
            prompt=normalized_prompt,
        )

    payload = {
        "image_path": str(source),
        "provenance_path": calibration.get("provenance_path"),
        "prompt": normalized_prompt,
        "artifact_root": str(settings.artifact_root),
    }
    try:
        result = _post_json(
            f"{worker_url}/v1/analyze",
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
        worker_url = validate_grounded_sam_worker_url(settings.worker_url)
    except ValueError:
        return {
            **base,
            "model_state": "unavailable",
            "last_load_error": "Worker configuration is not loopback-only.",
        }
    try:
        request = Request(f"{worker_url}/v1/health", method="GET")
        with urlopen(request, timeout=min(settings.request_timeout_seconds, 3.0)) as response:
            payload = json.load(response)
        if isinstance(payload, dict):
            return {**base, **payload, "enabled": True, "worker_reachable": True}
    except Exception as exc:
        return {**base, "last_load_error": f"Worker unavailable: {type(exc).__name__}"}
    return base
