"""Request-scoped Brain v2 context used during orchestration."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrainRequestContext:
    """Context propagated only for the lifetime of one Brain request."""

    context_policy: Any


_ACTIVE_REQUEST_CONTEXT: ContextVar[BrainRequestContext | None] = ContextVar(
    "jarvis_active_brain_request_context",
    default=None,
)


def set_active_request_context(context: BrainRequestContext) -> Token:
    return _ACTIVE_REQUEST_CONTEXT.set(context)


def reset_active_request_context(token: Token) -> None:
    _ACTIVE_REQUEST_CONTEXT.reset(token)


def get_active_request_context() -> BrainRequestContext | None:
    return _ACTIVE_REQUEST_CONTEXT.get()
