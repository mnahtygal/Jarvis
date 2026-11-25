from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Barrier

import pytest

from core.memory_approval import (
    InteractionSource,
    MemoryApprovalEngine,
    MemoryApprovalError,
    ProposalStatus,
)


LOCAL = InteractionSource.TRUSTED_LOCAL_USER


@pytest.fixture
def engine():
    return MemoryApprovalEngine(clock=lambda: 100.0)


def propose(engine, text="Build a calibration fixture.", interaction="local-1"):
    return engine.propose(interaction_id=interaction, source=LOCAL, text=text)


def approve(engine, proposal_id, interaction="local-1", source=LOCAL):
    return engine.approve(
        interaction_id=interaction, source=source,
        command=f"approve memory {proposal_id}",
    )


def assert_rejected(code, action, *args, **kwargs):
    with pytest.raises(MemoryApprovalError) as exc:
        action(*args, **kwargs)
    assert exc.value.code == code


def test_valid_proposal_is_immutable_and_preserves_exact_text(engine):
    text = "  Build a calibration fixture.\n"
    proposal = propose(engine, text)
    other = propose(engine, interaction="local-2")
    assert proposal.proposal_id != other.proposal_id
    assert proposal.interaction_id == "local-1"
    assert proposal.text == text
    assert proposal.memory_type == "project_note"
    assert proposal.category == "project"
    assert proposal.created_at == 100.0
    assert proposal.expires_at == 220.0
    assert proposal.status is ProposalStatus.PENDING
    with pytest.raises(FrozenInstanceError):
        proposal.text = "changed"


