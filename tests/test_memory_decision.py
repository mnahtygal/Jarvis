from core import orchestrator
from core.memory_decision import MemoryType, decide_memory
from core.request_classifier import classify_request


def test_memory_decisions_are_deterministic_and_bounded():
    cases = {
        "remember that Kelly likes tea": (True, MemoryType.EXPLICIT_MEMORY_COMMAND),
        "my favorite color is blue": (True, MemoryType.PREFERENCE),
        "I work at GM": (True, MemoryType.EXACT_FACT),
        "I prefer SQL Server": (True, MemoryType.PREFERENCE),
        "My new phone is a Samsung S26 Ultra.": (True, MemoryType.EXACT_FACT),
        "We should build satellite tracking someday.": (True, MemoryType.PROJECT_NOTE),
        "I'm watching Captain America.": (False, MemoryType.NONE),
        "I'm drinking coffee.": (False, MemoryType.NONE),
        "What is PostgreSQL?": (False, MemoryType.NONE),
        "What should we build later?": (False, MemoryType.NONE),
        "brain status": (False, MemoryType.NONE),
    }

    for command, expected in cases.items():
        classification = classify_request(command)
        first = decide_memory(command, classification)
        second = decide_memory(command, classification)

        assert (first.should_store, first.memory_type) == expected
        assert first == second
        assert 0.0 <= first.confidence <= 1.0
        assert first.reason
        assert len(first.reason) <= 40


def test_memory_decision_has_no_persistence_side_effects(monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("memory decision attempted persistence")

    monkeypatch.setattr("core.memory.remember", unexpected_call)
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", unexpected_call)
    monkeypatch.setattr(orchestrator, "route", lambda command: "existing response")

    result = orchestrator.process_request("remember that Kelly likes tea")

    assert result.response == "existing response"
    assert result.memory_decision.should_store is True
    assert result.metadata["should_store_memory"] is True


def test_memory_decision_does_not_change_router_response_or_call_count(monkeypatch):
    calls = []

    def fake_route(command):
        calls.append(command)
        return "router response"

    monkeypatch.setattr(orchestrator, "route", fake_route)

    result = orchestrator.process_request("my favorite color is blue")

    assert calls == ["my favorite color is blue"]
    assert result.response == "router response"
    assert result.memory_decision.memory_type is MemoryType.PREFERENCE
