import re
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone, tzinfo
from enum import Enum
from threading import Barrier, Event
from unittest.mock import Mock
from uuid import UUID

import pytest

from core.exact_memory_approval import (
    ExactMemoryApprovalEngine,
    ExactMemoryOperation,
    ExactMemoryRecordSnapshot,
)
from core.memory_approval import InteractionSource, MemoryApprovalEngine, MemoryApprovalError, ProposalStatus


LOCAL = InteractionSource.TRUSTED_LOCAL_USER
CREATE, UPDATE, DELETE = ExactMemoryOperation
KEY = "my preferred language"
EXISTING = ExactMemoryRecordSnapshot(17, KEY, "  C++  ", None, datetime(2026, 11, 28))
NEW_VALUE = "  Python, 3.x!  "
TIMEOUT = 5


def propose(engine, *, interaction="local-1", source=LOCAL, operation=CREATE,
            key=KEY, value=NEW_VALUE):
    return engine.propose(
        interaction_id=interaction, source=source, operation=operation,
        memory_key=key, proposed_value=value,
    )


def confirm(engine, pending, *, verb="approve", interaction="local-1", source=LOCAL):
    return getattr(engine, verb)(
        interaction_id=interaction, source=source,
        command=f"{verb} exact memory {pending.proposal_id}",
    )


def rejected(code, call, *args, **kwargs):
    with pytest.raises(MemoryApprovalError) as exc:
        call(*args, **kwargs)
    assert exc.value.code == code
    assert exc.value.args == (code,)
    return exc.value


@pytest.fixture
def empty_engine():
    lookup = Mock(return_value=None)
    return ExactMemoryApprovalEngine(lookup, clock=lambda: 100), lookup


@pytest.mark.parametrize(("operation", "existing", "value"), [
    (CREATE, None, NEW_VALUE),
    (UPDATE, EXISTING, NEW_VALUE),
    (DELETE, EXISTING, None),
])
def test_operations_preserve_reviewed_data(operation, existing, value):
    lookup = Mock(return_value=existing)
    engine = ExactMemoryApprovalEngine(lookup, clock=lambda: 100)
    pending = propose(engine, operation=operation, key="  My Preferred Language  ", value=value)
    lookup.assert_called_once_with(KEY)
    assert pending.memory_key == KEY
    assert pending.operation is operation
    assert pending.existing_record is existing
    assert pending.proposed_value == value
    assert pending.interaction_id == "local-1"
    assert pending.created_at == 100
    assert pending.expires_at == 220
    approved = confirm(engine, pending)
    assert approved == replace(pending, status=ProposalStatus.APPROVED)
    assert pending.status is ProposalStatus.PENDING
    lookup.assert_called_once()


@pytest.mark.parametrize(("operation", "existing", "value", "error"), [
    (CREATE, EXISTING, NEW_VALUE, "record_exists"),
    (CREATE, replace(EXISTING, memory_value=""), NEW_VALUE, "record_exists"),
    (UPDATE, None, NEW_VALUE, "record_missing"),
    (DELETE, None, None, "record_missing"),
    (UPDATE, EXISTING, EXISTING.memory_value, "no_change"),
])
def test_operation_preconditions(operation, existing, value, error):
    lookup = Mock(return_value=existing)
    engine = ExactMemoryApprovalEngine(lookup, max_pending=1)
    rejected(error, propose, engine, operation=operation, value=value)
    lookup.assert_called_once_with(KEY)
    lookup.return_value = None
    assert propose(engine).status is ProposalStatus.PENDING


@pytest.mark.parametrize(("operation", "value"), [(UPDATE, NEW_VALUE), (DELETE, None)])
def test_empty_value_is_a_present_record(operation, value):
    row = replace(EXISTING, memory_value="", updated_at=None)
    engine = ExactMemoryApprovalEngine(lambda _: row)
    assert propose(engine, operation=operation, value=value).existing_record is row