@pytest.mark.parametrize(("text", "code"), [
    ("", "empty_candidate"),
    (" \n ", "empty_candidate"),
    ("a" * 1001, "oversized_candidate"),
    ("Password: example-value", "credential_pattern"),
    ("The API key is example-value", "credential_pattern"),
    ("Authorization: Bearer example-token", "credential_pattern"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----", "credential_pattern"),
    ("Don't remember this detail.", "retention_opt_out"),
    ("Please do not store this.", "retention_opt_out"),
    ("Keep this off the record.", "retention_opt_out"),
])
def test_candidate_validation(engine, text, code):
    assert_rejected(code, propose, engine, text)


def test_exact_size_limit_is_accepted(engine):
    assert len(propose(engine, "a" * 1000).text) == 1000


@pytest.mark.parametrize("source", [InteractionSource.REMOTE_USER, InteractionSource.MODEL])
def test_untrusted_sources_cannot_propose_or_consume(engine, source):
    assert_rejected("untrusted_source", engine.propose,
                    interaction_id="local-1", source=source, text="A project note")
    pending = propose(engine)
    assert_rejected("untrusted_source", approve, engine, pending.proposal_id, source=source)
    assert_rejected("untrusted_source", engine.cancel,
                    interaction_id="local-1", source=source,
                    command=f"cancel memory {pending.proposal_id}")
    assert approve(engine, pending.proposal_id).status is ProposalStatus.APPROVED


def test_approval_consumes_exact_proposal_once(engine):
    pending = propose(engine)
    approved = approve(engine, pending.proposal_id)
    assert approved.status is ProposalStatus.APPROVED
    assert approved.proposal_id == pending.proposal_id
    assert approved.text == pending.text
    assert pending.status is ProposalStatus.PENDING
    assert_rejected("no_matching_proposal", approve, engine, pending.proposal_id)


def test_wrong_proposal_and_interaction_cannot_consume(engine):
    pending = propose(engine)
    other = propose(engine, interaction="local-2")
    assert_rejected("no_matching_proposal", approve, engine, other.proposal_id)
    assert_rejected("no_matching_proposal", approve, engine, pending.proposal_id, "local-2")
    assert approve(engine, pending.proposal_id).status is ProposalStatus.APPROVED
    assert approve(engine, other.proposal_id, "local-2").status is ProposalStatus.APPROVED


def test_cancellation_consumes_only_its_target(engine):
    pending = propose(engine)
    command = f"cancel memory {pending.proposal_id}"
    assert_rejected("no_matching_proposal", engine.cancel,
                    interaction_id="local-2", source=LOCAL, command=command)
    assert engine.cancel(
        interaction_id="local-1", source=LOCAL, command=command,
    ).status is ProposalStatus.CANCELLED
    assert_rejected("no_matching_proposal", approve, engine, pending.proposal_id)


def test_expiration_at_deadline():
    now = 10.0
    engine = MemoryApprovalEngine(clock=lambda: now)
    pending = propose(engine)
    now = pending.expires_at
    assert_rejected("expired", approve, engine, pending.proposal_id)
    assert_rejected("no_matching_proposal", approve, engine, pending.proposal_id)


def test_concurrent_approval_consumes_once(engine):
    pending = propose(engine)
    barrier = Barrier(2)

    def confirm():
        barrier.wait(timeout=5)
        try:
            return approve(engine, pending.proposal_id).status.value
        except MemoryApprovalError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = [workers.submit(confirm) for _ in range(2)]
        assert sorted(result.result() for result in results) == [
            "approved", "no_matching_proposal",
        ]


def test_active_pending_proposal_is_preserved_until_consumed(engine):
    pending = propose(engine, "First candidate")
    assert_rejected("already_pending", propose, engine, "Replacement candidate")
    assert approve(engine, pending.proposal_id).text == "First candidate"
    assert propose(engine, "Replacement candidate").proposal_id != pending.proposal_id


def test_bounded_capacity_and_lazy_cleanup():
    now = 0.0
    engine = MemoryApprovalEngine(clock=lambda: now, max_pending=1)
    pending = propose(engine)
    assert_rejected("capacity_reached", propose, engine, interaction="local-2")
    now = pending.expires_at
    assert propose(engine, interaction="local-2").status is ProposalStatus.PENDING
    assert_rejected("no_matching_proposal", approve, engine, pending.proposal_id)


def test_explicit_cleanup_only_removes_expired_proposals():
    now = 0.0
    engine = MemoryApprovalEngine(clock=lambda: now)
    first = propose(engine)
    now = 60.0
    second = propose(engine, interaction="local-2")
    now = first.expires_at
    assert engine.cleanup_expired() == 1
    assert engine.cleanup_expired() == 0
    assert approve(engine, second.proposal_id, "local-2").status is ProposalStatus.APPROVED


def test_proposal_text_stays_out_of_repr_and_logs(engine, caplog):
    caplog.set_level("DEBUG")
    secret = "Confidential fixture detail"
    pending = propose(engine, secret)
    approved = approve(engine, pending.proposal_id)
    assert all(secret not in repr(obj) for obj in (engine, pending, approved))
    assert secret not in caplog.text


def test_developer_approval_is_separate(engine, monkeypatch):
    from core import developer_bridge

    sentinel = object()
    monkeypatch.setattr(developer_bridge, "_pending_action", sentinel)
    pending = propose(engine)
    for command in ("approve", "yes, approve", "proceed", "execute it", "run it",
                    f"approve memory {pending.proposal_id} please"):
        assert_rejected("invalid_confirmation", engine.approve,
                        interaction_id="local-1", source=LOCAL, command=command)
    approve(engine, pending.proposal_id)
    assert developer_bridge._pending_action is sentinel


def test_proposal_lifecycle_makes_no_database_calls(engine, monkeypatch):
    from unittest.mock import Mock

    from core import db

    connect = Mock(side_effect=AssertionError("database access is prohibited"))
    monkeypatch.setattr(db.psycopg2, "connect", connect)
    pending = propose(engine)
    approve(engine, pending.proposal_id)
    another = propose(engine)
    engine.cancel(interaction_id="local-1", source=LOCAL,
                  command=f"cancel memory {another.proposal_id}")
    engine.cleanup_expired()
    connect.assert_not_called()
