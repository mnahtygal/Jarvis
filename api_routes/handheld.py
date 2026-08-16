from __future__ import annotations

import hmac
import json
import os
import threading
import time
import unicodedata
from collections import deque
from typing import Any

from flask import Blueprint, jsonify, request

from skills.handheld_chat_skill import (
    HandheldChatResult,
    HandheldModelError,
    HandheldModelTimeout,
    generate_handheld_response,
)


handheld_blueprint = Blueprint("handheld", __name__)

TOKEN_ENVIRONMENT_VARIABLE = "JARVIS_HANDHELD_TOKEN"
MAX_AUTHORIZATION_LENGTH = 512
MAX_REQUEST_BYTES = 768
MAX_PROMPT_BYTES = 256
RATE_LIMIT_REQUESTS = 6
RATE_LIMIT_WINDOW_SECONDS = 60.0

_request_slot = threading.BoundedSemaphore(value=1)
_rate_lock = threading.Lock()
_accepted_request_times: deque[float] = deque()


class _DuplicateJsonKey(ValueError):
    pass


def _error(status: int, code: str, message: str):
    return jsonify({
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }), status


def _get_server_token() -> str:
    return os.getenv(TOKEN_ENVIRONMENT_VARIABLE, "")


def _authorization_is_valid(expected_token: str) -> bool:
    authorization = request.headers.get("Authorization", "")
    presented_token = ""

    if len(authorization) <= MAX_AUTHORIZATION_LENGTH:
        scheme, separator, value = authorization.partition(" ")
        if (
            scheme == "Bearer"
            and separator
            and value
            and value == value.strip()
            and not any(character.isspace() for character in value)
        ):
            presented_token = value

    try:
        return hmac.compare_digest(
            presented_token.encode("utf-8"),
            expected_token.encode("utf-8"),
        )
    except UnicodeEncodeError:
        return False


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey
        result[key] = value
    return result


def _parse_request_body(raw_body: bytes) -> dict[str, Any] | None:
    try:
        decoded = raw_body.decode("utf-8")
        payload = json.loads(
            decoded,
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey):
        return None

    return payload if isinstance(payload, dict) else None


def _prompt_is_supported(prompt: str) -> bool:
    for character in prompt:
        if unicodedata.category(character) == "Cc" and character not in "\n\r\t":
            return False
    return True


def _claim_rate_limit_slot(now: float) -> bool:
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        while _accepted_request_times and _accepted_request_times[0] <= cutoff:
            _accepted_request_times.popleft()
        if len(_accepted_request_times) >= RATE_LIMIT_REQUESTS:
            return False
        _accepted_request_times.append(now)
        return True


@handheld_blueprint.post("/handheld/v1/chat")
def handheld_chat():
    expected_token = _get_server_token()
    if not expected_token:
        return _error(503, "not_configured", "Handheld chat is not configured.")

    if not _authorization_is_valid(expected_token):
        return _error(401, "unauthorized", "Request could not be authorized.")

    if request.mimetype != "application/json":
        return _error(415, "unsupported_media_type", "Content-Type must be application/json.")

    content_length = request.content_length
    if content_length is None:
        return _error(411, "length_required", "Content-Length is required.")
    if content_length > MAX_REQUEST_BYTES:
        return _error(413, "request_too_large", "Request body is too large.")
    if content_length <= 0:
        return _error(400, "invalid_request", "Request body must be a JSON object.")

    raw_body = request.get_data(cache=False)
    if len(raw_body) > MAX_REQUEST_BYTES:
        return _error(413, "request_too_large", "Request body is too large.")
    if len(raw_body) != content_length:
        return _error(400, "invalid_request", "Request body is invalid.")

    payload = _parse_request_body(raw_body)
    if payload is None:
        return _error(400, "invalid_request", "Request body must be a JSON object.")
    if set(payload) != {"prompt"}:
        return _error(400, "invalid_request", "Request must contain only prompt.")

    prompt_value = payload["prompt"]
    if not isinstance(prompt_value, str):
        return _error(400, "invalid_request", "Prompt must be text.")
    if not _prompt_is_supported(prompt_value):
        return _error(400, "invalid_request", "Prompt contains unsupported control characters.")

    prompt = prompt_value.strip()
    if not prompt:
        return _error(400, "invalid_request", "Prompt must not be empty.")
    try:
        prompt_length = len(prompt.encode("utf-8"))
    except UnicodeEncodeError:
        return _error(400, "invalid_request", "Prompt contains unsupported text.")
    if prompt_length > MAX_PROMPT_BYTES:
        return _error(400, "invalid_request", "Prompt is too long.")

    if not _request_slot.acquire(blocking=False):
        return _error(429, "busy", "Another handheld request is already running.")

    try:
        if not _claim_rate_limit_slot(time.monotonic()):
            return _error(429, "rate_limited", "Handheld request rate limit exceeded.")

        try:
            result: HandheldChatResult = generate_handheld_response(prompt)
        except HandheldModelTimeout:
            return _error(504, "model_timeout", "Jarvis did not respond in time.")
        except HandheldModelError:
            return _error(502, "model_error", "Jarvis could not complete the request.")
        except Exception:
            return _error(502, "model_error", "Jarvis could not complete the request.")

        return jsonify({
            "ok": True,
            "response": result.response,
            "truncated": result.truncated,
        })
    finally:
        _request_slot.release()
