from __future__ import annotations

import hmac
import json
import os
import re
import threading
import time
import unicodedata
from collections import deque
from typing import Any

from flask import Blueprint, Response, jsonify, request

from core.handheld_sessions import (
    HandheldReplay,
    HandheldRequestClaim,
    HandheldSessionError,
    HandheldSessionStore,
)
from skills.handheld_chat_skill import (
    HandheldChatResult,
    HandheldModelError,
    HandheldModelTimeout,
    generate_handheld_conversation_response,
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
_session_store = HandheldSessionStore()
_HANDHELD_ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")


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


def _v2_error(status: int, code: str, message: str):
    return jsonify({
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "retryable": False,
        },
    }), status


def _v2_success(payload: dict[str, Any]) -> Response:
    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return Response(body, status=200, content_type="application/json; charset=utf-8")


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


_SESSION_ERROR_RESPONSES = {
    "request_in_progress": (409, "A matching request is already running."),
    "session_unavailable": (409, "The session is temporarily unavailable."),
    "request_conflict": (409, "The request identifier conflicts with prior use."),
    "turn_conflict": (409, "The requested turn is out of order."),
    "session_capacity": (429, "Handheld session capacity is currently full."),
}


def _session_error(error: HandheldSessionError):
    status, message = _SESSION_ERROR_RESPONSES[error.code]
    return _v2_error(status, error.code, message)


def _v2_request_payload() -> dict[str, Any] | tuple[Any, int]:
    if request.mimetype != "application/json":
        return _v2_error(
            400,
            "invalid_request",
            "Content-Type must be application/json.",
        )

    content_length = request.content_length
    if content_length is None:
        return _v2_error(400, "invalid_request", "Content-Length is required.")
    if content_length <= 0:
        return _v2_error(400, "invalid_request", "Request body must be a JSON object.")
    if content_length > MAX_REQUEST_BYTES:
        return _v2_error(400, "invalid_request", "Request body is too large.")

    raw_body = request.get_data(cache=False)
    if len(raw_body) > MAX_REQUEST_BYTES:
        return _v2_error(400, "invalid_request", "Request body is too large.")
    if len(raw_body) != content_length:
        return _v2_error(400, "invalid_request", "Request body is invalid.")
    payload = _parse_request_body(raw_body)
    if payload is None:
        return _v2_error(400, "invalid_request", "Request body must be a JSON object.")
    return payload


def _normalized_v2_prompt(value: Any) -> str | None:
    if not isinstance(value, str) or not _prompt_is_supported(value):
        return None
    prompt = value.strip()
    if not prompt:
        return None
    try:
        prompt_length = len(prompt.encode("utf-8"))
    except UnicodeEncodeError:
        return None
    return prompt if prompt_length <= MAX_PROMPT_BYTES else None


@handheld_blueprint.post("/handheld/v2/chat")
def handheld_chat_v2():
    expected_token = _get_server_token()
    if not expected_token:
        return _v2_error(503, "not_configured", "Handheld chat is not configured.")
    if not _authorization_is_valid(expected_token):
        return _v2_error(401, "unauthorized", "Request could not be authorized.")

    parsed = _v2_request_payload()
    if not isinstance(parsed, dict):
        return parsed
    operation = parsed.get("operation")

    if operation == "reset":
        if set(parsed) != {"operation", "session_id"}:
            return _v2_error(400, "invalid_request", "Reset request fields are invalid.")
        session_id = parsed["session_id"]
        if not isinstance(session_id, str) or not _HANDHELD_ID_PATTERN.fullmatch(session_id):
            return _v2_error(400, "invalid_request", "Session identifier is invalid.")
        if not _claim_rate_limit_slot(time.monotonic()):
            return _v2_error(429, "rate_limited", "Handheld request rate limit exceeded.")
        try:
            _session_store.reset(session_id)
        except HandheldSessionError as error:
            return _session_error(error)
        return _v2_success({"ok": True, "reset": True})

    if operation != "message" or set(parsed) != {
        "operation",
        "session_id",
        "request_id",
        "turn",
        "prompt",
    }:
        return _v2_error(400, "invalid_request", "Message request fields are invalid.")

    session_id = parsed["session_id"]
    request_id = parsed["request_id"]
    turn = parsed["turn"]
    prompt = _normalized_v2_prompt(parsed["prompt"])
    if not isinstance(session_id, str) or not _HANDHELD_ID_PATTERN.fullmatch(session_id):
        return _v2_error(400, "invalid_request", "Session identifier is invalid.")
    if not isinstance(request_id, str) or not _HANDHELD_ID_PATTERN.fullmatch(request_id):
        return _v2_error(400, "invalid_request", "Request identifier is invalid.")
    if isinstance(turn, bool) or not isinstance(turn, int) or not 1 <= turn <= 6:
        return _v2_error(400, "invalid_request", "Turn is invalid.")
    if prompt is None:
        return _v2_error(400, "invalid_request", "Prompt is invalid.")

    try:
        claim = _session_store.begin_message(session_id, request_id, turn, prompt)
    except HandheldSessionError as error:
        return _session_error(error)

    if isinstance(claim, HandheldReplay):
        if not _claim_rate_limit_slot(time.monotonic()):
            return _v2_error(429, "rate_limited", "Handheld request rate limit exceeded.")
        return _v2_success({
            "ok": True,
            "turn": claim.turn,
            "response": claim.response,
            "truncated": claim.truncated,
            "replayed": True,
        })

    assert isinstance(claim, HandheldRequestClaim)
    if not _request_slot.acquire(blocking=False):
        _session_store.abort(claim)
        return _v2_error(409, "session_unavailable", "The model is currently unavailable.")

    try:
        if not _claim_rate_limit_slot(time.monotonic()):
            _session_store.abort(claim)
            return _v2_error(429, "rate_limited", "Handheld request rate limit exceeded.")
        try:
            result = generate_handheld_conversation_response(claim.messages, prompt)
            completed = _session_store.commit(claim, result.response, result.truncated)
        except HandheldModelTimeout:
            _session_store.abort(claim)
            return _v2_error(504, "model_timeout", "Jarvis did not respond in time.")
        except HandheldModelError:
            _session_store.abort(claim)
            return _v2_error(502, "model_error", "Jarvis could not complete the request.")
        except HandheldSessionError as error:
            _session_store.abort(claim)
            return _session_error(error)
        except Exception:
            _session_store.abort(claim)
            return _v2_error(502, "model_error", "Jarvis could not complete the request.")

        return _v2_success({
            "ok": True,
            "turn": completed.turn,
            "response": completed.response,
            "truncated": completed.truncated,
            "replayed": False,
        })
    finally:
        _request_slot.release()
