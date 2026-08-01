"""Dependency-injected worker orchestration; contains no ML imports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from core.grounded_sam_contract import BACKEND_NAME, BACKEND_VERSION, grounded_sam_failure
from .lifecycle import ModelLoadFailure, ModelRegistry


class GroundedSamWorker:
    def __init__(self, *, registry: ModelRegistry, analyzer: Callable[..., dict[str, Any]],
                 allowed_input_root: Path, artifact_root: Path,
                 dependency_probe: Callable[[], dict[str, Any]]) -> None:
        self.registry = registry
        self.analyzer = analyzer
        self.allowed_input_root = allowed_input_root.resolve()
        self.artifact_root = artifact_root.resolve()
        self.dependency_probe = dependency_probe

    def health(self) -> dict[str, Any]:
        dependencies = self.dependency_probe()
        return {
            "backend": BACKEND_NAME, "backend_version": BACKEND_VERSION,
            "experimental": True, "worker_reachable": True,
            "dependencies_available": dependencies.get("available"),
            "reported_dependencies": dependencies.get("versions", {}),
            **self.registry.health(),
        }

    def analyze(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return grounded_sam_failure("internal_error", "Worker request must be a JSON object.")
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return grounded_sam_failure(
                "invalid_prompt", "Worker requires a normalized text prompt."
            )
        if len(" ".join(prompt.split())) > 256:
            return grounded_sam_failure(
                "invalid_prompt", "Worker prompt must not exceed 256 characters."
            )
        image_path = payload.get("image_path")
        if not isinstance(image_path, str) or not image_path.strip():
            return grounded_sam_failure(
                "source_image_missing", "Saved source image path is required.",
                prompt=" ".join(prompt.split()),
            )
        resolved_image = Path(image_path).resolve()
        try:
            resolved_image.relative_to(self.allowed_input_root)
        except ValueError:
            return grounded_sam_failure(
                "source_image_unreadable", "Source image path is outside the worker allow-list.",
                prompt=" ".join(prompt.split()),
            )
        if not resolved_image.is_file():
            return grounded_sam_failure(
                "source_image_missing", f"Saved source image does not exist: {resolved_image}",
                prompt=" ".join(prompt.split()),
            )
        if not resolved_image.name.endswith("_mat_rectified.jpg"):
            return grounded_sam_failure(
                "source_image_unreadable", "Worker accepts only saved *_mat_rectified.jpg artifacts.",
                prompt=" ".join(prompt.split()),
            )
        if not self.registry.acquire_request():
            return grounded_sam_failure("worker_busy", "Grounded SAM worker is busy.")
        try:
            try:
                models, cache_hit = self.registry.get_or_load()
            except ModelLoadFailure as exc:
                return grounded_sam_failure(
                    exc.reason, str(exc),
                    model_load_timing_ms={"total": self.registry.last_load_ms, "cache_hit": False,
                                          "attempt": self.registry.load_attempts},
                    diagnostics={"retryable": True},
                )
            try:
                return self.analyzer(
                    payload=payload, models=models,
                    allowed_input_root=self.allowed_input_root,
                    artifact_root=self.artifact_root,
                    model_load_timing_ms={
                        "total": self.registry.last_load_ms if not cache_hit else 0.0,
                        "cache_hit": cache_hit, "attempt": self.registry.load_attempts,
                    },
                )
            except Exception:
                return grounded_sam_failure(
                    "internal_error", "Unexpected Grounded SAM worker failure.",
                    diagnostics={"exception_suppressed": True},
                )
        finally:
            self.registry.release_request()
