from __future__ import annotations

import io
import json
import logging
import unittest
from unittest.mock import patch

import api
import api_routes.handheld as handheld_routes
from skills.handheld_chat_skill import (
    HandheldChatResult,
    HandheldModelError,
    HandheldModelTimeout,
)
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Response


TEST_TOKEN = "unit-test-only-handheld-token"


class HandheldChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = api.app.test_client()
        with handheld_routes._rate_lock:
            handheld_routes._accepted_request_times.clear()

        self.token_patch = patch(
            "api_routes.handheld._get_server_token",
            return_value=TEST_TOKEN,
        )
        self.model_patch = patch(
            "api_routes.handheld.generate_handheld_response",
            return_value=HandheldChatResult(
                response="Unit-test response",
                truncated=False,
            ),
        )
        self.token = self.token_patch.start()
        self.model = self.model_patch.start()

    def tearDown(self) -> None:
        self.model_patch.stop()
        self.token_patch.stop()
        with handheld_routes._rate_lock:
            handheld_routes._accepted_request_times.clear()

    @staticmethod
    def _authorization(token: str = TEST_TOKEN) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _post_payload(
        self,
        payload,
        *,
        token: str = TEST_TOKEN,
        content_type: str = "application/json",
    ):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self.client.post(
            "/handheld/v1/chat",
            data=body,
            content_type=content_type,
            headers=self._authorization(token),
        )

    def test_missing_server_token_fails_closed(self) -> None:
        self.token.return_value = ""

        response = self._post_payload({"prompt": "Hello"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "not_configured")
        self.model.assert_not_called()

    def test_missing_and_invalid_credentials_have_equal_outward_behavior(self) -> None:
        body = json.dumps({"prompt": "Hello"}).encode("utf-8")
        missing = self.client.post(
            "/handheld/v1/chat",
            data=body,
            content_type="application/json",
        )
        invalid = self._post_payload({"prompt": "Hello"}, token="invalid-test-token")

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(missing.get_json(), invalid.get_json())
        self.model.assert_not_called()

    def test_malformed_authorization_is_rejected(self) -> None:
        body = json.dumps({"prompt": "Hello"}).encode("utf-8")
        for authorization in (
            TEST_TOKEN,
            f"Basic {TEST_TOKEN}",
            "Bearer",
            f"Bearer  {TEST_TOKEN}",
            f"bearer {TEST_TOKEN}",
        ):
            with self.subTest(authorization=authorization.split(" ", 1)[0]):
                response = self.client.post(
                    "/handheld/v1/chat",
                    data=body,
                    content_type="application/json",
                    headers={"Authorization": authorization},
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"]["code"], "unauthorized")
        self.model.assert_not_called()

    def test_valid_authentication_reaches_model_service(self) -> None:
        response = self._post_payload({"prompt": "  Hello Jarvis  "})

        self.assertEqual(response.status_code, 200)
        self.model.assert_called_once_with("Hello Jarvis")

    def test_wrong_content_type_is_rejected(self) -> None:
        response = self._post_payload(
            {"prompt": "Hello"},
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.get_json()["error"]["code"], "unsupported_media_type")
        self.model.assert_not_called()

    def test_missing_content_length_is_rejected(self) -> None:
        body = json.dumps({"prompt": "Hello"}).encode("utf-8")
        builder = EnvironBuilder(
            path="/handheld/v1/chat",
            method="POST",
            input_stream=io.BytesIO(body),
            content_type="application/json",
            headers=self._authorization(),
        )
        environment = builder.get_environ()
        environment.pop("CONTENT_LENGTH", None)

        response = Response.from_app(api.app, environment)

        self.assertEqual(response.status_code, 411)
        self.assertEqual(response.get_json()["error"]["code"], "length_required")
        self.model.assert_not_called()

    def test_oversized_request_is_rejected(self) -> None:
        body = b'{"prompt":"' + (b"a" * 800) + b'"}'

        response = self.client.post(
            "/handheld/v1/chat",
            data=body,
            content_type="application/json",
            headers=self._authorization(),
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json()["error"]["code"], "request_too_large")
        self.model.assert_not_called()

    def test_invalid_and_non_object_json_are_rejected(self) -> None:
        invalid_bodies = (b"{not-json", b"[]", b'"prompt"', b"null")
        for body in invalid_bodies:
            with self.subTest(body=body):
                response = self.client.post(
                    "/handheld/v1/chat",
                    data=body,
                    content_type="application/json",
                    headers=self._authorization(),
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"]["code"], "invalid_request")
        self.model.assert_not_called()

    def test_missing_empty_and_non_string_prompts_are_rejected(self) -> None:
        for payload in ({}, {"prompt": "  "}, {"prompt": 7}, {"prompt": None}):
            with self.subTest(payload=payload):
                response = self._post_payload(payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"]["code"], "invalid_request")
        self.model.assert_not_called()

    def test_prompt_limit_is_measured_in_utf8_bytes(self) -> None:
        response = self._post_payload({"prompt": "é" * 129})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "invalid_request")
        self.model.assert_not_called()

    def test_unknown_and_duplicate_fields_are_rejected(self) -> None:
        unknown = self._post_payload({"prompt": "Hello", "operation": "status"})
        duplicate_body = b'{"prompt":"first","prompt":"second"}'
        duplicate = self.client.post(
            "/handheld/v1/chat",
            data=duplicate_body,
            content_type="application/json",
            headers=self._authorization(),
        )

        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(duplicate.status_code, 400)
        self.model.assert_not_called()

    def test_unsupported_control_character_is_rejected(self) -> None:
        for prompt in ("Hello\u0000Jarvis", "\u001fHello", "Hello\u001f"):
            with self.subTest(prompt_position=prompt.find("Hello")):
                response = self._post_payload({"prompt": prompt})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"]["code"], "invalid_request")
        self.model.assert_not_called()

    def test_valid_request_returns_bounded_contract(self) -> None:
        self.model.return_value = HandheldChatResult(
            response="Bounded response",
            truncated=True,
        )

        response = self._post_payload({"prompt": "Hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "ok": True,
            "response": "Bounded response",
            "truncated": True,
        })

    def test_busy_request_is_rejected_without_consuming_rate_limit(self) -> None:
        self.assertTrue(handheld_routes._request_slot.acquire(blocking=False))
        try:
            response = self._post_payload({"prompt": "Hello"})
        finally:
            handheld_routes._request_slot.release()

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["error"]["code"], "busy")
        self.model.assert_not_called()
        self.assertEqual(len(handheld_routes._accepted_request_times), 0)

    def test_rate_limit_allows_six_then_rejects(self) -> None:
        for index in range(6):
            response = self._post_payload({"prompt": f"Request {index}"})
            self.assertEqual(response.status_code, 200)

        limited = self._post_payload({"prompt": "Request seven"})

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.get_json()["error"]["code"], "rate_limited")
        self.assertEqual(self.model.call_count, 6)

    def test_model_timeout_is_safe(self) -> None:
        self.model.side_effect = HandheldModelTimeout

        response = self._post_payload({"prompt": "Hello"})

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.get_json()["error"]["code"], "model_timeout")

    def test_model_failure_is_safe(self) -> None:
        self.model.side_effect = HandheldModelError("internal detail")

        response = self._post_payload({"prompt": "Hello"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error"]["code"], "model_error")
        self.assertNotIn("internal detail", response.get_data(as_text=True))

    def test_prompt_token_and_response_are_not_logged(self) -> None:
        prompt = "private unit-test prompt"
        model_text = "private unit-test response"
        self.model.return_value = HandheldChatResult(model_text, False)
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        app_logger = api.app.logger
        root_logger.addHandler(handler)
        app_logger.addHandler(handler)
        try:
            with patch("builtins.print") as captured_print:
                response = self._post_payload({"prompt": prompt})
        finally:
            root_logger.removeHandler(handler)
            app_logger.removeHandler(handler)

        printed = " ".join(str(call) for call in captured_print.call_args_list)
        captured = log_stream.getvalue() + printed
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(TEST_TOKEN, captured)
        self.assertNotIn(prompt, captured)
        self.assertNotIn(model_text, captured)

    def test_health_remains_unauthenticated_and_unchanged(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})
        self.model.assert_not_called()

    def test_text_route_remains_unchanged(self) -> None:
        with patch("api.think", return_value="Existing text response") as think:
            response = self.client.post(
                "/text",
                json={"command": "Existing command", "use_voice": False},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "heard": "Existing command",
            "response": "Existing text response",
        })
        think.assert_called_once_with("Existing command")
        self.model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