def test_update_compares_values_exactly():
    engine = ExactMemoryApprovalEngine(lambda _: EXISTING)
    pending = propose(engine, operation=UPDATE, value=EXISTING.memory_value.strip())
    assert pending.existing_record.memory_value == "  C++  "
    assert pending.proposed_value == "C++"


@pytest.mark.parametrize(("key", "expected"), [
    ("My Preferred Database", "my preferred database"),
    ("My Preferred Language", "my preferred language"),
    (" My Wife's Name ", "my wife's name"),
    ("My Workshop Camera", "my workshop camera"),
    ("My Wife's  CAMERA: Mk. II!", "my wife's  camera: mk. ii!"),
    ("My Job  Title", "my job  title"),
    ("My Preferred  Café", "my preferred  café"),
])
def test_key_normalization_is_exact(empty_engine, key, expected):
    engine, lookup = empty_engine
    assert propose(engine, key=key).memory_key == expected
    lookup.assert_called_once_with(expected)


class OtherOperation(Enum):
    CREATE = "create"


class StringSubclass(str):
    pass


@pytest.mark.parametrize(("overrides", "error"), [
    ({"operation": "create"}, "invalid_operation"),
    ({"operation": False}, "invalid_operation"),
    ({"operation": OtherOperation.CREATE}, "invalid_operation"),
    ({"operation": None}, "invalid_operation"),
    ({"key": None}, "invalid_key"),
    ({"key": 17}, "invalid_key"),
    ({"key": StringSubclass(KEY)}, "invalid_key"),
    ({"key": ""}, "invalid_key"),
    ({"key": "   "}, "invalid_key"),
    ({"key": " " + "k" * 256}, "oversized_key"),
    ({"key": "\u0130" * 129}, "oversized_key"),  # lowercase expands to 258 code points
    ({"value": None}, "invalid_value"),
    ({"value": False}, "invalid_value"),
    ({"value": StringSubclass(NEW_VALUE)}, "invalid_value"),
    ({"value": ""}, "invalid_value"),
    ({"value": "  \u00a0 "}, "invalid_value"),
    ({"value": "v" * 1001}, "oversized_value"),
    ({"operation": UPDATE, "value": None}, "invalid_value"),
    ({"operation": DELETE, "value": ""}, "unexpected_value"),
    ({"operation": DELETE, "value": "replacement"}, "unexpected_value"),
])
def test_invalid_proposal_input_never_reaches_lookup(empty_engine, overrides, error):
    engine, lookup = empty_engine
    rejected(error, propose, engine, **overrides)
    lookup.assert_not_called()


def test_exact_length_limits_include_normalized_expansion(empty_engine):
    engine, lookup = empty_engine
    key = "\u0130" * 128
    value = " " + "V" * 998 + " "
    pending = propose(engine, key=key, value=value, interaction="i" * 128)
    assert len(pending.memory_key) == 256
    assert pending.proposed_value == value
    lookup.assert_called_once_with(key.lower())
    assert len(propose(engine, key="K" * 256, interaction="other").memory_key) == 256


@pytest.mark.parametrize("char", ["\n", "\x1b", "\u202e", "\ud800", "\u2028", "\u2029"])
def test_unsafe_unicode_rejected_before_stripping_or_lookup(empty_engine, char):
    engine, lookup = empty_engine
    rejected("unsafe_key", propose, engine, key=f"{char}{KEY}")
    rejected("unsafe_value", propose, engine, value=f"new{char}value")
    lookup.assert_not_called()


@pytest.mark.parametrize(("key", "value", "code"), [
    ("Password: confidential", "new", "credential_pattern"),
    ("MY API KEY", "example-secret", "credential_pattern"),
    ("Access token is", "example-secret", "credential_pattern"),
    ("Other", "https://user:secret@example.invalid", "credential_pattern"),
    ("Other", "-----BEGIN OPENSSH PRIVATE KEY-----", "credential_pattern"),
    ("Other", "Authorization: Bearer example-token", "credential_pattern"),
    ("Keep this off the record", "example", "retention_opt_out"),
    ("Other", "Don't remember this detail", "retention_opt_out"),
    ("Please do not", "store this", "retention_opt_out"),
])
def test_screening_rejects_both_fields_and_split_payloads(empty_engine, key, value, code):
    engine, lookup = empty_engine
    rejected(code, propose, engine, key=key, value=value)
    lookup.assert_not_called()


