"""Regression tests for mixed-intent runtime identity requests."""

import pytest

from core.router import (
    _is_runtime_identity_request,
    normalize_text_for_routing,
)


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("What model are you using?", True),
        ("What hardware are you running on?", True),
        ("What LLM are you using?", True),
        (
            "Good morning, Jarvis. Tell me what model you're using "
            "and give me a short welcome-home message.",
            False,
        ),
        (
            "What model are you using and explain how neural networks work?",
            False,
        ),
        (
            "What hardware are you running on and tell me a joke.",
            False,
        ),
        (
            "Write exactly three sentences welcoming me home from vacation.",
            False,
        ),
    ],
)
def test_runtime_identity_only_matches_standalone_requests(prompt, expected):
    normalized = normalize_text_for_routing(prompt)
    assert _is_runtime_identity_request(normalized) is expected
