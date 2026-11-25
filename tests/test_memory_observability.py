from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core import context, orchestrator
from core.brain_request_context import get_active_request_context
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.memory_observability import get_memory_retrieval_diagnostics


DIAGNOSTIC_KEY = "semantic_memory_retrieval"


@pytest.fixture(autouse=True)
def isolate_context_sources(monkeypatch):
    monkeypatch.setattr(context, "build_memory_context", lambda: "")
    monkeypatch.setattr(context, "get_recent_history", lambda **kwargs: [])
    monkeypatch.setattr(context, "get_last_topic", lambda: None)


def _route_through_context(command: str) -> str:
    return context.build_messages(command)[0]["content"]


def test_disabled_semantic_retrieval_is_recorded(monkeypatch):
    monkeypatch.setattr(orchestrator, "route", _route_through_context)
    monkeypatch.setattr(
        context,
        "search_semantic_memories",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("disabled retrieval must not run")
        ),
    )

    result = orchestrator.process_request("what is PostgreSQL")

    assert result.metadata[DIAGNOSTIC_KEY] == {
        "status": "disabled",
        "results_examined": 0,
        "results_selected": 0,
        "selected_memory_ids": [],
        "selected_weighted_similarity_scores": [],
        "similarity_threshold": 0.50,
        "category_labels": [],
    }


def test_permitted_semantic_retrieval_not_invoked_is_recorded(monkeypatch):
    monkeypatch.setattr(orchestrator, "route", lambda command: "safe response")

    result = orchestrator.process_request(
        "what did I tell you about Jarvis memory"
    )

    assert result.metadata[DIAGNOSTIC_KEY]["status"] == "not_run"
    assert result.metadata[DIAGNOSTIC_KEY]["results_examined"] == 0


def test_zero_matching_memories_is_recorded(monkeypatch):
    monkeypatch.setattr(orchestrator, "route", _route_through_context)
    monkeypatch.setattr(
        context,
        "search_semantic_memories",
        lambda *args, **kwargs: [
            {
                "id": 11,
                "content": "private low score memory",
                "category": "project",
                "weighted_similarity": 0.49,
            }
        ],
    )

    result = orchestrator.process_request(
        "what did I tell you about Jarvis memory"
    )
    diagnostics = result.metadata[DIAGNOSTIC_KEY]

    assert diagnostics["status"] == "no_matches"
    assert diagnostics["results_examined"] == 1
    assert diagnostics["results_selected"] == 0
    assert diagnostics["selected_memory_ids"] == []


def test_successful_semantic_retrieval_records_only_safe_fields(monkeypatch):
    prompt_secret = "private user prompt token"
    memory_secret = "private stored memory content"
    monkeypatch.setattr(orchestrator, "route", _route_through_context)
    monkeypatch.setattr(
        context,
        "search_semantic_memories",
        lambda *args, **kwargs: [
            {
                "id": 41,
                "content": memory_secret,
                "category": "project",
                "weighted_similarity": 0.91,
                "embedding": [0.1, 0.2, 0.3],
                "authorization": "Bearer private-credential",
                "conversation_history": ["private prior message"],
            },
            {
                "id": 42,
                "content": "another private memory",
                "category": "untrusted-private-label",
                "weighted_similarity": 0.75,
            },
            {
                "id": 43,
                "content": "below threshold private memory",
                "category": "work",
                "weighted_similarity": 0.25,
            },
        ],
    )

    result = orchestrator.process_request(
        f"what did I tell you about {prompt_secret}"
    )
    diagnostics = result.metadata[DIAGNOSTIC_KEY]

    assert diagnostics == {
        "status": "matched",
        "results_examined": 3,
        "results_selected": 2,
        "selected_memory_ids": [41, 42],
        "selected_weighted_similarity_scores": [0.91, 0.75],
        "similarity_threshold": 0.50,
        "category_labels": ["project", "unknown"],
    }
    serialized = repr(diagnostics)
    assert prompt_secret not in serialized
    assert memory_secret not in serialized
    assert "another private memory" not in serialized
    assert "untrusted-private-label" not in serialized
    assert "private-credential" not in serialized
    assert "private prior message" not in serialized
    assert "0.1" not in serialized


