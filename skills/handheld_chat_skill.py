from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import requests

from skills.llama_cpp_skill import LLAMA_CPP_URL, strip_thinking
from skills.model_runtime import get_active_model_id


HANDHELD_MODEL_TIMEOUT_SECONDS = 60
HANDHELD_MODEL_MAX_TOKENS = 256
HANDHELD_RESPONSE_MAX_BYTES = 2048
HANDHELD_SYSTEM_PROMPT = (
    "You are Jarvis, a local text assistant for a handheld console. "
    "Answer the user's question directly, clearly, and concisely. "
    "Do not claim to operate devices, cameras, voice systems, files, memory, "
    "tools, or external services. Do not reveal internal reasoning."
)


class HandheldModelTimeout(Exception):
    """The local model did not respond before the handheld deadline."""


class HandheldModelError(Exception):
    """The local model returned an unusable response or transport failure."""


@dataclass(frozen=True)
class HandheldChatResult:
    response: str
    truncated: bool


def _bounded_utf8(value: str, maximum_bytes: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value, False

    bounded = encoded[:maximum_bytes].decode("utf-8", errors="ignore")
    return bounded, True


def _extract_model_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""

    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        content = message.get("reasoning_content")
    return content if isinstance(content, str) else ""


def generate_handheld_response(prompt: str) -> HandheldChatResult:
    payload = {
        "model": get_active_model_id(),
        "messages": [
            {"role": "system", "content": HANDHELD_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": HANDHELD_MODEL_MAX_TOKENS,
        "stream": False,
    }

    try:
        model_response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=HANDHELD_MODEL_TIMEOUT_SECONDS,
        )
        model_response.raise_for_status()
        response_payload = model_response.json()
    except requests.exceptions.Timeout as error:
        raise HandheldModelTimeout from error
    except (requests.exceptions.RequestException, ValueError) as error:
        raise HandheldModelError from error

    response_text = strip_thinking(_extract_model_text(response_payload)).strip()
    if not response_text:
        raise HandheldModelError

    bounded_response, truncated = _bounded_utf8(
        response_text,
        HANDHELD_RESPONSE_MAX_BYTES,
    )
    return HandheldChatResult(response=bounded_response, truncated=truncated)


def generate_handheld_conversation_response(
    completed_messages: Sequence[tuple[str, str]],
    prompt: str,
) -> HandheldChatResult:
    messages = [{"role": "system", "content": HANDHELD_SYSTEM_PROMPT}]
    messages.extend(
        {"role": role, "content": content}
        for role, content in completed_messages
    )
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": get_active_model_id(),
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": HANDHELD_MODEL_MAX_TOKENS,
        "stream": False,
    }

    try:
        model_response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=HANDHELD_MODEL_TIMEOUT_SECONDS,
        )
        model_response.raise_for_status()
        response_payload = model_response.json()
    except requests.exceptions.Timeout as error:
        raise HandheldModelTimeout from error
    except (requests.exceptions.RequestException, ValueError) as error:
        raise HandheldModelError from error

    response_text = strip_thinking(_extract_model_text(response_payload)).strip()
    if not response_text:
        raise HandheldModelError

    bounded_response, truncated = _bounded_utf8(
        response_text,
        HANDHELD_RESPONSE_MAX_BYTES,
    )
    return HandheldChatResult(response=bounded_response, truncated=truncated)
