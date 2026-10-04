"""Deterministic request classification for the Brain v2 decision layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.router import normalize_text_for_routing


class RequestIntent(str, Enum):
    CONVERSATION = "conversation"
    FACTUAL_QUESTION = "factual_question"
    MEMORY_RECALL = "memory_recall"
    MEMORY_WRITE = "memory_write"
    RUNTIME_STATUS = "runtime_status"
    SYSTEM_COMMAND = "system_command"
    CAMERA_OR_VISION = "camera_or_vision"
    HELP_OR_DOCS = "help_or_docs"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ContextPolicy:
    use_exact_memory: bool
    use_semantic_memory: bool
    use_recent_history: bool
    use_last_topic: bool
    reason: str


@dataclass(frozen=True)
class RequestClassification:
    intent: RequestIntent
    context_policy: ContextPolicy


def _policy_for(intent: RequestIntent) -> ContextPolicy:
    policies = {
        RequestIntent.CONVERSATION: ContextPolicy(False, True, True, True, "conversation request"),
        RequestIntent.FACTUAL_QUESTION: ContextPolicy(False, False, False, False, "general factual question"),
        RequestIntent.MEMORY_RECALL: ContextPolicy(True, True, True, False, "memory recall request"),
        RequestIntent.MEMORY_WRITE: ContextPolicy(False, False, False, False, "memory write request"),
        RequestIntent.RUNTIME_STATUS: ContextPolicy(False, False, False, False, "runtime command"),
        RequestIntent.SYSTEM_COMMAND: ContextPolicy(False, False, False, False, "system command"),
        RequestIntent.CAMERA_OR_VISION: ContextPolicy(False, False, False, False, "camera or vision command"),
        RequestIntent.HELP_OR_DOCS: ContextPolicy(False, False, False, False, "help or documentation request"),
        RequestIntent.UNKNOWN: ContextPolicy(
            False,
            True,
            True,
            True,
            "general request with conversational context",
        ),
    }
    return policies[intent]


def _is_exact_memory_recall(text: str) -> bool:
    return (
        ("database" in text and ("prefer" in text or "preferred" in text))
        or "what is my wife s name" in text
        or "where do i work" in text
        or "what is my favorite ship" in text
        or "what is my favorite cruise ship" in text
    )


def _is_semantic_memory_recall(text: str) -> bool:
    return (
        text.startswith("what did i tell you about ")
        or text.startswith("what do you remember about ")
        or text.startswith("what have we discussed about ")
        or text.startswith("what did we discuss about ")
        or text.startswith("what do you remember")
    )


def _is_follow_up(text: str) -> bool:
    phrases = (
        "how is it different", "how is that different", "what about that",
        "what about it", "tell me more", "explain more", "why is that",
        "how does it work", "compare it",
    )
    return any(phrase in text for phrase in phrases)


def _is_memory_write(text: str) -> bool:
    return (
        text.startswith(("remember", "note", "save", "update my ", "forget that "))
        or (text.startswith("my ") and " is " in text)
        or text.startswith(("i work at ", "i work for ", "i prefer ", "i like "))
    )


def _is_runtime_status(text: str) -> bool:
    return (
        "brain status" in text
        or "brain health" in text
        or "brain v2 status" in text
        or "jarvis health" in text
        or text in {"health check", "status", "system status"}
        or ("model" in text and ("using" in text or "running" in text))
        or ("llm" in text and ("using" in text or "running" in text))
        or ("camera" in text and ("active" in text or "using" in text))
    )


def _is_camera_or_vision(text: str) -> bool:
    return any(term in text for term in ("camera", "vision", "scan mat", "snapshot", "capture"))


def _is_help_or_docs(text: str) -> bool:
    return text in {
        "help", "jarvis help", "what can you do", "what can jarvis do",
        "show commands", "list commands", "capabilities", "jarvis capabilities",
        "brain capabilities",
        "jarvis docs", "jarvis documentation", "show docs", "show documentation",
        "where are the docs", "where is the documentation", "open docs", "documentation",
    }


def _is_system_command(text: str) -> bool:
    return (
        text.startswith(("turn on ", "turn off ", "restart ", "shutdown "))
        or text in {"what time is it", "what is the time", "what is the date"}
        or any(term in text for term in ("cpu", "disk usage", "system information"))
    )


def _is_factual_question(text: str) -> bool:
    return text.startswith(("what is ", "what are ", "explain ", "define ", "how does ", "why does "))


def classify_request(command: str) -> RequestClassification:
    """Classify a command without models, databases, or external tools."""

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    text = normalize_text_for_routing(command)
    if _is_exact_memory_recall(text):
        intent = RequestIntent.MEMORY_RECALL
        policy = ContextPolicy(True, False, False, False, "memory recall request")
    elif _is_semantic_memory_recall(text):
        intent = RequestIntent.MEMORY_RECALL
        policy = _policy_for(intent)
    elif _is_follow_up(text):
        intent = RequestIntent.CONVERSATION
        policy = ContextPolicy(False, True, True, True, "follow-up conversation")
    elif _is_memory_write(text):
        intent = RequestIntent.MEMORY_WRITE
        policy = _policy_for(intent)
    elif _is_runtime_status(text):
        intent = RequestIntent.RUNTIME_STATUS
        policy = _policy_for(intent)
    elif _is_camera_or_vision(text):
        intent = RequestIntent.CAMERA_OR_VISION
        policy = _policy_for(intent)
    elif _is_help_or_docs(text):
        intent = RequestIntent.HELP_OR_DOCS
        policy = _policy_for(intent)
    elif _is_system_command(text):
        intent = RequestIntent.SYSTEM_COMMAND
        policy = _policy_for(intent)
    elif text in {"hello", "hi", "hey", "hey jarvis", "hello jarvis"} or "how are you" in text:
        intent = RequestIntent.CONVERSATION
        policy = _policy_for(intent)
    elif _is_factual_question(text):
        intent = RequestIntent.FACTUAL_QUESTION
        policy = _policy_for(intent)
    else:
        intent = RequestIntent.UNKNOWN
        policy = _policy_for(intent)

    return RequestClassification(intent=intent, context_policy=policy)
