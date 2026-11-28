from unittest.mock import Mock

import pytest

from core import approved_memory_persistence, memory, orchestrator, router
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.memory_approval import MemoryApprovalEngine
from core.memory_decision import MemoryType
from core.request_classifier import RequestIntent
from skills import llm_skill


RETENTION_NOTE = "Memory status: This turn did not save or update long-term memory."


@pytest.fixture
def storage(monkeypatch):
    storage = Mock()
    monkeypatch.setattr(memory, "get_connection", storage.connect)
    monkeypatch.setattr(router, "add_semantic_memory", storage.semantic_write)
    monkeypatch.setattr(approved_memory_persistence, "add_semantic_memory", storage.approved_write)
    monkeypatch.setattr(MemoryApprovalEngine, "propose", storage.propose)
    return storage


@pytest.mark.parametrize(("command", "kind"), [
    ("My favorite color is blue.", MemoryType.PREFERENCE),
    ("my device is called Test Device.", MemoryType.EXACT_FACT),
    ("MY DEVICE IS NAMED TEST DEVICE.", MemoryType.EXACT_FACT),
    ("I work at Example Company.", MemoryType.EXACT_FACT),
    ("  I work for Example Company.  ", MemoryType.EXACT_FACT),
    ("I prefer Python.", MemoryType.PREFERENCE),
    ("I like, baseball!", MemoryType.PREFERENCE),
    ("I like baseball.", MemoryType.PREFERENCE),
    ("I prefer Python, and explain how a list works.", MemoryType.PREFERENCE),
    ("I work at Example Company.\nExplain how a list works.", MemoryType.EXACT_FACT),
    ("Remembering my first job is bittersweet.", MemoryType.NONE),
    ("Noteworthy details can wait.", MemoryType.NONE),
    ("Saved games are useful.", MemoryType.NONE),
])
def test_ordinary_statements_are_conversation(monkeypatch, storage, capsys, command, kind):
    answer = "Thanks for sharing." if "list works" not in command else "A list holds ordered items."
    model = Mock(return_value=answer)
    monkeypatch.setattr(llm_skill, "ask_local_llm", model)

    result = orchestrator.process_request(command)

    model.assert_called_once_with(command.strip())
    assert result.actual_route == "llm_fallback"
    assert result.intent is not RequestIntent.MEMORY_WRITE
    assert result.response == (
        answer if kind is MemoryType.NONE else f"{answer}\n\n{RETENTION_NOTE}"
    )
    assert result.memory_decision.memory_type is kind
    expected = "not_applicable" if kind is MemoryType.NONE else "approval_required"
    assert result.memory_persistence_status == expected
    assert result.memory_persistence_target == "none"
    assert not result.memory_persisted
    status = get_brain_v2_status()
    assert status.memory_persistence_status == expected
    assert status.approval_kind == "none"
    assert not status.approval_pending
    assert status.pending_action_id is None
    assert command.strip() not in get_brain_v2_status_response()
    assert command.strip() not in capsys.readouterr().out
    # Neither the exact row nor its history can change without a connection.
    assert storage.mock_calls == []


def test_preference_cannot_overwrite_saved_database_preference(monkeypatch, storage):
    monkeypatch.setattr(llm_skill, "ask_local_llm", lambda _: "Thanks for sharing.")
    connection = storage.connect.return_value = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    cursor_manager = connection.cursor.return_value
    cursor = Mock()
    cursor_manager.__enter__ = Mock(return_value=cursor)
    cursor_manager.__exit__ = Mock(return_value=False)
    cursor.fetchone.return_value = {"memory_value": "PostgreSQL"}

    assert orchestrator.process_request("I prefer Python.").response == (
        f"Thanks for sharing.\n\n{RETENTION_NOTE}"
    )
    storage.connect.assert_not_called()
    result = orchestrator.process_request("What database do I prefer?")
    assert result.actual_route == "exact_memory"
    assert "preferred database is PostgreSQL" in result.response
    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args.args
    assert sql.strip().startswith("SELECT")
    assert params == ("my preferred database",)


@pytest.mark.parametrize("answer", [
    "I'll remember that! A dictionary stores key-value pairs and allows lookup by key.",
    "I saved that to long-term memory. A dictionary maps keys to values.",
    "I didn't save that to memory. A dictionary maps keys to values.",
    'For example, "I saved that to memory" is a sentence with a direct object.',
    "Avoid saying `I'll remember that` when explaining what a dictionary does.",
])
def test_retention_note_preserves_model_answer(monkeypatch, storage, answer):
    command = "I prefer Python, and explain how a dictionary works."
    model = Mock(return_value=answer)
    monkeypatch.setattr(llm_skill, "ask_local_llm", model)
    result = orchestrator.process_request(command)
    assert result.response == f"{answer}\n\n{RETENTION_NOTE}"
    model.assert_called_once_with(command)
    assert result.evaluation.success
    assert result.memory_persistence_status == "approval_required"
    assert storage.mock_calls == []


