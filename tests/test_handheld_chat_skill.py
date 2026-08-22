from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from skills.handheld_chat_skill import (
    HANDHELD_MODEL_MAX_TOKENS,
    HANDHELD_MODEL_TIMEOUT_SECONDS,
    HANDHELD_RESPONSE_MAX_BYTES,
    HANDHELD_SYSTEM_PROMPT,
    HandheldModelError,
    HandheldModelTimeout,
    generate_handheld_conversation_response,
    generate_handheld_response,
)


class HandheldChatSkillTests(unittest.TestCase):
    @staticmethod
    def _model_response(content: str):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": content}}],
        }
        return response

    def test_valid_model_response_uses_fixed_stateless_contract(self) -> None:
        with (
            patch(
                "skills.handheld_chat_skill.get_active_model_id",
                return_value="unit-test-model",
            ),
            patch(
                "skills.handheld_chat_skill.requests.post",
                return_value=self._model_response("Model response"),
            ) as model_post,
        ):
            result = generate_handheld_response("User prompt")

        self.assertEqual(result.response, "Model response")
        self.assertFalse(result.truncated)
        model_post.assert_called_once()
        call = model_post.call_args
        self.assertEqual(call.kwargs["timeout"], HANDHELD_MODEL_TIMEOUT_SECONDS)
        self.assertEqual(call.kwargs["json"]["max_tokens"], HANDHELD_MODEL_MAX_TOKENS)
        self.assertFalse(call.kwargs["json"]["stream"])
        self.assertEqual(call.kwargs["json"]["messages"], [
            {"role": "system", "content": HANDHELD_SYSTEM_PROMPT},
            {"role": "user", "content": "User prompt"},
        ])

    def test_timeout_is_converted_without_retry(self) -> None:
        with (
            patch(
                "skills.handheld_chat_skill.get_active_model_id",
                return_value="unit-test-model",
            ),
            patch(
                "skills.handheld_chat_skill.requests.post",
                side_effect=requests.exceptions.Timeout,
            ) as model_post,
        ):
            with self.assertRaises(HandheldModelTimeout):
                generate_handheld_response("User prompt")

        model_post.assert_called_once()

    def test_transport_failure_is_converted_without_retry(self) -> None:
        with (
            patch(
                "skills.handheld_chat_skill.get_active_model_id",
                return_value="unit-test-model",
            ),
            patch(
                "skills.handheld_chat_skill.requests.post",
                side_effect=requests.exceptions.ConnectionError("detail"),
            ) as model_post,
        ):
            with self.assertRaises(HandheldModelError):
                generate_handheld_response("User prompt")

        model_post.assert_called_once()

    def test_invalid_json_and_invalid_model_shapes_fail_safely(self) -> None:
        invalid_json = Mock()
        invalid_json.raise_for_status.return_value = None
        invalid_json.json.side_effect = ValueError("detail")
        invalid_shape = Mock()
        invalid_shape.raise_for_status.return_value = None
        invalid_shape.json.return_value = {"choices": []}

        for model_response in (invalid_json, invalid_shape):
            with self.subTest(model_response=model_response):
                with (
                    patch(
                        "skills.handheld_chat_skill.get_active_model_id",
                        return_value="unit-test-model",
                    ),
                    patch(
                        "skills.handheld_chat_skill.requests.post",
                        return_value=model_response,
                    ) as model_post,
                ):
                    with self.assertRaises(HandheldModelError):
                        generate_handheld_response("User prompt")
                model_post.assert_called_once()

    def test_response_truncation_preserves_utf8_boundary(self) -> None:
        response_text = ("a" * (HANDHELD_RESPONSE_MAX_BYTES - 1)) + "€"
        with (
            patch(
                "skills.handheld_chat_skill.get_active_model_id",
                return_value="unit-test-model",
            ),
            patch(
                "skills.handheld_chat_skill.requests.post",
                return_value=self._model_response(response_text),
            ),
        ):
            result = generate_handheld_response("User prompt")

        encoded = result.response.encode("utf-8")
        self.assertTrue(result.truncated)
        self.assertLessEqual(len(encoded), HANDHELD_RESPONSE_MAX_BYTES)
        self.assertEqual(result.response, "a" * (HANDHELD_RESPONSE_MAX_BYTES - 1))

    def test_thinking_text_is_not_returned(self) -> None:
        with (
            patch(
                "skills.handheld_chat_skill.get_active_model_id",
                return_value="unit-test-model",
            ),
            patch(
                "skills.handheld_chat_skill.requests.post",
                return_value=self._model_response(
                    "<think>private reasoning</think>Visible answer"
                ),
            ),
        ):
            result = generate_handheld_response("User prompt")

        self.assertEqual(result.response, "Visible answer")

    def test_conversation_wrapper_builds_ordered_bounded_model_request(self) -> None:
        with (
            patch(
                "skills.handheld_chat_skill.get_active_model_id",
                return_value="unit-test-model",
            ),
            patch(
                "skills.handheld_chat_skill.requests.post",
                return_value=self._model_response("Conversation response"),
            ) as model_post,
        ):
            result = generate_handheld_conversation_response(
                (("user", "first"), ("assistant", "answer one")),
                "second",
            )

        self.assertEqual(result.response, "Conversation response")
        model_post.assert_called_once()
        call = model_post.call_args
        self.assertEqual(call.kwargs["timeout"], HANDHELD_MODEL_TIMEOUT_SECONDS)
        self.assertEqual(call.kwargs["json"]["max_tokens"], HANDHELD_MODEL_MAX_TOKENS)
        self.assertEqual(call.kwargs["json"]["messages"], [
            {"role": "system", "content": HANDHELD_SYSTEM_PROMPT},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer one"},
            {"role": "user", "content": "second"},
        ])

    def test_conversation_timeout_and_failure_make_one_call(self) -> None:
        for error, expected in (
            (requests.exceptions.Timeout(), HandheldModelTimeout),
            (requests.exceptions.ConnectionError("detail"), HandheldModelError),
        ):
            with self.subTest(expected=expected):
                with (
                    patch(
                        "skills.handheld_chat_skill.get_active_model_id",
                        return_value="unit-test-model",
                    ),
                    patch(
                        "skills.handheld_chat_skill.requests.post",
                        side_effect=error,
                    ) as model_post,
                ):
                    with self.assertRaises(expected):
                        generate_handheld_conversation_response((), "prompt")
                model_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
