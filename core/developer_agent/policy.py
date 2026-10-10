"""Shared sensitive and protected path policy for developer tools."""

from __future__ import annotations

from pathlib import Path


PROTECTED_MUTATION_FILENAMES = frozenset({
    "audio_pipeline_tester.py",
    "audio_pipeline_tester_jarvis.py",
    "audio_pipeline_tester_jarvis_v2.py",
})


def _is_sensitive_name(name: str) -> bool:
    normalized = name.casefold()
    return (
        normalized.startswith(".env")
        or normalized.endswith((".pem", ".key"))
        or normalized.startswith("credentials")
        or normalized.startswith("secrets")
    )


def is_sensitive_path(path: Path) -> bool:
    """Return whether any path component matches the explicit secret policy."""

    return any(_is_sensitive_name(part) for part in path.parts)


def mutation_protection_code(*paths: Path) -> str | None:
    """Return a stable refusal code for protected mutation targets."""

    for path in paths:
        normalized_parts = tuple(part.casefold() for part in path.parts)
        if ".git" in normalized_parts:
            return "repository_metadata"
        if path.name.casefold() in PROTECTED_MUTATION_FILENAMES:
            return "protected_file"
        if is_sensitive_path(path):
            return "sensitive_file"
    return None