class CustomTimezone(tzinfo):
    pass


@pytest.mark.parametrize("record", [
    {}, True, [], (17, KEY, "old", None, None),
    object.__new__(ExactMemoryRecordSnapshot),
    replace(EXISTING, record_id=True),
    replace(EXISTING, record_id=0),
    replace(EXISTING, record_id=-1),
    replace(EXISTING, record_id="17"),
    replace(EXISTING, memory_key=KEY.upper()),
    replace(EXISTING, memory_key=KEY + " "),
    replace(EXISTING, memory_key=None),
    replace(EXISTING, memory_value=None),
    replace(EXISTING, memory_value="v" * 1001),
    replace(EXISTING, created_at=date(2026, 11, 28)),
    replace(EXISTING, updated_at="2026-11-28"),
    replace(EXISTING, updated_at=datetime(2026, 11, 28, tzinfo=CustomTimezone())),
], ids=[
    "dict", "bool", "list", "tuple", "missing-fields", "bool-id", "zero-id",
    "negative-id", "str-id", "uppercase-key", "space-key", "null-key",
    "null-value", "oversized-value", "date", "text-timestamp", "custom-timezone",
])
def test_malformed_snapshot_fails_closed(record):
    engine = ExactMemoryApprovalEngine(lambda _: record)
    rejected("invalid_snapshot", propose, engine, operation=UPDATE)


@pytest.mark.parametrize(("key", "value"), [
    (KEY, "before\u2028after"),
    (KEY, "Password: private-old-value"),
    ("my api key", "private-old-value"),
    (KEY, "Don't remember this private-old-value"),
])
def test_unsafe_snapshot_cannot_be_reviewed_even_for_deletion(key, value):
    row = replace(EXISTING, memory_key=key, memory_value=value)
    engine = ExactMemoryApprovalEngine(lambda _: row)
    rejected("unsafe_snapshot", propose, engine, key=key, operation=DELETE, value=None)


def test_snapshot_accepts_aware_timestamps_and_boundary_values():
    timestamp = datetime(2026, 11, 28, tzinfo=timezone.utc)
    row = replace(EXISTING, memory_value="v" * 1000, updated_at=timestamp)
    engine = ExactMemoryApprovalEngine(lambda _: row)
    review = propose(engine, operation=UPDATE)
    assert review.existing_record is row
    assert review.existing_record.updated_at is timestamp


def test_lookup_exception_is_sanitized_and_releases_capacity(caplog):
    secret = "private-lookup-failure-content"
    lookup = Mock(side_effect=[RuntimeError(secret), None])
    engine = ExactMemoryApprovalEngine(lookup, max_pending=1)
    error = rejected("lookup_failed", propose, engine)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert secret not in "".join(traceback.format_exception(error)) + caplog.text
    assert propose(engine, interaction="next").status is ProposalStatus.PENDING


@pytest.mark.parametrize("capacity", [True, 0, -1, "64", 1.25, None])
def test_invalid_capacity_is_rejected(capacity):
    with pytest.raises(ValueError, match="max_pending"):
        ExactMemoryApprovalEngine(lambda _: None, max_pending=capacity)


@pytest.mark.parametrize("arguments", [{"lookup": None}, {"clock": 1}])
def test_lookup_and_clock_must_be_callable(arguments):
    with pytest.raises(TypeError, match="must be callable"):
        ExactMemoryApprovalEngine(**({"lookup": lambda _: None} | arguments))


@pytest.mark.parametrize("invalid_time", [float("nan"), float("inf"), "100", True, 1e100])
def test_invalid_clock_cannot_publish_or_consume(invalid_time):
    lookup = Mock(return_value=None)
    clock = Mock(side_effect=[0, invalid_time, 1, 1, invalid_time, 2])
    engine = ExactMemoryApprovalEngine(lookup, clock=clock, max_pending=1)
    rejected("invalid_clock", propose, engine)
    pending = propose(engine)
    rejected("invalid_clock", confirm, engine, pending)
    assert confirm(engine, pending).status is ProposalStatus.APPROVED


