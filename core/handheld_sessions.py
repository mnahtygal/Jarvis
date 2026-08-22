from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Literal


MAX_HANDHELD_SESSIONS = 4
MAX_HANDHELD_TURNS = 6
MAX_HANDHELD_CONTENT_BYTES = 16_384
HANDHELD_IDLE_SECONDS = 30 * 60
HANDHELD_ABSOLUTE_SECONDS = 4 * 60 * 60


SessionErrorCode = Literal[
    "request_in_progress",
    "session_unavailable",
    "request_conflict",
    "turn_conflict",
    "session_capacity",
]


class HandheldSessionError(Exception):
    def __init__(self, code: SessionErrorCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class HandheldTurn:
    request_id: str
    turn: int
    prompt: str
    response: str
    truncated: bool


@dataclass(frozen=True)
class HandheldRequestClaim:
    session_id: str
    request_id: str
    turn: int
    prompt: str
    generation: int
    messages: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class HandheldReplay:
    turn: int
    response: str
    truncated: bool


@dataclass
class _InFlight:
    request_id: str
    turn: int
    prompt: str


@dataclass
class _Session:
    session_id: str
    created_at: float
    last_activity: float
    generation: int
    turns: list[HandheldTurn] = field(default_factory=list)
    in_flight: _InFlight | None = None


class HandheldSessionStore:
    """Bounded, process-local conversation state for the handheld v2 route."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}
        self._next_generation = 1

    def begin_message(
        self,
        session_id: str,
        request_id: str,
        turn: int,
        prompt: str,
    ) -> HandheldRequestClaim | HandheldReplay:
        now = self._clock()
        with self._lock:
            self._expire(now)
            existing = self._find_request(request_id)
            if existing is not None:
                owner, completed, pending = existing
                if owner.session_id != session_id:
                    raise HandheldSessionError("request_conflict")
                if completed is not None:
                    if completed.turn != turn or completed.prompt != prompt:
                        raise HandheldSessionError("request_conflict")
                    owner.last_activity = now
                    return HandheldReplay(
                        turn=completed.turn,
                        response=completed.response,
                        truncated=completed.truncated,
                    )
                if pending is not None:
                    if pending.turn != turn or pending.prompt != prompt:
                        raise HandheldSessionError("request_conflict")
                    raise HandheldSessionError("request_in_progress")

            session = self._sessions.get(session_id)
            if session is None:
                if turn != 1:
                    raise HandheldSessionError("turn_conflict")
                self._make_room()
                session = _Session(
                    session_id=session_id,
                    created_at=now,
                    last_activity=now,
                    generation=self._next_generation,
                )
                self._next_generation += 1
                self._sessions[session_id] = session
            elif session.in_flight is not None:
                raise HandheldSessionError("session_unavailable")

            expected_turn = len(session.turns) + 1
            if turn != expected_turn or turn > MAX_HANDHELD_TURNS:
                raise HandheldSessionError("turn_conflict")

            session.in_flight = _InFlight(request_id, turn, prompt)
            session.last_activity = now
            messages = tuple(
                item
                for completed_turn in session.turns
                for item in (
                    ("user", completed_turn.prompt),
                    ("assistant", completed_turn.response),
                )
            )
            return HandheldRequestClaim(
                session_id=session_id,
                request_id=request_id,
                turn=turn,
                prompt=prompt,
                generation=session.generation,
                messages=messages,
            )

    def commit(
        self,
        claim: HandheldRequestClaim,
        response: str,
        truncated: bool,
    ) -> HandheldReplay:
        now = self._clock()
        with self._lock:
            session = self._sessions.get(claim.session_id)
            if not self._claim_matches(session, claim):
                raise HandheldSessionError("session_unavailable")
            assert session is not None

            content_bytes = sum(
                len(turn.prompt.encode("utf-8")) + len(turn.response.encode("utf-8"))
                for turn in session.turns
            )
            content_bytes += len(claim.prompt.encode("utf-8"))
            content_bytes += len(response.encode("utf-8"))
            if content_bytes > MAX_HANDHELD_CONTENT_BYTES:
                self._clear_in_flight(session)
                raise HandheldSessionError("session_unavailable")

            completed = HandheldTurn(
                request_id=claim.request_id,
                turn=claim.turn,
                prompt=claim.prompt,
                response=response,
                truncated=truncated,
            )
            session.turns.append(completed)
            self._clear_in_flight(session)
            session.last_activity = now
            return HandheldReplay(claim.turn, response, truncated)

    def abort(self, claim: HandheldRequestClaim) -> None:
        with self._lock:
            session = self._sessions.get(claim.session_id)
            if self._claim_matches(session, claim):
                assert session is not None
                self._clear_in_flight(session)
                session.last_activity = self._clock()

    def reset(self, session_id: str) -> None:
        now = self._clock()
        with self._lock:
            self._expire(now)
            session = self._sessions.get(session_id)
            if session is None:
                return
            if session.in_flight is not None:
                raise HandheldSessionError("session_unavailable")
            self._remove_session(session_id)

    def _make_room(self) -> None:
        if len(self._sessions) < MAX_HANDHELD_SESSIONS:
            return
        candidates = [
            session for session in self._sessions.values() if session.in_flight is None
        ]
        if not candidates:
            raise HandheldSessionError("session_capacity")
        oldest = min(candidates, key=lambda session: session.last_activity)
        self._remove_session(oldest.session_id)

    def _expire(self, now: float) -> None:
        expired = [
            session.session_id
            for session in self._sessions.values()
            if session.in_flight is None
            and (
                now - session.last_activity >= HANDHELD_IDLE_SECONDS
                or now - session.created_at >= HANDHELD_ABSOLUTE_SECONDS
            )
        ]
        for session_id in expired:
            self._remove_session(session_id)

    def _find_request(
        self,
        request_id: str,
    ) -> tuple[_Session, HandheldTurn | None, _InFlight | None] | None:
        for session in self._sessions.values():
            if session.in_flight is not None and session.in_flight.request_id == request_id:
                return session, None, session.in_flight
            for turn in session.turns:
                if turn.request_id == request_id:
                    return session, turn, None
        return None

    @staticmethod
    def _claim_matches(
        session: _Session | None,
        claim: HandheldRequestClaim,
    ) -> bool:
        if session is None or session.generation != claim.generation:
            return False
        pending = session.in_flight
        return (
            pending is not None
            and pending.request_id == claim.request_id
            and pending.turn == claim.turn
            and pending.prompt == claim.prompt
        )

    @staticmethod
    def _clear_in_flight(session: _Session) -> None:
        if session.in_flight is not None:
            session.in_flight.prompt = ""
            session.in_flight.request_id = ""
            session.in_flight = None

    def _remove_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        if session.in_flight is not None:
            self._clear_in_flight(session)
        for index, turn in enumerate(session.turns):
            session.turns[index] = HandheldTurn("", turn.turn, "", "", turn.truncated)
        session.turns.clear()
        session.session_id = ""