def test_semantic_retrieval_exception_is_recorded_without_private_error(monkeypatch):
    secret = "database password in exception"
    monkeypatch.setattr(orchestrator, "route", _route_through_context)
    monkeypatch.setattr(
        context,
        "search_semantic_memories",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    result = orchestrator.process_request(
        "what did I tell you about Jarvis memory"
    )
    diagnostics = result.metadata[DIAGNOSTIC_KEY]

    assert diagnostics["status"] == "error"
    assert diagnostics["results_examined"] == 0
    assert secret not in repr(diagnostics)


def test_semantic_result_processing_exception_is_recorded(monkeypatch):
    monkeypatch.setattr(orchestrator, "route", _route_through_context)
    monkeypatch.setattr(
        context,
        "search_semantic_memories",
        lambda *args, **kwargs: [
            {
                "id": 51,
                "content": "private malformed memory",
                "category": "project",
                "weighted_similarity": "not-a-number",
            }
        ],
    )

    result = orchestrator.process_request(
        "what did I tell you about Jarvis memory"
    )

    assert result.metadata[DIAGNOSTIC_KEY]["status"] == "error"
    assert result.metadata[DIAGNOSTIC_KEY]["results_examined"] == 1


def test_concurrent_requests_keep_retrieval_diagnostics_isolated(monkeypatch):
    barrier = Barrier(2)

    def mocked_search(query, limit):
        memory_id = 101 if "alpha" in query else 202
        category = "project" if memory_id == 101 else "work"
        barrier.wait(timeout=5)
        return [
            {
                "id": memory_id,
                "content": f"private {memory_id}",
                "category": category,
                "weighted_similarity": 0.80,
            }
        ]

    monkeypatch.setattr(orchestrator, "route", _route_through_context)
    monkeypatch.setattr(context, "search_semantic_memories", mocked_search)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                orchestrator.process_request,
                f"what did I tell you about {name}",
            )
            for name in ("alpha", "beta")
        ]
    diagnostics = [future.result().metadata[DIAGNOSTIC_KEY] for future in futures]

    assert diagnostics[0]["selected_memory_ids"] == [101]
    assert diagnostics[0]["category_labels"] == ["project"]
    assert diagnostics[1]["selected_memory_ids"] == [202]
    assert diagnostics[1]["category_labels"] == ["work"]


def test_sequential_requests_do_not_leak_diagnostics(monkeypatch):
    monkeypatch.setattr(orchestrator, "route", _route_through_context)
    monkeypatch.setattr(
        context,
        "search_semantic_memories",
        lambda *args, **kwargs: [
            {
                "id": 77,
                "content": "private memory",
                "category": "project",
                "weighted_similarity": 0.88,
            }
        ],
    )
    first = orchestrator.process_request(
        "what did I tell you about first request"
    )

    monkeypatch.setattr(orchestrator, "route", lambda command: "safe response")
    second = orchestrator.process_request(
        "what did I tell you about second request"
    )

    assert first.metadata[DIAGNOSTIC_KEY]["selected_memory_ids"] == [77]
    assert second.metadata[DIAGNOSTIC_KEY]["status"] == "not_run"
    assert second.metadata[DIAGNOSTIC_KEY]["selected_memory_ids"] == []
    assert get_memory_retrieval_diagnostics() is None
    assert get_active_request_context() is None


def test_request_local_diagnostics_reset_when_request_raises(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "route",
        lambda command: (_ for _ in ()).throw(RuntimeError("expected failure")),
    )

    with pytest.raises(RuntimeError, match="expected failure"):
        orchestrator.process_request(
            "what did I tell you about Jarvis memory"
        )

    assert get_memory_retrieval_diagnostics() is None
    assert get_active_request_context() is None


