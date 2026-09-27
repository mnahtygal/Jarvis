"""Fixed route labels scoped to a single orchestrated request.

Outside an active trace, instrumentation is a no-op for legacy direct callers.
Tokens restore the enclosing trace for nested requests.
"""

from contextvars import ContextVar, Token


ROUTE_LABELS = frozenset({
    "unknown", "exact_memory", "semantic_memory", "memory_write",
    "runtime_status", "system", "help_docs", "camera_vision", "chat",
    "llm_fallback",
})
_actual_route: ContextVar[str | None] = ContextVar("jarvis_actual_route", default=None)


def begin_route_trace() -> Token:
    return _actual_route.set("unknown")


def set_actual_route(name: str) -> None:
    if name not in ROUTE_LABELS:
        raise ValueError("Unsupported route label")
    if _actual_route.get() is not None:
        _actual_route.set(name)


def get_actual_route() -> str:
    return _actual_route.get() or "unknown"


def reset_route_trace(token: Token) -> None:
    _actual_route.reset(token)