@pytest.mark.parametrize("source", [
    InteractionSource.REMOTE_USER, InteractionSource.MODEL, "trusted_local_user", None,
])
def test_untrusted_source_cannot_propose_or_consume(empty_engine, source):
    engine, lookup = empty_engine
    rejected("untrusted_source", propose, engine, source=source)
    lookup.assert_not_called()
    pending = propose(engine)
    rejected("untrusted_source", confirm, engine, pending, source=source)
    rejected("untrusted_source", confirm, engine, pending, verb="cancel", source=source)
    assert confirm(engine, pending).status is ProposalStatus.APPROVED


@pytest.mark.parametrize("interaction", ["", " ", "i" * 129, None, 17, "local\n"])
def test_invalid_interaction_is_rejected_before_lookup(empty_engine, interaction):
    engine, lookup = empty_engine
    rejected("invalid_interaction", propose, engine, interaction=interaction)
    lookup.assert_not_called()


def test_proposals_and_snapshots_are_immutable_and_safe_to_log(caplog):
    key, interaction, old, new = "private-key-field", "private-interaction", "private-old", "private-new"
    row = replace(EXISTING, memory_key=key, memory_value=old)
    engine = ExactMemoryApprovalEngine(lambda _: row)
    caplog.set_level("DEBUG")
    pending = propose(engine, interaction=interaction, key=key, operation=UPDATE, value=new)
    approved = confirm(engine, pending, interaction=interaction)
    for field in (key, interaction, old, new):
        assert all(field not in repr(obj) for obj in (engine, row, pending, approved))
        assert field not in caplog.text
    assert "existing_record" not in repr(pending)
    assert not hasattr(pending, "__dict__") and not hasattr(row, "__dict__")
    with pytest.raises(FrozenInstanceError):
        approved.proposed_value = "replacement"
    with pytest.raises(FrozenInstanceError):
        row.memory_value = "replacement"


def test_uuid_ids_and_one_pending_per_interaction(empty_engine):
    engine, lookup = empty_engine
    first = propose(engine)
    second = propose(engine, interaction="local-2")
    rejected("already_pending", propose, engine)
    lookup.assert_called()
    assert lookup.call_count == 2
    for proposal in (first, second):
        assert re.fullmatch(r"[0-9a-f]{32}", proposal.proposal_id)
        assert UUID(hex=proposal.proposal_id).version == 4
    assert first.proposal_id != second.proposal_id
    rejected("no_matching_proposal", confirm, engine, second)
    rejected("no_matching_proposal", confirm, engine, first, interaction="local-2")
    assert confirm(engine, first).status is ProposalStatus.APPROVED
    rejected("no_matching_proposal", confirm, engine, first)
    assert confirm(engine, second, verb="cancel", interaction="local-2").status is ProposalStatus.CANCELLED
    rejected("no_matching_proposal", confirm, engine, second, verb="cancel", interaction="local-2")


@pytest.mark.parametrize("command", [
    None, "approve", "yes, approve", "approve memory {id}", "approve exact memory ABCD",
    "approve exact memory " + "A" * 32, "approve exact memory {id}\n",
    " approve exact memory {id}", "approve  exact memory {id}",
    "approve exact memory {id} please", "cancel exact memory {id}",
    "approve exact memory {id}\ncancel exact memory {id}",
])
def test_confirmation_grammar_is_exact_without_consuming_proposal(empty_engine, command):
    engine, _ = empty_engine
    pending = propose(engine)
    rejected(
        "invalid_confirmation", engine.approve, interaction_id="local-1", source=LOCAL,
        command=command.format(id=pending.proposal_id) if command is not None else None,
    )
    assert confirm(engine, pending).status is ProposalStatus.APPROVED


