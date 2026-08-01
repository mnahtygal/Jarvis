"""Thread-safe lazy model lifecycle and single-request admission control."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


MODEL_STATES = {"unloaded", "loading", "ready", "load_failed", "unavailable"}


class ModelLoadFailure(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class LoadedModels:
    value: Any
    device: str
    dtype: str
    dependency_versions: dict[str, str | None]


class ModelRegistry:
    def __init__(self, loader: Callable[[], LoadedModels]) -> None:
        self._loader = loader
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._models: LoadedModels | None = None
        self.state = "unloaded"
        self.load_attempts = 0
        self.last_load_error: str | None = None
        self.last_load_failure_reason: str | None = None
        self.last_load_ms: float | None = None

    @property
    def busy(self) -> bool:
        acquired = self._inference_lock.acquire(blocking=False)
        if acquired:
            self._inference_lock.release()
            return False
        return True

    def acquire_request(self) -> bool:
        return self._inference_lock.acquire(blocking=False)

    def release_request(self) -> None:
        self._inference_lock.release()

    def get_or_load(self) -> tuple[LoadedModels, bool]:
        if self._models is not None and self.state == "ready":
            return self._models, True
        with self._load_lock:
            if self._models is not None and self.state == "ready":
                return self._models, True
            self.state = "loading"
            self.load_attempts += 1
            started = time.perf_counter()
            try:
                loaded = self._loader()
            except ModelLoadFailure as exc:
                self._models = None
                self.state = "unavailable" if exc.reason in {
                    "dependency_missing", "model_unavailable"
                } else "load_failed"
                self.last_load_failure_reason = exc.reason
                self.last_load_error = _safe_error(exc)
                self.last_load_ms = _elapsed_ms(started)
                raise
            except Exception as exc:
                self._models = None
                self.state = "load_failed"
                self.last_load_failure_reason = "model_load_failed"
                self.last_load_error = _safe_error(exc)
                self.last_load_ms = _elapsed_ms(started)
                raise ModelLoadFailure("model_load_failed", "Grounded SAM model loading failed.") from exc
            self._models = loaded
            self.state = "ready"
            self.last_load_error = None
            self.last_load_failure_reason = None
            self.last_load_ms = _elapsed_ms(started)
            return loaded, False

    def health(self) -> dict[str, Any]:
        return {
            "model_state": self.state,
            "last_load_error": self.last_load_error,
            "last_load_failure_reason": self.last_load_failure_reason,
            "load_attempts": self.load_attempts,
            "last_load_ms": self.last_load_ms,
            "busy": self.busy,
            "models_loaded": self._models is not None,
            "device": self._models.device if self._models else None,
            "dtype": self._models.dtype if self._models else None,
            "dependency_versions": self._models.dependency_versions if self._models else {},
        }


def _safe_error(error: BaseException) -> str:
    return f"{type(error).__name__}: {str(error)[:240]}"


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 2)
