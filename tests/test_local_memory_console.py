import logging
import re
from collections.abc import Callable
from contextlib import nullcontext
from io import StringIO
from unittest.mock import Mock

import pytest

from core import approved_memory_persistence as persistence
from core.memory_approval import MemoryApprovalEngine, MemoryApprovalError
from tools import local_memory_console as console


class Terminal(StringIO):
    def isatty(self):
        return True


@pytest.fixture
def session(monkeypatch):
    now = [100.0]
    engines = []

    def make_engine():
        engine = MemoryApprovalEngine(clock=lambda: now[0])
        engine.propose = Mock(wraps=engine.propose)
        engines.append(engine)
        return engine

    search = Mock(return_value=[])
    write = Mock(return_value=17)
    monkeypatch.setattr(console, "MemoryApprovalEngine", make_engine)
    monkeypatch.setattr(persistence, "search_semantic_memories", search)
    monkeypatch.setattr(persistence, "add_semantic_memory", write)
    return now, engines, search, write


def run_console(monkeypatch, lines, args=(), input_tty=True, output_tty=True, columns=80):
    output = Terminal() if output_tty else StringIO()
    source = Terminal() if input_tty else StringIO()
    iterator = iter(lines)

    def readline(size):
        line = next(iterator, "")
        if isinstance(line, Callable):
            line = line()
        if "{id}" in line:
            proposal_ids = re.findall(r"Proposal ID: ([0-9a-f]{32})", output.getvalue())
            line = line.replace("{id}", proposal_ids[-1])
        return line

    source.readline = readline
    monkeypatch.setattr(console.sys, "stdin", source)
    monkeypatch.setattr(console.sys, "stdout", output)
    monkeypatch.setattr(console, "_hidden_input", lambda stdin: nullcontext())
    monkeypatch.setattr(console, "_terminal_columns", lambda output: columns)
    return console.main(list(args)), output.getvalue()


def test_default_dry_run_exercises_approval_without_storage(monkeypatch, session):
    _, engines, search, write = session
    status, output = run_console(monkeypatch, [
        "propose memory Build a fixture\n", "status\n",
        "approve memory {id}\n", "approve memory {id}\n", "exit\n",
    ])
    assert status == 0
    assert "DRY RUN" in output
    assert "Approved in dry run. No memory was saved." in output
    assert "Unauthorized" in output
    assert len(engines) == 1
    search.assert_not_called()
    write.assert_not_called()


@pytest.mark.parametrize("input_tty,output_tty", [(False, True), (True, False)])
def test_noninteractive_streams_are_rejected(monkeypatch, session, input_tty, output_tty):
    status, output = run_console(monkeypatch, [], ["--persist"], input_tty, output_tty)
    assert status != 0
    assert "interactive terminal" in output
    assert not session[1]


def test_console_generates_a_new_opaque_identity_for_each_session(monkeypatch, session):
    _, engines, _, _ = session
    for _ in range(2):
        run_console(monkeypatch, ["propose memory Build a fixture\n", "exit\n"])
    one, two = [engine.propose.call_args.kwargs for engine in engines]
    assert len(one["interaction_id"]) == len(two["interaction_id"]) == 32
    assert one["interaction_id"] != two["interaction_id"]
    assert all(fields["source"] is console.InteractionSource.TRUSTED_LOCAL_USER
               for fields in (one, two))


def test_review_and_persistence_preserve_exact_whitespace(monkeypatch, session, caplog):
    _, _, _, write = session
    text = "  Private jig note  "
    caplog.set_level(logging.DEBUG)
    _, output = run_console(monkeypatch, [
        f"propose memory {text}\n", "status\n", "approve memory {id}\n",
    ], ["--persist"])
    assert f"|{text}|" in output
    assert output.count(text) == 1
    assert "Category: project" in output
    assert "120 seconds" in output
    assert "has not yet been saved" in output
    assert "Persisted" in output
    assert text.strip() not in caplog.text
    assert "approve memory" not in caplog.text
    assert write.call_args.kwargs["content"] == text


def test_only_explicit_approval_can_write_and_cancellation_consumes(monkeypatch, session):
    _, engines, search, write = session
    _, output = run_console(monkeypatch, [
        "We should build a fixture.\n", "approve\n",
        "propose memory Build first fixture\n",
        "propose memory Replacement fixture\n", "status\n",
        "cancel memory {id}\n", "approve memory {id}\n", "exit\n",
    ], ["--persist"])
    assert "Unknown command" in output
    assert "already_pending" in output
    assert "Replacement fixture" not in output
    assert "Cancelled" in output and "Unauthorized" in output
    assert engines[0].propose.call_count == 2
    search.assert_not_called()
    write.assert_not_called()


