"""Review and approve project notes from a dedicated local terminal."""

from __future__ import annotations

import argparse
import os
import re
import sys
import termios
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TextIO
from uuid import uuid4

from core.memory_approval import (
    MAX_CANDIDATE_CHARS,
    InteractionSource,
    MemoryApprovalEngine,
    MemoryApprovalError,
    MemoryProposal,
)


_PROPOSE = "propose memory "
_CONFIRMATION = re.compile(r"(approve|cancel) memory ([a-f0-9]{32})")
_MAX_LINE_CHARS = len(_PROPOSE) + MAX_CANDIDATE_CHARS
_UNSAFE_CATEGORIES = {"Cc", "Cf", "Cs", "Zl", "Zp"}
_OUTCOME_MESSAGES = {
    "persisted": "Persisted. The approved memory was saved.",
    "duplicate": "Duplicate. No new memory was saved.",
    "unauthorized": "Unauthorized. No live proposal matched that approval.",
    "lookup_failed": "Lookup failed. No write was attempted.",
    "persistence_failed": "Persistence failed.",
}


class _ConsoleArguments(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        super().error("invalid startup options. Use --help for usage.")


@contextmanager
def _hidden_input(stdin: TextIO) -> Iterator[None]:
    """Prevent the terminal driver from echoing unvalidated input."""
    fd = stdin.fileno()
    original = termios.tcgetattr(fd)
    settings = original.copy()
    settings[3] &= ~(termios.ECHO | termios.ECHONL)
    try:
        termios.tcsetattr(fd, termios.TCSANOW, settings)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, original)


def _notice(output: TextIO, message: str) -> None:
    print(f"Console: {message}", file=output, flush=True)


def _terminal_columns(output: TextIO) -> int:
    columns = os.get_terminal_size(output.fileno()).columns
    return columns or 40


def _review(output: TextIO, proposal: MemoryProposal, columns: int) -> None:
    _notice(output, f"Proposal ID: {proposal.proposal_id}")
    _notice(output, f"Category: {proposal.category}")
    lifetime = proposal.expires_at - proposal.created_at
    _notice(output, f"Expires after {lifetime:g} seconds. This note has not yet been saved.")
    _notice(output, "Exact candidate follows. Join the text between each pair of bars.")
    # Leave a spare column and conservatively budget two cells for non-ASCII.
    width = columns - 3
    chunk: list[str] = []
    cells = 0
    for character in proposal.text:
        cost = 1 if character.isascii() else 2
        if cells + cost > width:
            print(f"|{''.join(chunk)}|", file=output, flush=True)
            chunk.clear()
            cells = 0
        chunk.append(character)
        cells += cost
    if chunk:
        print(f"|{''.join(chunk)}|", file=output, flush=True)


def _run_session(stdin: TextIO, output: TextIO, *, persist: bool) -> int:
    engine = MemoryApprovalEngine()
    adapter = None
    if persist:
        from core.approved_memory_persistence import ApprovedMemoryPersistence

        adapter = ApprovedMemoryPersistence(engine)

    interaction = {
        "interaction_id": uuid4().hex,
        "source": InteractionSource.TRUSTED_LOCAL_USER,
    }
    pending_id = None
    mode = "PERSISTENCE ENABLED" if persist else "DRY RUN"
    _notice(output, f"{mode}. Input is hidden. Type help for commands.")
    limit = _MAX_LINE_CHARS + 2

    try:
        while True:
            print("memory> ", end="", file=output, flush=True)
            line = stdin.readline(limit)
            # The terminal does not echo the Enter key in hidden-input mode.
            print(file=output, flush=True)
            if not line:
                return 0
            command = line.removesuffix("\n")
            if len(command) > _MAX_LINE_CHARS:
                while line and not line.endswith("\n"):
                    line = stdin.readline(limit)
                _notice(output, "Command too long.")
                continue
            if any(unicodedata.category(char) in _UNSAFE_CATEGORIES for char in command):
                _notice(output, "Unsafe terminal character. Command rejected.")
                continue
            if command == "exit":
                return 0
            if command == "help":
                _notice(output, "help | propose memory <text> | approve memory <id> | "
                        "cancel memory <id> | status | exit")
                continue
            if command == "status":
                if engine.cleanup_expired():
                    pending_id = None
                detail = f"Pending proposal {pending_id}" if pending_id else "No pending proposal"
                _notice(output, f"{mode}. {detail}.")
                continue
            if command.startswith(_PROPOSE):
                columns = _terminal_columns(output)
                if columns < 8:
                    _notice(output, "Widen the terminal before proposing a note.")
                    continue
                try:
                    proposal = engine.propose(**interaction, text=command[len(_PROPOSE):])
                except MemoryApprovalError as error:
                    _notice(output, f"Proposal rejected ({error.code}).")
                else:
                    pending_id = proposal.proposal_id
                    _review(output, proposal, columns)
                continue
            confirmation = _CONFIRMATION.fullmatch(command)
            if confirmation is None:
                _notice(output, "Unknown command. Type help.")
                continue

            try:
                if confirmation[1] == "cancel":
                    engine.cancel(**interaction, command=command)
                    _notice(output, "Cancelled. No memory was saved.")
                elif adapter is not None:
                    result = adapter.approve_and_persist(**interaction, command=command)
                    message = _OUTCOME_MESSAGES[result.status]
                    if result.commit_uncertain:
                        message += " Commit outcome is uncertain. No retry was attempted."
                    _notice(output, message)
                else:
                    engine.approve(**interaction, command=command)
                    _notice(output, "Approved in dry run. No memory was saved.")
            except MemoryApprovalError:
                _notice(output, _OUTCOME_MESSAGES["unauthorized"])
            except KeyboardInterrupt:
                if persist and confirmation[1] == "approve":
                    _notice(output, "Approval interrupted. Commit outcome may be uncertain.")
                raise
            if pending_id == confirmation[2]:
                pending_id = None
    except KeyboardInterrupt:
        _notice(output, "Session interrupted.")
        return 130
    finally:
        if pending_id is not None:
            try:
                engine.cancel(**interaction, command=f"cancel memory {pending_id}")
            except MemoryApprovalError:
                pass  # The session's proposal is already expired or consumed.


def main(argv: Sequence[str] | None = None) -> int:
    parser = _ConsoleArguments(description=__doc__, allow_abbrev=False)
    parser.add_argument("--persist", action="store_true", help="enable actual memory storage")
    options = parser.parse_args(argv)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        _notice(sys.stdout, "An interactive terminal is required for input and output.")
        return 2
    try:
        with _hidden_input(sys.stdin):
            return _run_session(sys.stdin, sys.stdout, persist=options.persist)
    except KeyboardInterrupt:
        _notice(sys.stdout, "Session interrupted.")
        return 130
    except (OSError, termios.error):
        _notice(sys.stdout, "Terminal I/O failed. Storage may be uncertain if approval was in progress.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