def test_expiration_at_exact_deadline_and_no_terminal_history():
    now = [100]
    engine = ExactMemoryApprovalEngine(lambda _: None, clock=lambda: now[0])
    first = propose(engine)
    second = propose(engine, interaction="local-2")
    now[0] = first.expires_at - 0.01
    assert confirm(engine, first).status is ProposalStatus.APPROVED
    now[0] = second.expires_at
    rejected("expired", confirm, engine, second, verb="cancel", interaction="local-2")
    rejected("no_matching_proposal", confirm, engine, second, interaction="local-2")
    assert engine.cleanup_expired() == 0


def test_default_capacity_is_per_engine_and_cleanup_is_lazy():
    clock = [0.0]
    lookup = Mock(return_value=None)
    engine = ExactMemoryApprovalEngine(lookup, clock=lambda: clock[0])
    for index in range(64):
        propose(engine, interaction=f"local-{index}")
    rejected("capacity_reached", propose, engine, interaction="overflow")
    assert lookup.call_count == 64
    assert propose(ExactMemoryApprovalEngine(lambda _: None), interaction="overflow")
    clock[0] = 120.0
    pending = propose(engine, interaction="overflow")
    assert pending.created_at == 120
    assert engine.cleanup_expired() == 0


@pytest.mark.parametrize("second_verb", ["approve", "cancel"])
def test_concurrent_confirmation_has_exactly_one_winner(empty_engine, second_verb):
    engine, lookup = empty_engine
    pending = propose(engine)
    barrier = Barrier(2)

    def consume(verb):
        barrier.wait(timeout=TIMEOUT)
        try:
            return confirm(engine, pending, verb=verb).status.value
        except MemoryApprovalError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(consume, verb) for verb in ("approve", second_verb)]
        results = [future.result(timeout=TIMEOUT) for future in futures]
    assert results.count("no_matching_proposal") == 1
    winner = next(result for result in results if result != "no_matching_proposal")
    assert winner in ({"approved"} if second_verb == "approve" else {"approved", "cancelled"})
    lookup.assert_called_once()


