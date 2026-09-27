from core import orchestrator
from core.memory_decision import MemoryDecision, MemoryType
from core.memory_persistence import (
    PROJECT_NOTE_AUTO_SAVE_THRESHOLD,
    determine_persistence,
    persist_project_note,
)


PROJECT_NOTE = "We should build satellite tracking someday."


def _project_decision(confidence=0.72):
    return MemoryDecision(True, MemoryType.PROJECT_NOTE, confidence, "project idea")


def test_high_confidence_project_note_persists_after_successful_route(monkeypatch):
    added = []
    monkeypatch.setattr(orchestrator, "route", lambda command: "successful response")
    monkeypatch.setattr("core.memory_persistence.search_semantic_memories", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: added.append(kwargs) or 42,
    )

    result = orchestrator.process_request(PROJECT_NOTE)

    assert len(added) == 1
    assert added[0]["source_type"] == "project_note"
    assert added[0]["metadata"] == {
        "source": "brain_v2",
        "capture_method": "automatic_project_note",
    }
    assert result.response == "successful response"
    assert result.memory_persisted is True
    assert result.memory_persistence_status == "persisted"


def test_duplicate_project_note_is_not_added(monkeypatch):
    added = []
    monkeypatch.setattr(
        "core.memory_persistence.search_semantic_memories",
        lambda *args, **kwargs: [{"content": PROJECT_NOTE, "similarity": 1.0}],
    )
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: added.append(kwargs),
    )

    result = persist_project_note(PROJECT_NOTE, _project_decision())

    assert added == []
    assert result.status == "duplicate"
    assert result.persisted is False


def test_project_note_below_threshold_is_skipped(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.memory_persistence.search_semantic_memories",
        lambda *args, **kwargs: calls.append("search"),
    )
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: calls.append("add"),
    )

    result = persist_project_note(
        PROJECT_NOTE,
        _project_decision(PROJECT_NOTE_AUTO_SAVE_THRESHOLD - 0.01),
    )

    assert calls == []
    assert result.status == "skipped"
    assert result.persisted is False


def test_personal_facts_preferences_and_explicit_commands_do_not_auto_persist(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.memory_persistence.search_semantic_memories",
        lambda *args, **kwargs: calls.append("search"),
    )
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: calls.append("add"),
    )
    monkeypatch.setattr(orchestrator, "route", lambda command: "legacy response")

    for command in (
        "My new phone is a Samsung S26 Ultra",
        "I prefer SQL Server",
        "remember that Kelly likes tea",
    ):
        result = orchestrator.process_request(command)
        assert result.response == "legacy response"
        assert result.memory_persisted is False
        assert result.memory_persistence_status == "not_applicable"

    assert calls == []


def test_route_exception_prevents_persistence_and_propagates(monkeypatch):
    calls = []
    monkeypatch.setattr(orchestrator, "route", lambda command: (_ for _ in ()).throw(RuntimeError("route failed")))
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: calls.append(kwargs),
    )

    try:
        orchestrator.process_request(PROJECT_NOTE)
    except RuntimeError as error:
        assert str(error) == "route failed"
    else:
        raise AssertionError("route exception was swallowed")

    assert calls == []


def test_failed_evaluation_prevents_persistence(monkeypatch):
    calls = []
    monkeypatch.setattr(orchestrator, "route", lambda command: "")
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: calls.append(kwargs),
    )

    result = orchestrator.process_request(PROJECT_NOTE)

    assert result.memory_persisted is False
    assert result.memory_persistence_status == "skipped"
    assert calls == []


def test_persistence_failure_preserves_response_and_hides_raw_error(monkeypatch):
    secret_error = "database password should not leak"
    monkeypatch.setattr(orchestrator, "route", lambda command: "successful response")
    monkeypatch.setattr("core.memory_persistence.search_semantic_memories", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError(secret_error)),
    )

    result = orchestrator.process_request(PROJECT_NOTE)

    assert result.response == "successful response"
    assert result.memory_persisted is False
    assert result.memory_persistence_status == "failed"
    assert secret_error not in repr(result.metadata)


def test_repeated_project_note_is_blocked_by_duplicate_protection(monkeypatch):
    stored = []
    monkeypatch.setattr(
        "core.memory_persistence.search_semantic_memories",
        lambda *args, **kwargs: stored.copy(),
    )
    monkeypatch.setattr(
        "core.memory_persistence.add_semantic_memory",
        lambda **kwargs: stored.append({"content": kwargs["content"], "similarity": 1.0}) or 1,
    )

    first = persist_project_note(PROJECT_NOTE, _project_decision())
    second = persist_project_note(PROJECT_NOTE, _project_decision())

    assert first.status == "persisted"
    assert second.status == "duplicate"
    assert len(stored) == 1


def test_persistence_decision_uses_project_threshold_only():
    non_project = MemoryDecision(True, MemoryType.EXACT_FACT, 1.0, "fact")

    assert determine_persistence(non_project).persist is False
    assert determine_persistence(_project_decision(PROJECT_NOTE_AUTO_SAVE_THRESHOLD)).persist is True