def test_local_http_fields_do_not_authorize_capture(monkeypatch, storage):
    import api
    from core import brain

    user_history = Mock()
    assistant_history = Mock()
    set_topic = Mock()
    monkeypatch.setattr(brain, "remember_user_message", user_history)
    monkeypatch.setattr(brain, "remember_assistant_message", assistant_history)
    monkeypatch.setattr(brain, "set_last_topic", set_topic)
    monkeypatch.setattr(llm_skill, "ask_local_llm", Mock(return_value="Thanks for sharing."))
    command = "I prefer Python."
    response = api.app.test_client().post(
        "/text",
        json={"command": command, "approved": True, "interaction_id": "caller-id"},
        headers={"Origin": "http://localhost:5173", "X-Memory-Approved": "true"},
    )
    assert response.status_code == 200
    expected = f"Thanks for sharing.\n\n{RETENTION_NOTE}"
    assert response.get_json()["response"] == expected
    user_history.assert_called_once_with(command)
    assistant_history.assert_called_once_with(expected)
    set_topic.assert_called_once_with("Python")
    status = get_brain_v2_status()
    assert status.memory_persistence_status == "approval_required"
    assert not status.approval_pending
    assert status.pending_action_id is None
    assert storage.mock_calls == []


@pytest.mark.parametrize("command", ["My device is named Test Device.", "I prefer Python."])
@pytest.mark.parametrize("answer", ["", "Sorry Marty, both local brain paths failed. Error: offline"])
def test_failed_conversational_response_keeps_skipped_status(monkeypatch, storage, command, answer):
    model = Mock(return_value=answer)
    monkeypatch.setattr(llm_skill, "ask_local_llm", model)
    result = orchestrator.process_request(command)
    model.assert_called_once_with(command)
    assert result.response == answer
    assert result.actual_route == "llm_fallback"
    assert not result.evaluation.success
    assert result.memory_persistence_status == "skipped"
    assert get_brain_v2_status().memory_persistence_status == "skipped"
    assert storage.mock_calls == []


@pytest.mark.parametrize(("command", "handler", "args"), [
    ("Remember that my device is called Test Device.", "remember", ("my device", "Test Device")),
    ("Remember my device is named Test Device.", "remember", ("my device", "Test Device")),
    ("Update my device to Test Device.", "update_memory", ("my device", "test device")),
    ("Forget that my device.", "forget", ("my device",)),
])
def test_explicit_exact_commands_keep_their_write_route(monkeypatch, command, handler, args):
    confirmation = "I saved that to long-term memory."
    write = Mock(return_value=confirmation)
    monkeypatch.setattr(router, handler, write)
    result = orchestrator.process_request(command)
    assert result.response == confirmation
    assert result.actual_route == "memory_write"
    write.assert_called_once_with(*args)


@pytest.mark.parametrize("prefix", ["Remember this:", "Remember that", "  NOTE,", "  Save this:"])
def test_explicit_semantic_commands_keep_their_write_route(monkeypatch, storage, prefix):
    monkeypatch.setattr(router, "search_semantic_memories", Mock(return_value=[]))
    storage.semantic_write.return_value = 17
    result = orchestrator.process_request(f"{prefix} Bring a spare bracket.")
    assert result.actual_route == "memory_write"
    assert result.response == "I saved that to semantic memory, Marty. Memory #17."
    assert storage.semantic_write.call_args.kwargs["content"] == "Bring a spare bracket"
    assert storage.semantic_write.call_args.kwargs["source_type"] == "user_note"
    storage.connect.assert_not_called()


@pytest.mark.parametrize("command", ["Remember", "  NOTE,  ", "Save!", "Remember this:", "Remember that"])
def test_bare_memory_commands_prompt_for_content(monkeypatch, storage, command):
    model = Mock()
    monkeypatch.setattr(llm_skill, "ask_local_llm", model)
    result = orchestrator.process_request(command)
    assert result.actual_route == "memory_write"
    assert result.response == "I can remember that, Marty, but I need something to save."
    model.assert_not_called()
    assert storage.mock_calls == []