def test_in_flight_lookup_reserves_interaction_and_capacity():
    started, finish = Event(), Event()

    def lookup(_):
        started.set()
        assert finish.wait(timeout=TIMEOUT)

    read = Mock(side_effect=lookup)
    engine = ExactMemoryApprovalEngine(read, max_pending=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(propose, engine)
        try:
            assert started.wait(timeout=TIMEOUT)
            same = pool.submit(rejected, "already_pending", propose, engine)
            same.result(timeout=TIMEOUT)
            other = pool.submit(rejected, "capacity_reached", propose, engine, interaction="local-2")
            other.result(timeout=TIMEOUT)
        finally:
            finish.set()
        assert pending.result(timeout=TIMEOUT).status is ProposalStatus.PENDING
    read.assert_called_once()


def test_slow_lookup_does_not_block_cleanup_or_start_ttl_early():
    now = [0.0]
    started, finish = Event(), Event()

    def lookup(key):
        if key == "slow":
            started.set()
            assert finish.wait(timeout=TIMEOUT)

    engine = ExactMemoryApprovalEngine(lookup, clock=lambda: now[0], max_pending=2)
    expired = propose(engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(propose, engine, interaction="slow-session", key="slow")
        try:
            assert started.wait(timeout=TIMEOUT)
            now[0] = expired.expires_at + 60
            assert pool.submit(engine.cleanup_expired).result(timeout=TIMEOUT) == 1
            fresh = pool.submit(propose, engine).result(timeout=TIMEOUT)
            assert confirm(engine, fresh).status is ProposalStatus.APPROVED
        finally:
            finish.set()
        pending = slow.result(timeout=TIMEOUT)
    assert pending.created_at == 180
    assert pending.expires_at == 300
    assert confirm(engine, pending, interaction="slow-session").status is ProposalStatus.APPROVED


def test_interrupted_lookup_releases_reservation():
    lookup = Mock(side_effect=[KeyboardInterrupt, None])
    engine = ExactMemoryApprovalEngine(lookup, max_pending=1)
    with pytest.raises(KeyboardInterrupt):
        propose(engine)
    assert propose(engine).status is ProposalStatus.PENDING


def test_cross_engine_ids_are_rejected_and_project_adapter_is_unchanged(monkeypatch, empty_engine):
    from core import approved_memory_persistence

    engine, _ = empty_engine
    pending = propose(engine)
    other = ExactMemoryApprovalEngine(lambda _: None)
    other_pending = propose(other)
    project = MemoryApprovalEngine()
    project_pending = project.propose(interaction_id="local-1", source=LOCAL, text="Build a jig.")
    with pytest.raises(TypeError, match="MemoryApprovalEngine"):
        approved_memory_persistence.ApprovedMemoryPersistence(engine)
    adapter = approved_memory_persistence.ApprovedMemoryPersistence(project)
    write = Mock(return_value=17)
    monkeypatch.setattr(approved_memory_persistence, "add_semantic_memory", write)
    monkeypatch.setattr(approved_memory_persistence, "search_semantic_memories", Mock(return_value=[]))
    for proposal in (pending, project_pending):
        rejected("no_matching_proposal", confirm, other, proposal)
    rejected("no_matching_proposal", confirm, engine, project_pending)
    assert adapter.approve_and_persist(
        interaction_id="local-1", source=LOCAL, command=f"approve memory {pending.proposal_id}",
    ).status == "unauthorized"
    write.assert_not_called()
    assert adapter.approve_and_persist(
        interaction_id="local-1", source=LOCAL, command=f"approve memory {project_pending.proposal_id}",
    ).status == "persisted"
    write.assert_called_once()
    assert confirm(engine, pending).status is ProposalStatus.APPROVED
    assert confirm(other, other_pending).status is ProposalStatus.APPROVED


def test_engine_lifecycle_requires_only_the_injected_lookup(monkeypatch):
    from core import db, memory, semantic_memory, session
    from skills import llm_skill

    forbidden = Mock(side_effect=AssertionError("unexpected external call"))
    for module, names in (
        (db, ["get_connection"]),
        (memory, ["remember", "update_memory", "forget", "get_connection"]),
        (semantic_memory, ["add_semantic_memory", "get_embedding", "get_connection"]),
        (session, ["remember_user_message", "remember_assistant_message", "get_connection"]),
        (llm_skill, ["ask_local_llm"]),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    now = [100]
    read = Mock(return_value=EXISTING)
    engine = ExactMemoryApprovalEngine(read, clock=lambda: now[0])
    pending = propose(engine, operation=UPDATE)
    assert confirm(engine, pending).status is ProposalStatus.APPROVED
    pending = propose(engine, operation=DELETE, value=None)
    assert confirm(engine, pending, verb="cancel").status is ProposalStatus.CANCELLED
    pending = propose(engine, operation=UPDATE)
    now[0] = pending.expires_at
    assert engine.cleanup_expired() == 1
    assert read.call_count == 3
    forbidden.assert_not_called()


def test_chat_and_voice_cannot_consume_a_live_exact_proposal(monkeypatch, empty_engine):
    import api
    from core import brain
    from skills import llm_skill

    engine, lookup = empty_engine
    pending = propose(engine)
    command = f"approve exact memory {pending.proposal_id}"
    monkeypatch.setattr(api, "listen_command", lambda: command)
    monkeypatch.setattr(brain, "set_last_topic", Mock())
    monkeypatch.setattr(brain, "remember_user_message", Mock())
    monkeypatch.setattr(brain, "remember_assistant_message", Mock())
    monkeypatch.setattr(llm_skill, "ask_local_llm", lambda _: "Approval accepted.")
    metadata = {"approved": True, "interaction_id": pending.interaction_id,
                "source": LOCAL.value, "use_voice": False}
    with api.app.test_client() as client:
        for path in ("/text", "/ask"):
            response = client.post(path, json={**metadata, "command": command},
                                   headers={"X-Memory-Approved": "true"})
            assert response.status_code == 200
    lookup.assert_called_once()
    assert confirm(engine, pending).status is ProposalStatus.APPROVED