def test_diagnostics_do_not_appear_in_response_or_public_brain_status(monkeypatch):
    monkeypatch.setattr(orchestrator, "route", lambda command: "safe response")

    result = orchestrator.process_request(
        "what did I tell you about Jarvis memory"
    )

    assert DIAGNOSTIC_KEY not in result.response
    assert DIAGNOSTIC_KEY not in repr(get_brain_v2_status())
    assert DIAGNOSTIC_KEY not in get_brain_v2_status_response()


def test_malformed_selected_metadata_keeps_arrays_aligned(monkeypatch):
    rows = [
        {"id": "private id", "weighted_similarity": 0.9, "category": "project"},
        {"id": 12, "weighted_similarity": float("inf"), "category": "work"},
        {"id": 13, "weighted_similarity": 0.5, "category": ["private"]},
    ]
    monkeypatch.setattr(context, "search_semantic_memories", lambda *a, **kw: rows)

    def format_results(selected):
        assert selected == rows
        return "original formatted response"

    monkeypatch.setattr(context, "format_semantic_results", format_results)
    monkeypatch.setattr(orchestrator, "route", context._format_semantic_memory)
    result = orchestrator.process_request("tell me more")

    assert result.response == "original formatted response"
    diagnostics = result.metadata[DIAGNOSTIC_KEY]
    assert diagnostics["results_selected"] == 3
    assert diagnostics["selected_memory_ids"] == [None, 12, 13]
    assert diagnostics["selected_weighted_similarity_scores"] == [0.9, None, 0.5]
    assert diagnostics["category_labels"] == ["project", "work", "unknown"]
    assert "private" not in repr(diagnostics)
    assert DIAGNOSTIC_KEY not in repr(result)


@pytest.mark.parametrize("failure", ["unavailable", "search", "format"])
def test_error_uses_caller_threshold(monkeypatch, caplog, failure):
    secret = "private exception payload"

    def fail(*args, **kwargs):
        raise RuntimeError(secret)

    rows = [{"id": 23, "weighted_similarity": 0.9}]
    monkeypatch.setattr(
        context, "search_semantic_memories",
        fail if failure == "search" else lambda *a, **kw: iter(rows),
    )
    if failure != "search":
        monkeypatch.setattr(
            context, "format_semantic_results", fail if failure == "format" else None
        )
    monkeypatch.setattr(
        orchestrator, "route",
        lambda command: context._format_semantic_memory(command, min_similarity=0.8),
    )
    result = orchestrator.process_request("tell me more")

    diagnostics = result.metadata[DIAGNOSTIC_KEY]
    assert diagnostics["status"] == "error"
    assert diagnostics["similarity_threshold"] == 0.8
    assert diagnostics["results_examined"] == (1 if failure == "format" else 0)
    assert secret not in caplog.text


def test_latest_retrieval_replaces_previous_snapshot(monkeypatch):
    rows = iter([[{"id": 77, "weighted_similarity": 0.9}], []])
    monkeypatch.setattr(context, "search_semantic_memories", lambda *a, **kw: next(rows))
    monkeypatch.setattr(context, "format_semantic_results", lambda rows: "matched memory")

    def route(command):
        assert context._format_semantic_memory(command) == "matched memory"
        assert get_memory_retrieval_diagnostics().status == "matched"
        return context._format_semantic_memory(command)

    monkeypatch.setattr(orchestrator, "route", route)
    result = orchestrator.process_request("tell me more")

    assert result.response == context.NO_RELEVANT_SEMANTIC_MEMORY
    diagnostics = result.metadata[DIAGNOSTIC_KEY]
    assert diagnostics["status"] == "no_matches"
    assert diagnostics["results_examined"] == 0
    assert diagnostics["selected_memory_ids"] == []


