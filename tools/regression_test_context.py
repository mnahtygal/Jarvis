# tools/regression_test_context.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.context import (  # noqa: E402
    build_context_sections,
    build_context_summary,
    build_messages,
    build_prompt,
)


TEST_QUERY = "What is the long term goal for Jarvis?"


def _assert_contains(name: str, text: str, expected: str) -> None:
    if expected not in text:
        raise AssertionError(f"{name} did not contain expected text: {expected!r}")


def _assert_truthy(name: str, value: object) -> None:
    if not value:
        raise AssertionError(f"{name} was empty or false")


def test_build_context_sections() -> None:
    sections = build_context_sections(user_text=TEST_QUERY)

    required_keys = {
        "last_topic",
        "exact_memory",
        "semantic_memory",
        "recent_history",
    }

    missing = required_keys.difference(sections)

    if missing:
        raise AssertionError(f"build_context_sections missing keys: {sorted(missing)}")

    for key in required_keys:
        _assert_truthy(f"sections[{key}]", sections[key])

    _assert_contains("exact_memory", sections["exact_memory"], "Known facts about Marty")
    _assert_contains("semantic_memory", sections["semantic_memory"], "Jarvis")


def test_build_prompt() -> None:
    prompt = build_prompt(TEST_QUERY)

    _assert_truthy("build_prompt", prompt)
    _assert_contains("prompt", prompt, "You are Jarvis, Marty's local AI assistant.")
    _assert_contains("prompt", prompt, "Exact long-term memory:")
    _assert_contains("prompt", prompt, "Semantic memory:")
    _assert_contains("prompt", prompt, "Recent conversation:")
    _assert_contains("prompt", prompt, "Current user message:")
    _assert_contains("prompt", prompt, TEST_QUERY)
    _assert_contains("prompt", prompt, "Jarvis response:")


def test_build_messages() -> None:
    messages = build_messages(TEST_QUERY)

    if not isinstance(messages, list):
        raise AssertionError("build_messages did not return a list")

    if len(messages) != 2:
        raise AssertionError(f"build_messages returned {len(messages)} messages, expected 2")

    system_message = messages[0]
    user_message = messages[1]

    if system_message.get("role") != "system":
        raise AssertionError("First message role should be system")

    if user_message.get("role") != "user":
        raise AssertionError("Second message role should be user")

    _assert_contains("system message", system_message.get("content", ""), "Exact long-term memory:")
    _assert_contains("system message", system_message.get("content", ""), "Semantic memory:")
    _assert_contains("system message", system_message.get("content", ""), "Recent conversation:")
    _assert_contains("user message", user_message.get("content", ""), TEST_QUERY)


def test_build_context_summary() -> None:
    summary = build_context_summary(user_text=TEST_QUERY)

    _assert_truthy("build_context_summary", summary)
    _assert_contains("summary", summary, "Last topic:")
    _assert_contains("summary", summary, "Exact long-term memory:")
    _assert_contains("summary", summary, "Semantic memory:")
    _assert_contains("summary", summary, "Recent conversation:")
    _assert_contains("summary", summary, "Known facts about Marty")
    _assert_contains("summary", summary, "Jarvis")


def run_test(name: str, test_func: Callable[[], None]) -> bool:
    try:
        test_func()
    except Exception as error:
        print(f"[FAIL] {name}: {type(error).__name__}: {error}")
        return False

    print(f"[PASS] {name}")
    return True


def main() -> int:
    print("===================================")
    print(" Jarvis Context Regression Test")
    print("===================================")

    tests = [
        ("build_context_sections", test_build_context_sections),
        ("build_prompt", test_build_prompt),
        ("build_messages", test_build_messages),
        ("build_context_summary", test_build_context_summary),
    ]

    passed = 0

    for name, test_func in tests:
        if run_test(name, test_func):
            passed += 1

    print()
    print("===================================")
    print(f" Context regression complete: {passed}/{len(tests)} passed")
    print("===================================")

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
