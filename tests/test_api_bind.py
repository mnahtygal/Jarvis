from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import api


class ApiBindTests(unittest.TestCase):
    def test_missing_value_defaults_to_ipv4_loopback(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(api._resolve_api_bind_host(), "127.0.0.1")

    def test_approved_loopback_values_are_preserved(self) -> None:
        for bind_host in ("127.0.0.1", "localhost", "::1"):
            with self.subTest(bind_host=bind_host):
                self.assertEqual(api._resolve_api_bind_host(bind_host), bind_host)

    def test_unsafe_or_malformed_values_fall_back_to_ipv4_loopback(self) -> None:
        unsafe_values = (
            "",
            "0.0.0.0",
            "10.0.0.213",
            "example.invalid",
            "127.0.0.1 ",
            " 127.0.0.1",
            "127.0.0.2",
            "[::1]",
            "::",
            "127.0.0.1:5000",
            "\n127.0.0.1",
        )
        for bind_host in unsafe_values:
            with self.subTest(bind_host=bind_host):
                self.assertEqual(
                    api._resolve_api_bind_host(bind_host),
                    "127.0.0.1",
                )

    def test_environment_value_controls_server_bind_without_starting_server(self) -> None:
        with (
            patch.dict(os.environ, {"JARVIS_API_BIND_HOST": "localhost"}, clear=True),
            patch.object(api.app, "run") as run,
        ):
            api._run_api_server()

        run.assert_called_once_with(host="localhost", port=5000)

    def test_unsafe_environment_value_cannot_create_wildcard_listener(self) -> None:
        with (
            patch.dict(os.environ, {"JARVIS_API_BIND_HOST": "0.0.0.0"}, clear=True),
            patch.object(api.app, "run") as run,
        ):
            api._run_api_server()

        run.assert_called_once_with(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    unittest.main()