def test_expired_proposals_cannot_be_written(monkeypatch, session):
    now, _, search, _ = session

    def expire_and_confirm():
        now[0] += 120
        return "approve memory {id}\n"

    _, output = run_console(monkeypatch, [
        "propose memory Build first fixture\n", expire_and_confirm, "status\n",
    ], ["--persist"])
    assert "Unauthorized" in output
    assert "No pending proposal" in output
    search.assert_not_called()


@pytest.mark.parametrize("failure,message", [
    ("duplicate", "Duplicate"),
    ("lookup", "Lookup failed"),
    ("writer", "Persistence failed. Commit outcome is uncertain"),
])
def test_persistence_outcomes_and_no_retry(monkeypatch, session, failure, message):
    _, _, search, write = session
    if failure == "duplicate":
        search.return_value = [{"content": "Build a fixture", "similarity": 1.0}]
    elif failure == "lookup":
        search.side_effect = RuntimeError("private lookup content")
    else:
        write.side_effect = RuntimeError("private write content")
    _, output = run_console(monkeypatch, [
        "propose memory Build a fixture\n", "approve memory {id}\n",
        "approve memory {id}\n",
    ], ["--persist"])
    assert message in output
    assert "Persisted" not in output
    assert "private " not in output
    assert "Unauthorized" in output
    search.assert_called_once()
    assert write.call_count == (1 if failure == "writer" else 0)


@pytest.mark.parametrize("character", ["\x1b", "\t", "\x00", "\u202e", "\u2028"])
def test_terminal_control_characters_are_rejected(monkeypatch, session, character):
    _, engines, _, _ = session
    _, output = run_console(monkeypatch, [f"propose memory before{character}after\n"])
    assert "Unsafe terminal character" in output
    assert character not in output
    engines[0].propose.assert_not_called()


def test_candidate_review_frames_console_like_text(monkeypatch, session):
    text = "first section followed by Persisted. No pending proposal."
    _, output = run_console(monkeypatch, [f"propose memory {text}\n"], columns=30)
    lines = [line for line in output.splitlines() if line.startswith("|")]
    assert "".join(line[1:-1] for line in lines) == text
    assert all(line.endswith("|") and len(line) < 30 for line in lines)
    assert "Persisted." not in output.splitlines()


@pytest.mark.parametrize("ending", ["exit\n", "", KeyboardInterrupt])
def test_session_cleanup_on_exit_eof_and_interrupt(monkeypatch, session, ending):
    _, engines, _, _ = session

    def finish():
        if ending is KeyboardInterrupt:
            raise KeyboardInterrupt
        return ending

    status, _ = run_console(monkeypatch, ["propose memory A fixture\n", finish])
    assert status == (130 if ending is KeyboardInterrupt else 0)
    engine = engines[0]
    interaction_id = engine.propose.call_args.kwargs["interaction_id"]
    try:
        engine.propose(interaction_id=interaction_id,
                       source=console.InteractionSource.TRUSTED_LOCAL_USER, text="New note")
    except MemoryApprovalError as error:
        pytest.fail(f"Session left a pending proposal: {error.code}")


def test_oversized_command_remainder_is_discarded(monkeypatch, session):
    _, engines, _, _ = session
    _, output = run_console(monkeypatch, [
        "propose memory " + "a" * 1002, "exit\n", "help\n", "exit\n",
    ])
    assert "Command too long" in output
    assert "help | propose memory" in output
    engines[0].propose.assert_not_called()


def test_interrupted_persistence_reports_possible_uncertainty(monkeypatch, session):
    _, _, _, write = session
    write.side_effect = KeyboardInterrupt
    status, output = run_console(monkeypatch, [
        "propose memory A fixture\n", "approve memory {id}\n",
    ], ["--persist"])
    assert status == 130
    assert "Commit outcome may be uncertain" in output
    assert "Persisted" not in output
    write.assert_called_once()


def test_terminal_echo_settings_are_restored_on_interruption(monkeypatch):
    flags = console.termios.ECHO | console.termios.ECHONL | console.termios.ICANON
    original = [0, 0, 0, flags, 0, 0, []]
    monkeypatch.setattr(console.termios, "tcgetattr", Mock(return_value=original))
    set_settings = Mock()
    monkeypatch.setattr(console.termios, "tcsetattr", set_settings)
    stdin = Mock()
    stdin.fileno.return_value = 10
    with pytest.raises(KeyboardInterrupt), console._hidden_input(stdin):
        raise KeyboardInterrupt
    assert set_settings.call_args_list[0].args[2][3] == console.termios.ICANON
    assert set_settings.call_args_list[1].args[2] == original


def test_startup_options_cannot_supply_interaction_identity(capsys):
    with pytest.raises(SystemExit) as error:
        console.main(["--interaction-id", "private value"])
    assert error.value.code == 2
    assert "private value" not in capsys.readouterr().err
