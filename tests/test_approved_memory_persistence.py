from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from unittest.mock import Mock

import pytest

from core import approved_memory_persistence as persistence, semantic_memory
from core.memory_approval import InteractionSource, MemoryApprovalEngine, ProposalStatus


LOCAL = InteractionSource.TRUSTED_LOCAL_USER
TEXT = "  Plan a new fixture.\n"


@pytest.fixture
def setup(monkeypatch):
    now = [100.0]
    engine = MemoryApprovalEngine(clock=lambda: now[0])
    storage = Mock()
    storage.search.return_value = []
    storage.write.return_value = 17
    monkeypatch.setattr(persistence, "search_semantic_memories", storage.search)
    monkeypatch.setattr(persistence, "add_semantic_memory", storage.write)
    adapter = persistence.ApprovedMemoryPersistence(engine)
    return engine, adapter, storage, now


def propose(engine):
    return engine.propose(interaction_id="local-1", source=LOCAL, text=TEXT)


def confirm(adapter, proposal, interaction="local-1", source=LOCAL):
    return adapter.approve_and_persist(
        interaction_id=interaction, source=source,
        command=f"approve memory {proposal.proposal_id}",
    )


def test_only_live_approval_writes_exact_text_and_fixed_metadata(setup):
    engine, adapter, storage, _ = setup
    pending = propose(engine)
    assert storage.mock_calls == []
    result = confirm(adapter, pending)
    assert result.status == "persisted"
    assert result.commit_uncertain is False
    storage.search.assert_called_once_with(TEXT, limit=3)
    storage.write.assert_called_once_with(
        content=TEXT, source_type="project_note", preserve_whitespace=True,
        metadata={"category": "project", "source": "brain_v2",
                  "capture_method": "approved_project_note"},
    )
    assert [entry[0] for entry in storage.mock_calls] == ["search", "write"]


def test_forged_approved_object_and_id_cannot_authorize_storage(setup):
    engine, adapter, storage, _ = setup
    pending = propose(engine)
    forged = replace(pending, status=ProposalStatus.APPROVED, text="forged candidate")
    result = adapter.approve_and_persist(
        interaction_id="local-1", source=LOCAL, command=forged,
    )
    assert result.status == "unauthorized"
    assert confirm(adapter, replace(forged, proposal_id="0" * 32)).status == "unauthorized"
    assert storage.mock_calls == []
    assert confirm(adapter, pending).status == "persisted"
    assert storage.write.call_args.kwargs["content"] == TEXT


def test_adapter_requires_a_real_engine(setup):
    engine, _, _, _ = setup
    forged = replace(propose(engine), status=ProposalStatus.APPROVED)
    impostor = Mock(spec=MemoryApprovalEngine)
    impostor.approve.return_value = forged
    with pytest.raises(TypeError, match="MemoryApprovalEngine"):
        persistence.ApprovedMemoryPersistence(impostor)


@pytest.mark.parametrize("state", ["cancelled", "expired", "already_approved"])
def test_unavailable_proposal_cannot_write(setup, state):
    engine, adapter, storage, now = setup
    pending = propose(engine)
    if state == "cancelled":
        engine.cancel(interaction_id="local-1", source=LOCAL,
                      command=f"cancel memory {pending.proposal_id}")
    elif state == "expired":
        now[0] = pending.expires_at
    else:
        engine.approve(interaction_id="local-1", source=LOCAL,
                       command=f"approve memory {pending.proposal_id}")
    assert confirm(adapter, pending).status == "unauthorized"
    assert storage.mock_calls == []


def test_wrong_interaction_and_model_turn_cannot_consume(setup):
    engine, adapter, storage, _ = setup
    pending = propose(engine)
    assert confirm(adapter, pending, "local-2").status == "unauthorized"
    assert confirm(adapter, pending, source=InteractionSource.MODEL).status == "unauthorized"
    assert storage.mock_calls == []
    assert confirm(adapter, pending).status == "persisted"


def test_replay_cannot_insert_twice(setup):
    engine, adapter, storage, _ = setup
    pending = propose(engine)
    assert confirm(adapter, pending).status == "persisted"
    assert confirm(adapter, pending).status == "unauthorized"
    storage.write.assert_called_once()


