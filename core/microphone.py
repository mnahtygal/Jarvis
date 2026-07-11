from __future__ import annotations

import os
import subprocess
from typing import Any

PREFERRED_MICROPHONE_NAME = "Samson Q2U Microphone"
PREFERRED_PIPEWIRE_SOURCE = (
    "alsa_input.usb-Samson_Technologies_Samson_Q2U_Microphone-00.iec958-stereo"
)
MICROPHONE_HINTS = ["samson", "q2u"]
CAMERA_MIC_HINTS = ["insta360", "logitech", "c920", "webcam", "camera"]


def get_microphone_status() -> dict[str, Any]:
    sources = list_audio_sources()
    preferred = resolve_preferred_microphone(sources)
    fallback = resolve_fallback_microphone(sources)
    env_source = os.getenv("JARVIS_MIC_SOURCE")

    resolved = env_source or (preferred.get("name") if preferred else None) or (
        fallback.get("name") if fallback else None
    )

    return {
        "preferred_microphone": PREFERRED_MICROPHONE_NAME,
        "preferred_source": PREFERRED_PIPEWIRE_SOURCE,
        "resolved_microphone": resolved,
        "available": preferred is not None,
        "using_preferred": bool(preferred and resolved == preferred.get("name")),
        "fallback_microphone": None if preferred else fallback,
        "sources": sources,
    }


def get_preferred_microphone_source() -> str | None:
    env_source = os.getenv("JARVIS_MIC_SOURCE")
    if env_source:
        return env_source
    status = get_microphone_status()
    return status.get("resolved_microphone")


def list_audio_sources() -> list[dict[str, Any]]:
    text = _run_command(["pactl", "list", "short", "sources"])
    sources = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sources.append({
            "id": parts[0],
            "name": parts[1],
            "driver": parts[2] if len(parts) > 2 else None,
            "description": line.strip(),
        })
    return sources


def resolve_preferred_microphone(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    for source in sources:
        haystack = f"{source.get('name', '')} {source.get('description', '')}".lower()
        if all(hint in haystack for hint in MICROPHONE_HINTS):
            return source
    return None


def resolve_fallback_microphone(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    for source in sources:
        haystack = f"{source.get('name', '')} {source.get('description', '')}".lower()
        if any(hint in haystack for hint in CAMERA_MIC_HINTS):
            continue
        if source.get("name"):
            return source
    return sources[0] if sources else None


def _run_command(command: list[str], timeout: float = 3.0) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""
