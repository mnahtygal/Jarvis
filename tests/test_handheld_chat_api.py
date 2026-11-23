from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Response

import api
import api_routes.handheld as handheld_routes
from skills.handheld_chat_skill import (
    HandheldChatResult,
    HandheldModelError,
    HandheldModelTimeout,
)


TEST_TOKEN = "unit-test-only-handheld-token"


@pytest.fixture(autouse=True)
def reset_handheld_rate_limit():
    with handheld_routes._rate_lock:
        handheld_routes._accepted_request_times.clear()
    yield
    with handheld_routes._rate_lock:
        handheld_routes._accepted_request_times.clear()


@pytest.fixture
def client():
    return api.app.test_client()


def _headers(token: str = TEST_TOKEN, *, origin: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if origin is not None:
        headers["Origin"] = origin
    return headers


def _post(client, payload, *, token: str = TEST_TOKEN, content_type="application/json"):
    return client.post(
        "/handheld/v1/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type=content_type,
        headers=_headers(token),
    )


def test_endpoint_is_registered():
    rules = {
        (rule.rule, frozenset(rule.methods))
        for rule in api.app.url_map.iter_rules()
    }
    assert any(path == "/handheld/v1/chat" and "POST" in methods for path, methods in rules)


def test_valid_authenticated_request_matches_android_contract(client, monkeypatch):
    model = patch(
        "api_routes.handheld.generate_handheld_response",
        return_value=HandheldChatResult("Hello, Olivia!", False),
    ).start()
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    try:
        response = _post(client, {"prompt": "  Hello LooLoo  "})
    finally:
        model.stop()

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "response": "Hello, Olivia!",
        "truncated": False,
    }
    model.assert_called_once_with("Hello LooLoo")


def test_missing_server_token_fails_closed(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: "")
    model = patch("api_routes.handheld.generate_handheld_response").start()
    try:
        response = _post(client, {"prompt": "Hello"})
    finally:
        model.stop()

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "not_configured"
    model.assert_not_called()


def test_invalid_and_missing_credentials_are_indistinguishable(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    body = json.dumps({"prompt": "Hello"}).encode()

    missing = client.post(
        "/handheld/v1/chat",
        data=body,
        content_type="application/json",
    )
    invalid = _post(client, {"prompt": "Hello"}, token="incorrect")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.get_json() == invalid.get_json()


@pytest.mark.parametrize(
    "body",
    (b"{not-json", b"[]", b'"prompt"', b"null", b'{"prompt":"one","prompt":"two"}'),
)
def test_malformed_non_object_and_duplicate_json_are_rejected(client, monkeypatch, body):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    response = client.post(
        "/handheld/v1/chat",
        data=body,
        content_type="application/json",
        headers=_headers(),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize(
    "payload",
    ({}, {"prompt": ""}, {"prompt": "  "}, {"prompt": 7}, {"prompt": "ok", "extra": 1}),
)
def test_invalid_prompt_shapes_and_unknown_fields_are_rejected(client, monkeypatch, payload):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    response = _post(client, payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"


def test_control_characters_and_utf8_prompt_limit_are_enforced(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)

    control = _post(client, {"prompt": "Hello\u0000LooLoo"})
    too_long = _post(client, {"prompt": "é" * 129})

    assert control.status_code == 400
    assert too_long.status_code == 400


def test_body_size_content_type_and_content_length_are_enforced(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    oversized = b'{"prompt":"' + (b"a" * 800) + b'"}'
    too_large = client.post(
        "/handheld/v1/chat",
        data=oversized,
        content_type="application/json",
        headers=_headers(),
    )
    wrong_type = _post(client, {"prompt": "Hello"}, content_type="text/plain")

    body = b'{"prompt":"Hello"}'
    builder = EnvironBuilder(
        path="/handheld/v1/chat",
        method="POST",
        input_stream=io.BytesIO(body),
        content_type="application/json",
        headers=_headers(),
    )
    environment = builder.get_environ()
    environment.pop("CONTENT_LENGTH", None)
    missing_length = Response.from_app(api.app, environment)

    assert too_large.status_code == 413
    assert wrong_type.status_code == 415
    assert missing_length.status_code == 411


def test_busy_request_does_not_consume_rate_limit(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    assert handheld_routes._request_slot.acquire(blocking=False)
    try:
        response = _post(client, {"prompt": "Hello"})
    finally:
        handheld_routes._request_slot.release()

    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "busy"
    assert not handheld_routes._accepted_request_times


def test_rate_limit_allows_six_requests_then_rejects(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    monkeypatch.setattr(
        handheld_routes,
        "generate_handheld_response",
        lambda prompt: HandheldChatResult("answer", False),
    )

    for index in range(6):
        assert _post(client, {"prompt": f"Request {index}"}).status_code == 200
    limited = _post(client, {"prompt": "Request seven"})

    assert limited.status_code == 429
    assert limited.get_json()["error"]["code"] == "rate_limited"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    ((HandheldModelTimeout(), 504, "model_timeout"), (HandheldModelError(), 502, "model_error")),
)
def test_model_failures_return_safe_errors(client, monkeypatch, error, status, code):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    monkeypatch.setattr(
        handheld_routes,
        "generate_handheld_response",
        lambda prompt: (_ for _ in ()).throw(error),
    )

    response = _post(client, {"prompt": "private child prompt"})

    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code
    assert TEST_TOKEN not in response.get_data(as_text=True)
    assert "private child prompt" not in response.get_data(as_text=True)


def test_handheld_route_cannot_invoke_jarvis_tools_or_brain(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    monkeypatch.setattr(
        handheld_routes,
        "generate_handheld_response",
        lambda prompt: HandheldChatResult("Safe answer", False),
    )

    with (
        patch("api.think", side_effect=AssertionError("Brain must not run")),
        patch("api.capture_snapshot", side_effect=AssertionError("Camera must not run")),
        patch("api.listen_command", side_effect=AssertionError("Voice must not run")),
        patch("api.speak", side_effect=AssertionError("Speech must not run")),
        patch("core.orchestrator.process_request", side_effect=AssertionError("Tools must not run")),
    ):
        response = _post(client, {"prompt": "Please use a tool"})

    assert response.status_code == 200
    assert response.get_json()["response"] == "Safe answer"


def test_existing_health_and_text_routes_remain_unchanged(client):
    assert client.get("/health").get_json() == {"status": "ok"}
    with patch("api.think", return_value="Existing response"):
        response = client.post("/text", json={"command": "hello", "use_voice": False})
    assert response.status_code == 200
    assert response.get_json() == {"heard": "hello", "response": "Existing response"}


def test_handheld_route_opts_out_of_wildcard_cors_without_changing_health(client, monkeypatch):
    monkeypatch.setattr(handheld_routes, "_get_server_token", lambda: TEST_TOKEN)
    monkeypatch.setattr(
        handheld_routes,
        "generate_handheld_response",
        lambda prompt: HandheldChatResult("answer", False),
    )
    origin = "https://untrusted.example"

    handheld = client.post(
        "/handheld/v1/chat",
        data=b'{"prompt":"Hello"}',
        content_type="application/json",
        headers=_headers(origin=origin),
    )
    health = client.get("/health", headers={"Origin": origin})

    assert "Access-Control-Allow-Origin" not in handheld.headers
    assert health.headers.get("Access-Control-Allow-Origin") == origin
