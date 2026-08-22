from __future__ import annotations

import unittest

from core.handheld_sessions import (
    HANDHELD_ABSOLUTE_SECONDS,
    HANDHELD_IDLE_SECONDS,
    MAX_HANDHELD_CONTENT_BYTES,
    HandheldReplay,
    HandheldRequestClaim,
    HandheldSessionError,
    HandheldSessionStore,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class HandheldSessionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = _Clock()
        self.store = HandheldSessionStore(self.clock)

    def _claim(
        self,
        session: int = 1,
        request: int = 1,
        turn: int = 1,
        prompt: str = "prompt",
    ) -> HandheldRequestClaim:
        result = self.store.begin_message(
            f"{session:032x}", f"{request:032x}", turn, prompt
        )
        self.assertIsInstance(result, HandheldRequestClaim)
        return result  # type: ignore[return-value]

    def _complete(
        self,
        session: int = 1,
        request: int = 1,
        turn: int = 1,
        prompt: str = "prompt",
        response: str = "response",
    ) -> HandheldReplay:
        claim = self._claim(session, request, turn, prompt)
        return self.store.commit(claim, response, False)

    def _assert_error(self, code: str, callback) -> None:
        with self.assertRaises(HandheldSessionError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_completed_turns_are_returned_in_model_order(self) -> None:
        self._complete(prompt="first", response="answer one")
        claim = self._claim(request=2, turn=2, prompt="second")

        self.assertEqual(claim.messages, (
            ("user", "first"),
            ("assistant", "answer one"),
        ))

    def test_sessions_are_isolated(self) -> None:
        self._complete(session=1, request=1, prompt="private one")
        claim = self._claim(session=2, request=2, prompt="private two")

        self.assertEqual(claim.messages, ())

    def test_replay_is_cached_and_conflicts_are_rejected(self) -> None:
        self._complete(prompt="same", response="cached")
        replay = self.store.begin_message(f"{1:032x}", f"{1:032x}", 1, "same")

        self.assertEqual(replay, HandheldReplay(1, "cached", False))
        self._assert_error(
            "request_conflict",
            lambda: self.store.begin_message(f"{1:032x}", f"{1:032x}", 1, "changed"),
        )
        self._assert_error(
            "request_conflict",
            lambda: self.store.begin_message(f"{2:032x}", f"{1:032x}", 1, "same"),
        )

    def test_in_flight_duplicate_and_session_conflict_are_distinct(self) -> None:
        self._claim(prompt="same")
        self._assert_error(
            "request_in_progress",
            lambda: self.store.begin_message(f"{1:032x}", f"{1:032x}", 1, "same"),
        )
        self._assert_error(
            "session_unavailable",
            lambda: self.store.begin_message(f"{1:032x}", f"{2:032x}", 1, "other"),
        )

    def test_abort_does_not_commit_and_allows_retry(self) -> None:
        claim = self._claim(prompt="retry")
        self.store.abort(claim)

        retried = self._claim(prompt="retry")
        self.assertEqual(retried.messages, ())

    def test_turn_order_and_six_turn_limit(self) -> None:
        for turn in range(1, 7):
            self._complete(request=turn, turn=turn)

        self._assert_error(
            "turn_conflict",
            lambda: self.store.begin_message(f"{1:032x}", f"{7:032x}", 7, "extra"),
        )
        self._assert_error(
            "turn_conflict",
            lambda: self.store.begin_message(f"{2:032x}", f"{8:032x}", 2, "late"),
        )

    def test_aggregate_content_limit_is_enforced_atomically(self) -> None:
        claim = self._claim(prompt="p")
        self._assert_error(
            "session_unavailable",
            lambda: self.store.commit(claim, "x" * MAX_HANDHELD_CONTENT_BYTES, False),
        )

        retry = self._claim(request=2, prompt="p")
        self.assertEqual(retry.messages, ())

    def test_idle_and_absolute_expiration_use_monotonic_clock(self) -> None:
        self._complete(session=1, request=1)
        self.clock.now += HANDHELD_IDLE_SECONDS
        idle_replacement = self._claim(session=1, request=2, turn=1)
        self.store.abort(idle_replacement)

        self.clock.now = 100.0
        absolute_store = HandheldSessionStore(self.clock)
        claim = absolute_store.begin_message(f"{1:032x}", f"{1:032x}", 1, "one")
        assert isinstance(claim, HandheldRequestClaim)
        absolute_store.commit(claim, "answer", False)
        for _ in range(8):
            self.clock.now += HANDHELD_IDLE_SECONDS - 100
            replay = absolute_store.begin_message(
                f"{1:032x}", f"{1:032x}", 1, "one"
            )
            self.assertIsInstance(replay, HandheldReplay)
        self.clock.now = 100.0 + HANDHELD_ABSOLUTE_SECONDS - 1
        replay = absolute_store.begin_message(f"{1:032x}", f"{1:032x}", 1, "one")
        self.assertIsInstance(replay, HandheldReplay)
        self.clock.now += 1
        replacement = absolute_store.begin_message(f"{1:032x}", f"{2:032x}", 1, "new")
        self.assertIsInstance(replacement, HandheldRequestClaim)

    def test_capacity_evicts_least_recently_used_non_in_flight_session(self) -> None:
        for value in range(1, 5):
            self._complete(session=value, request=value)
            self.clock.now += 1
        self.store.begin_message(f"{1:032x}", f"{1:032x}", 1, "prompt")

        self._claim(session=5, request=5)
        replacement = self.store.begin_message(f"{2:032x}", f"{20:032x}", 1, "new")
        self.assertIsInstance(replacement, HandheldRequestClaim)

    def test_all_in_flight_sessions_reject_capacity(self) -> None:
        for value in range(1, 5):
            self._claim(session=value, request=value)

        self._assert_error(
            "session_capacity",
            lambda: self.store.begin_message(f"{5:032x}", f"{5:032x}", 1, "fifth"),
        )

    def test_reset_is_idempotent_and_rejects_in_flight(self) -> None:
        self.store.reset(f"{1:032x}")
        claim = self._claim()
        self._assert_error("session_unavailable", lambda: self.store.reset(f"{1:032x}"))
        self.store.abort(claim)
        self.store.reset(f"{1:032x}")
        self.store.reset(f"{1:032x}")
        replacement = self._claim(request=2)
        self.assertEqual(replacement.turn, 1)

    def test_new_store_simulates_process_restart_without_state(self) -> None:
        self._complete()
        restarted = HandheldSessionStore(self.clock)

        claim = restarted.begin_message(f"{1:032x}", f"{2:032x}", 1, "fresh")
        self.assertIsInstance(claim, HandheldRequestClaim)
        self.assertEqual(claim.messages, ())


if __name__ == "__main__":
    unittest.main()
