from __future__ import annotations

import io
import json
import logging
import unittest
from unittest.mock import Mock, patch

import api
import api_routes.handheld as handheld_routes
from core.handheld_sessions import HandheldSessionStore
from skills.handheld_chat_skill import (
    HANDHELD_CONVERSATION_SYSTEM_PROMPT,
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

    def test_v1_requests_remain_stateless(self) -> None:
        first = self._post_payload({"prompt": "My favorite color is blue"})
        second = self._post_payload({"prompt": "What is my favorite color?"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            [model_call.args for model_call in self.model.call_args_list],
            [
                ("My favorite color is blue",),
                ("What is my favorite color?",),
            ],
        )

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


class HandheldChatV2ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = api.app.test_client()
        with handheld_routes._rate_lock:
            handheld_routes._accepted_request_times.clear()
        handheld_routes._session_store = HandheldSessionStore()
        self.token_patch = patch(
            "api_routes.handheld._get_server_token",
            return_value=TEST_TOKEN,
        )
        self.model_patch = patch(
            "api_routes.handheld.generate_handheld_conversation_response",
            return_value=HandheldChatResult("Unit-test v2 response", False),
        )
        self.token = self.token_patch.start()
        self.model = self.model_patch.start()

    def tearDown(self) -> None:
        self.model_patch.stop()
        self.token_patch.stop()
        with handheld_routes._rate_lock:
            handheld_routes._accepted_request_times.clear()
        handheld_routes._session_store = HandheldSessionStore()

    @staticmethod
    def _authorization(token: str = TEST_TOKEN) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _message(
        *,
        session: int = 1,
        request_id: int = 1,
        turn: int = 1,
        prompt="Hello",
    ):
        return {
            "operation": "message",
            "session_id": f"{session:032x}",
            "request_id": f"{request_id:032x}",
            "turn": turn,
            "prompt": prompt,
        }

    def _post(self, payload, *, token: str = TEST_TOKEN, content_type="application/json"):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self.client.post(
            "/handheld/v2/chat",
            data=body,
            content_type=content_type,
            headers=self._authorization(token),
        )

    def test_authentication_matches_v1_outward_behavior(self) -> None:
        body = json.dumps(self._message()).encode("utf-8")
        missing = self.client.post(
            "/handheld/v2/chat", data=body, content_type="application/json"
        )
        invalid = self._post(self._message(), token="wrong")

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(missing.get_json(), invalid.get_json())
        self.assertFalse(missing.get_json()["error"]["retryable"])
        self.model.assert_not_called()

    def test_content_type_length_body_and_duplicate_keys_are_strict(self) -> None:
        wrong_type = self._post(self._message(), content_type="text/plain")
        duplicate = self.client.post(
            "/handheld/v2/chat",
            data=(
                b'{"operation":"message","operation":"message",'
                b'"session_id":"00000000000000000000000000000001",'
                b'"request_id":"00000000000000000000000000000001",'
                b'"turn":1,"prompt":"Hello"}'
            ),
            content_type="application/json",
            headers=self._authorization(),
        )
        oversized = self.client.post(
            "/handheld/v2/chat",
            data=b"{" + (b"x" * 768) + b"}",
            content_type="application/json",
            headers=self._authorization(),
        )
        builder = EnvironBuilder(
            path="/handheld/v2/chat",
            method="POST",
            input_stream=io.BytesIO(b"{}"),
            content_type="application/json",
            headers=self._authorization(),
        )
        environment = builder.get_environ()
        environment.pop("CONTENT_LENGTH", None)
        missing_length = Response.from_app(api.app, environment)

        for response in (wrong_type, duplicate, oversized, missing_length):
            with self.subTest(body=response.get_data(as_text=True)):
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"]["code"], "invalid_request")
        self.model.assert_not_called()

    def test_message_requires_exact_shape_and_operation(self) -> None:
        payloads = [
            {**self._message(), "extra": True},
            {key: value for key, value in self._message().items() if key != "prompt"},
            {**self._message(), "operation": "status"},
            [],
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self._post(payload)
                self.assertEqual(response.status_code, 400)
        self.model.assert_not_called()

    def test_identifier_and_turn_boundaries_are_enforced(self) -> None:
        invalid_values = [
            {"session_id": "A" * 32},
            {"session_id": "a" * 31},
            {"request_id": "g" * 32},
            {"request_id": 1},
            {"turn": True},
            {"turn": 0},
            {"turn": 7},
            {"turn": 1.0},
        ]
        for changed in invalid_values:
            with self.subTest(changed=changed):
                response = self._post({**self._message(), **changed})
                self.assertEqual(response.status_code, 400)
        self.model.assert_not_called()

    def test_prompt_utf8_and_control_boundaries_reuse_v1_rules(self) -> None:
        accepted = self._post(self._message(prompt="  " + ("é" * 128) + "  "))
        self.assertEqual(accepted.status_code, 200)
        self.model.assert_called_once_with((), "é" * 128)

        handheld_routes._session_store = HandheldSessionStore()
        self.model.reset_mock()
        for prompt in ("é" * 129, " ", 7, "bad\u0000text"):
            with self.subTest(prompt=prompt):
                response = self._post(self._message(prompt=prompt))
                self.assertEqual(response.status_code, 400)
        self.model.assert_not_called()

    def test_success_conversation_order_and_session_isolation(self) -> None:
        self.model.side_effect = (
            HandheldChatResult("I'll remember that for this conversation.", False),
            HandheldChatResult("Your favorite color is blue.", False),
            HandheldChatResult("Isolated response", False),
        )
        first = self._post(self._message(prompt="My favorite color is blue"))
        second = self._post(self._message(
            request_id=2,
            turn=2,
            prompt="What is my favorite color?",
        ))
        isolated = self._post(self._message(session=2, request_id=3, prompt="other"))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(isolated.status_code, 200)
        self.assertEqual(self.model.call_args_list[1].args, (
            (
                ("user", "My favorite color is blue"),
                ("assistant", "I'll remember that for this conversation."),
            ),
            "What is my favorite color?",
        ))
        self.assertEqual(self.model.call_args_list[2].args, ((), "other"))

    def test_cached_retry_does_not_call_model_again(self) -> None:
        original = self._post(self._message(prompt="same"))
        replay = self._post(self._message(prompt="same"))
        next_turn = self._post(self._message(
            request_id=2,
            turn=2,
            prompt="next",
        ))

        self.assertFalse(original.get_json()["replayed"])
        self.assertTrue(replay.get_json()["replayed"])
        self.assertEqual(original.get_json()["response"], replay.get_json()["response"])
        self.assertEqual(next_turn.status_code, 200)
        self.assertEqual(self.model.call_count, 2)
        self.assertEqual(self.model.call_args_list[1].args, (
            (("user", "same"), ("assistant", "Unit-test v2 response")),
            "next",
        ))

    def test_request_and_turn_conflicts_are_bounded(self) -> None:
        self._post(self._message(prompt="original"))
        request_conflict = self._post(self._message(prompt="changed"))
        turn_conflict = self._post(self._message(request_id=2, turn=1))

        self.assertEqual(request_conflict.status_code, 409)
        self.assertEqual(request_conflict.get_json()["error"]["code"], "request_conflict")
        self.assertEqual(turn_conflict.status_code, 409)
        self.assertEqual(turn_conflict.get_json()["error"]["code"], "turn_conflict")
        for response in (request_conflict, turn_conflict):
            self.assertLessEqual(len(response.data), 256)

    def test_reset_is_exact_idempotent_and_rejects_in_flight(self) -> None:
        reset = {"operation": "reset", "session_id": f"{1:032x}"}
        self.assertEqual(self._post(reset).get_json(), {"ok": True, "reset": True})
        self.assertEqual(self._post(reset).get_json(), {"ok": True, "reset": True})
        claim = handheld_routes._session_store.begin_message(
            f"{1:032x}", f"{1:032x}", 1, "private"
        )
        blocked = self._post(reset)

        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["error"]["code"], "session_unavailable")
        handheld_routes._session_store.abort(claim)

    def test_timeout_and_failure_do_not_commit_turn(self) -> None:
        for error, status, code in (
            (HandheldModelTimeout(), 504, "model_timeout"),
            (HandheldModelError("private detail"), 502, "model_error"),
        ):
            with self.subTest(code=code):
                handheld_routes._session_store = HandheldSessionStore()
                self.model.reset_mock()
                self.model.side_effect = error
                failed = self._post(self._message())
                self.assertEqual(failed.status_code, status)
                self.assertEqual(failed.get_json()["error"]["code"], code)
                self.model.side_effect = None
                retry = self._post(self._message(request_id=2))
                self.assertEqual(retry.status_code, 200)
                self.assertEqual(self.model.call_args_list[1].args, ((), "Hello"))

    def test_shared_v1_v2_model_concurrency_slot(self) -> None:
        self.assertTrue(handheld_routes._request_slot.acquire(blocking=False))
        try:
            v2 = self._post(self._message())
            v1 = self.client.post(
                "/handheld/v1/chat",
                data=b'{"prompt":"Hello"}',
                content_type="application/json",
                headers=self._authorization(),
            )
        finally:
            handheld_routes._request_slot.release()

        self.assertEqual(v2.status_code, 409)
        self.assertEqual(v2.get_json()["error"]["code"], "session_unavailable")
        self.assertEqual(v1.status_code, 429)
        self.assertEqual(v1.get_json()["error"]["code"], "busy")
        self.model.assert_not_called()

    def test_shared_rolling_rate_limit(self) -> None:
        with handheld_routes._rate_lock:
            handheld_routes._accepted_request_times.extend([0.0] * 5)
        with patch("api_routes.handheld.time.monotonic", return_value=1.0):
            allowed = self._post(self._message())
            limited = self._post(self._message(session=2, request_id=2))

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.get_json()["error"]["code"], "rate_limited")

    def test_success_and_errors_remain_serialization_bounded(self) -> None:
        self.model.return_value = HandheldChatResult("é" * 1024, True)
        success = self._post(self._message())
        invalid = self._post({"operation": "invalid"})

        self.assertLessEqual(len(success.data), 4608)
        self.assertLessEqual(len(success.get_json()["response"].encode("utf-8")), 2048)
        self.assertLessEqual(len(invalid.data), 256)

    def test_protected_values_and_internal_errors_are_not_logged(self) -> None:
        session_id = "a" * 32
        request_id = "b" * 32
        prompt = "private v2 prompt"
        response_text = "private v2 response"
        self.model.side_effect = RuntimeError("private internal exception")
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logging.getLogger().addHandler(handler)
        api.app.logger.addHandler(handler)
        try:
            with patch("builtins.print") as captured_print:
                response = self._post({
                    "operation": "message",
                    "session_id": session_id,
                    "request_id": request_id,
                    "turn": 1,
                    "prompt": prompt,
                })
        finally:
            logging.getLogger().removeHandler(handler)
            api.app.logger.removeHandler(handler)

        captured = log_stream.getvalue() + " ".join(
            str(call) for call in captured_print.call_args_list
        )
        for protected in (
            TEST_TOKEN,
            session_id,
            request_id,
            prompt,
            response_text,
            "private internal exception",
        ):
            self.assertNotIn(protected, captured)
        self.assertEqual(response.status_code, 502)


class HandheldChatV2EndToEndRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = api.app.test_client()
        with handheld_routes._rate_lock:
            handheld_routes._accepted_request_times.clear()
        handheld_routes._session_store = HandheldSessionStore()
        self.token_patch = patch(
            "api_routes.handheld._get_server_token",
            return_value=TEST_TOKEN,
        )
        self.model_id_patch = patch(
            "skills.handheld_chat_skill.get_active_model_id",
            return_value="unit-test-model",
        )
        self.token_patch.start()
        self.model_id_patch.start()

    def tearDown(self) -> None:
        self.model_id_patch.stop()
        self.token_patch.stop()
        with handheld_routes._rate_lock:
            handheld_routes._accepted_request_times.clear()
        handheld_routes._session_store = HandheldSessionStore()

    @staticmethod
    def _model_response(content: str) -> Mock:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": content}}],
        }
        return response

    def _post(self, request_id: int, turn: int, prompt: str):
        return self.client.post(
            "/handheld/v2/chat",
            json={
                "operation": "message",
                "session_id": f"{1:032x}",
                "request_id": f"{request_id:032x}",
                "turn": turn,
                "prompt": prompt,
            },
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )

    def test_completed_first_turn_reaches_second_model_request(self) -> None:
        with patch(
            "skills.handheld_chat_skill.requests.post",
            side_effect=(
                self._model_response("Acknowledged."),
                self._model_response("Your favorite color is blue."),
            ),
        ) as model_post:
            first = self._post(1, 1, "My favorite color is blue")
            second = self._post(2, 2, "What is my favorite color?")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["response"], "Your favorite color is blue.")
        self.assertEqual(model_post.call_args_list[1].kwargs["json"]["messages"], [
            {"role": "system", "content": HANDHELD_CONVERSATION_SYSTEM_PROMPT},
            {"role": "user", "content": "My favorite color is blue"},
            {"role": "assistant", "content": "Acknowledged."},
            {"role": "user", "content": "What is my favorite color?"},
        ])

    def test_reasoning_only_failure_does_not_create_history(self) -> None:
        with patch(
            "skills.handheld_chat_skill.requests.post",
            side_effect=(
                self._model_response("<think>private reasoning</think>"),
                self._model_response("Safe answer"),
            ),
        ) as model_post:
            failed = self._post(1, 1, "First attempt")
            retry = self._post(2, 1, "Retry")

        self.assertEqual(failed.status_code, 502)
        self.assertEqual(failed.get_json()["error"]["code"], "model_error")
        self.assertLessEqual(len(failed.data), 256)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(model_post.call_args_list[1].kwargs["json"]["messages"], [
            {"role": "system", "content": HANDHELD_CONVERSATION_SYSTEM_PROMPT},
            {"role": "user", "content": "Retry"},
        ])


if __name__ == "__main__":
    unittest.main()