@pytest.mark.parametrize("search_fails", [False, True])
def test_diagnostic_recording_failure_preserves_response(monkeypatch, caplog, search_fails):
    def fail(*args, **kwargs):
        raise RuntimeError("private diagnostic exception")

    rows = [{"id": 41, "weighted_similarity": 0.75}]
    monkeypatch.setattr(
        context, "search_semantic_memories",
        fail if search_fails else lambda *a, **kw: iter(rows),
    )
    monkeypatch.setattr(context, "format_semantic_results", lambda rows: "matched memory")
    monkeypatch.setattr(context, "record_memory_retrieval_result", fail)
    monkeypatch.setattr(context, "record_memory_retrieval_error", fail)
    monkeypatch.setattr(orchestrator, "route", context._format_semantic_memory)

    result = orchestrator.process_request("tell me more")

    assert result.response == (
        "Semantic memory search unavailable." if search_fails else "matched memory"
    )
    assert "private diagnostic exception" not in caplog.text


def test_diagnostic_snapshot_failure_preserves_response_and_resets_state(monkeypatch):
    def fail():
        raise RuntimeError("snapshot unavailable")

    monkeypatch.setattr(orchestrator, "get_memory_retrieval_diagnostics", fail)
    monkeypatch.setattr(orchestrator, "route", lambda command: "safe response")
    result = orchestrator.process_request("tell me more")

    assert result.response == "safe response"
    assert get_memory_retrieval_diagnostics() is None


def test_flask_chat_dashboard_and_logs_exclude_matched_diagnostics(monkeypatch, caplog):
    import api
    from core import brain
    from skills import dashboard_status_skill as dashboard

    rows = [{"id": 8675309123, "weighted_similarity": 0.987654321}]
    monkeypatch.setattr(context, "search_semantic_memories", lambda *a, **kw: rows)
    monkeypatch.setattr(context, "format_semantic_results", lambda rows: "safe response")
    monkeypatch.setattr(orchestrator, "route", context._format_semantic_memory)
    monkeypatch.setattr(brain, "detect_topic", lambda command: None)
    monkeypatch.setattr(brain, "remember_user_message", lambda message: None)
    monkeypatch.setattr(brain, "remember_assistant_message", lambda message: None)
    monkeypatch.setattr(api, "listen_command", lambda: "tell me more")
    observed = []

    def process(command):
        result = orchestrator.process_request(command)
        observed.append(result.metadata[DIAGNOSTIC_KEY])
        return result

    monkeypatch.setattr(brain, "process_request", process)
    for name in (
        "_check_postgres",
        "_count_semantic_memories",
        "_check_llm_endpoint",
        "_check_embedding_model",
    ):
        monkeypatch.setattr(dashboard, name, lambda: (True, "available"))
    monkeypatch.setattr(dashboard, "get_all_memories", lambda: {})
    monkeypatch.setattr(dashboard, "get_recent_history", lambda **kwargs: [])
    monkeypatch.setattr(dashboard, "get_last_topic", lambda: None)
    monkeypatch.setattr(dashboard, "get_active_model_friendly_name", lambda: "mock")
    for name in (
        "get_model_dashboard_status",
        "get_vision_dashboard_status",
        "get_memory_dashboard_status",
        "get_martybench_dashboard_status",
        "get_device_dashboard_status",
        "get_camera_diagnostics_status",
        "get_calibration_status",
        "get_measurement_status",
        "get_architecture_status",
    ):
        monkeypatch.setattr(dashboard, name, dict)

    caplog.set_level("DEBUG")
    client = api.app.test_client()
    chat_responses = [
        client.post("/text", json={"command": "tell me more"}),
        client.post("/ask", json={"use_voice": False}),
    ]
    for response in chat_responses:
        assert response.status_code == 200
        assert response.get_json() == {"heard": "tell me more", "response": "safe response"}
    assert len(observed) == 2
    assert all(entry["selected_memory_ids"] == [8675309123] for entry in observed)

    status = client.get("/api/status/brain")
    aggregate_status = client.get("/api/status/dashboard")
    assert status.status_code == 200
    assert aggregate_status.status_code == 200
    assert aggregate_status.get_json()["brain"] == status.get_json()
    for output in (
        status.get_data(as_text=True),
        aggregate_status.get_data(as_text=True),
        get_brain_v2_status_response(),
        caplog.text,
    ):
        assert DIAGNOSTIC_KEY not in output
        assert "8675309123" not in output
        assert "0.987654321" not in output