def test_concurrent_confirmation_can_insert_only_once(setup):
    engine, adapter, storage, _ = setup
    pending = propose(engine)
    barrier = Barrier(2)

    def run():
        barrier.wait(timeout=5)
        return confirm(adapter, pending).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(run) for _ in range(2)]
    assert sorted(call.result() for call in calls) == ["persisted", "unauthorized"]
    storage.search.assert_called_once()
    storage.write.assert_called_once()


@pytest.mark.parametrize("row", [
    {"content": "plan a new fixture", "similarity": 0.1},
    {"content": "another fixture", "similarity": 0.96},
])
def test_duplicate_is_skipped(setup, row):
    engine, adapter, storage, _ = setup
    storage.search.return_value = [row]
    assert confirm(adapter, propose(engine)).status == "duplicate"
    storage.write.assert_not_called()


def test_unrelated_match_below_duplicate_threshold_does_not_block_approved_write(setup):
    engine, adapter, storage, _ = setup
    storage.search.return_value = [{"content": "another fixture", "similarity": 0.959}]
    assert confirm(adapter, propose(engine)).status == "persisted"
    storage.write.assert_called_once()


def test_lookup_failure_closes_authorization_without_insertion(setup, caplog):
    engine, adapter, storage, _ = setup
    storage.search.side_effect = RuntimeError(TEXT)
    pending = propose(engine)
    outcome = confirm(adapter, pending)
    assert outcome.status == "lookup_failed"
    assert outcome.commit_uncertain is False
    assert confirm(adapter, pending).status == "unauthorized"
    storage.search.assert_called_once()
    storage.write.assert_not_called()
    assert TEXT.strip() not in repr(outcome) + caplog.text


def test_invalid_lookup_result_cannot_bypass_duplicate_check(setup):
    engine, adapter, storage, _ = setup
    storage.search.return_value = {}
    assert confirm(adapter, propose(engine)).status == "lookup_failed"
    storage.write.assert_not_called()


def test_writer_exception_reports_uncertain_outcome_and_cannot_retry(setup, caplog):
    engine, adapter, storage, _ = setup
    storage.write.side_effect = RuntimeError(f"private write payload: {TEXT}")
    pending = propose(engine)
    outcome = confirm(adapter, pending)
    assert outcome.status == "persistence_failed"
    assert outcome.commit_uncertain is True
    assert confirm(adapter, pending).status == "unauthorized"
    storage.write.assert_called_once()
    assert TEXT.strip() not in repr(outcome) + repr(pending) + caplog.text


@pytest.mark.parametrize("writer_result", [None, True, 0, -1, "17"])
def test_unconfirmed_writer_result_cannot_claim_success(setup, writer_result):
    engine, adapter, storage, _ = setup
    storage.write.return_value = writer_result
    outcome = confirm(adapter, propose(engine))
    assert outcome.status == "persistence_failed"
    assert outcome.commit_uncertain is True
    storage.write.assert_called_once()


def test_developer_confirmation_never_authorizes_or_changes_developer_state(setup, monkeypatch):
    from core import developer_bridge

    engine, adapter, storage, _ = setup
    sentinel = object()
    monkeypatch.setattr(developer_bridge, "_pending_action", sentinel)
    pending = propose(engine)
    outcome = adapter.approve_and_persist(
        interaction_id="local-1", source=LOCAL, command="approve",
    )
    assert outcome.status == "unauthorized"
    assert storage.mock_calls == []
    assert confirm(adapter, pending).status == "persisted"
    assert developer_bridge._pending_action is sentinel


@pytest.mark.parametrize("options,expected", [
    ({}, TEXT.strip()),
    ({"preserve_whitespace": True}, TEXT),
])
def test_semantic_writer_binds_expected_text_to_existing_insert(monkeypatch, options, expected):
    from unittest.mock import MagicMock

    conn, cursor = MagicMock(), MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = (17,)
    monkeypatch.setattr(semantic_memory, "ensure_semantic_memory_schema", Mock())
    monkeypatch.setattr(semantic_memory, "get_embedding", Mock(return_value=[0.1]))
    monkeypatch.setattr(semantic_memory, "get_connection", Mock(return_value=conn))

    assert semantic_memory.add_semantic_memory(TEXT, **options) == 17
    assert cursor.execute.call_args.args[1][2] == expected
    conn.commit.assert_called_once()
