import json
from pathlib import Path

from core.developer_agent import RepairProposalRequest, Workspace, propose_repair
from core.developer_agent.developer_session import (
    MAX_SESSION_PROPOSAL_REQUESTS,
    MAX_SESSION_REPAIRS,
    MAX_SESSION_VERIFICATION_RUNS,
)
from core.developer_agent.repair_proposal import (
    MAX_CANDIDATE_FILES,
    MAX_FILE_EXCERPT_BYTES,
    MAX_MODEL_CALLS,
    MAX_PROPOSAL_TEXT_BYTES,
    MIN_REPAIR_PROPOSAL_CONFIDENCE,
)


SOURCE = """def classify(records):
    remaining = len(records)
    if remaining >= 2:
        remaining -= 2
    if remaining >= 3:
        return "bulk"
    return "standard"
"""

TEST_SOURCE = """from processor import classify


def test_three_records_use_bulk_path():
    assert classify([1, 2, 3]) == "bulk"
"""


class _Capture:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response


def _untrusted_data(prompt: str) -> dict[str, object]:
    start_marker = "<UNTRUSTED_REPAIR_DATA>\n"
    end_marker = "\n</UNTRUSTED_REPAIR_DATA>"
    start = prompt.index(start_marker) + len(start_marker)
    end = prompt.index(end_marker, start)
    return json.loads(prompt[start:end])


def _no_fix() -> str:
    return json.dumps({
        "proposal_type": "no_fix",
        "confidence": 0.2,
        "reason": "The supplied evidence is insufficient",
    })


def test_small_semantic_fixture_includes_complete_function_and_test(tmp_path):
    (tmp_path / "processor.py").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "test_processor.py").write_text(TEST_SOURCE, encoding="utf-8")
    model = _Capture(_no_fix())

    proposal = propose_repair(
        RepairProposalRequest(
            verification_summary="one assertion failed",
            failure_output=(
                "test_processor.py:5: AssertionError: expected bulk, got standard"
            ),
            candidate_files=("processor.py", "test_processor.py"),
        ),
        workspace=Workspace(tmp_path),
        model_call=model,
    )

    assert proposal.valid is True
    assert len(model.calls) == 1
    system_prompt, user_prompt = model.calls[0]
    data = _untrusted_data(user_prompt)
    contexts = data["file_contexts"]

    assert data["candidate_files"] == ["processor.py", "test_processor.py"]
    assert [context["path"] for context in contexts] == [
        "processor.py", "test_processor.py",
    ]
    assert all(context["selection"] == "complete_file" for context in contexts)
    assert all(context["complete"] is True for context in contexts)
    assert all(context["line_numbered"] is True for context in contexts)
    assert "2:     remaining = len(records)" in contexts[0]["content"]
    assert "4:         remaining -= 2" in contexts[0]["content"]
    assert "5:     if remaining >= 3:" in contexts[0]["content"]
    assert "4: def test_three_records_use_bulk_path():" in contexts[1]["content"]
    normalized_system_prompt = " ".join(system_prompt.split())
    assert "check surrounding control flow, data flow, and mutation" in (
        normalized_system_prompt
    )
    assert "Do not default to appending code" in normalized_system_prompt
    assert "larger exact block" in normalized_system_prompt
    assert "must not depend on state already changed earlier" in (
        normalized_system_prompt
    )
    assert "put that decision before the mutation" in normalized_system_prompt
    assert "Do not compensate by changing a later threshold" in (
        normalized_system_prompt
    )
    assert "distinguish the original state from residual state" in (
        normalized_system_prompt
    )
    assert "must run before consumption or use a preserved value" in (
        normalized_system_prompt
    )
    assert "make the intended execution order observable" in (
        normalized_system_prompt
    )
    assert "Preserve existing behavior not contradicted by the failure" in (
        normalized_system_prompt
    )
    assert "no broader than the semantic repair requires" in normalized_system_prompt
    assert "old_text must include the exact mutation-and-decision block" in user_prompt
    assert "new_text must place the decision before the mutation" in user_prompt
    assert "do not append after it or change a later threshold" in user_prompt
    assert "consumable state after a mutation as residual, not original" in user_prompt


def test_large_candidate_uses_bounded_failure_line_window(tmp_path):
    before = [f"prefix_{number} = {number}" for number in range(600)]
    target = [
        "def evaluate(items):",
        "    count = len(items)",
        "    return count",
    ]
    after = [f"suffix_{number} = {number}" for number in range(600)]
    lines = before + target + after
    (tmp_path / "large.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    target_line = len(before) + 1
    model = _Capture(_no_fix())

    proposal = propose_repair(
        RepairProposalRequest(
            verification_summary="one assertion failed",
            failure_output=f"large.py:{target_line + 1}: AssertionError",
            candidate_files=("large.py",),
        ),
        workspace=Workspace(tmp_path),
        model_call=model,
    )

    assert proposal.valid is True
    context = _untrusted_data(model.calls[0][1])["file_contexts"][0]
    assert context["selection"] == "failure_line_window"
    assert context["complete"] is False
    assert context["line_numbered"] is True
    assert f"{target_line}: def evaluate(items):" in context["content"]
    assert len(context["content"].encode("utf-8")) <= MAX_FILE_EXCERPT_BYTES
    assert "1: prefix_0 = 0" not in context["content"]


def test_large_candidate_without_line_reference_uses_bounded_prefix(tmp_path):
    content = "\n".join(
        f"value_{number} = {number}" for number in range(1_200)
    ) + "\n"
    (tmp_path / "large.py").write_text(content, encoding="utf-8")
    model = _Capture(_no_fix())

    proposal = propose_repair(
        RepairProposalRequest(
            verification_summary="verification failed",
            failure_output="AssertionError without a source location",
            candidate_files=("large.py",),
        ),
        workspace=Workspace(tmp_path),
        model_call=model,
    )

    assert proposal.valid is True
    context = _untrusted_data(model.calls[0][1])["file_contexts"][0]
    assert context["selection"] == "bounded_prefix"
    assert context["complete"] is False
    assert context["content"].startswith("1: value_0 = 0")
    assert len(context["content"].encode("utf-8")) <= MAX_FILE_EXCERPT_BYTES


def test_absolute_failure_location_selects_bounded_candidate_window(tmp_path):
    lines = [f"value_{number} = {number}" for number in range(1_200)]
    (tmp_path / "large.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    model = _Capture(_no_fix())

    proposal = propose_repair(
        RepairProposalRequest(
            verification_summary="verification failed",
            failure_output=f"{tmp_path}/large.py:700: AssertionError",
            candidate_files=("large.py",),
        ),
        workspace=Workspace(tmp_path),
        model_call=model,
    )

    assert proposal.valid is True
    context = _untrusted_data(model.calls[0][1])["file_contexts"][0]
    assert context["selection"] == "failure_line_window"
    assert "700: value_699 = 699" in context["content"]
    assert len(context["content"].encode("utf-8")) <= MAX_FILE_EXCERPT_BYTES


def test_single_long_line_produces_nonempty_bounded_context(tmp_path):
    (tmp_path / "large.py").write_text("VALUE = '" + ("x" * 20_000), encoding="utf-8")
    model = _Capture(_no_fix())

    proposal = propose_repair(
        RepairProposalRequest(
            verification_summary="verification failed",
            failure_output="AssertionError without a source location",
            candidate_files=("large.py",),
        ),
        workspace=Workspace(tmp_path),
        model_call=model,
    )

    assert proposal.valid is True
    context = _untrusted_data(model.calls[0][1])["file_contexts"][0]
    assert context["selection"] == "bounded_prefix"
    assert context["content"].startswith("1: VALUE = '")
    assert 0 < len(context["content"].encode("utf-8")) <= MAX_FILE_EXCERPT_BYTES


def test_larger_exact_block_proposal_is_validated_without_mutation(tmp_path):
    source = tmp_path / "processor.py"
    source.write_text(SOURCE, encoding="utf-8")
    old_text = """    if remaining >= 2:
        remaining -= 2
    if remaining >= 3:
        return "bulk"
"""
    new_text = """    if remaining >= 3:
        return "bulk"
    if remaining >= 2:
        remaining -= 2
"""
    model = _Capture(json.dumps({
        "proposal_type": "patch_file",
        "path": "processor.py",
        "old_text": old_text,
        "new_text": new_text,
        "confidence": 0.9,
        "reason": "Check the bulk condition before the count is consumed",
    }))

    proposal = propose_repair(
        RepairProposalRequest(
            verification_summary="one assertion failed",
            failure_output="expected bulk, got standard",
            candidate_files=("processor.py",),
        ),
        workspace=Workspace(tmp_path),
        model_call=model,
    )

    assert proposal.valid is proposal.eligible_for_repair is True
    assert proposal.old_text == old_text
    assert proposal.new_text == new_text
    assert source.read_text(encoding="utf-8") == SOURCE
    assert len(model.calls) == 1


def test_phase8d_preserves_existing_bounds_and_limits():
    assert MAX_FILE_EXCERPT_BYTES == 8 * 1024
    assert MAX_PROPOSAL_TEXT_BYTES == 16 * 1024
    assert MAX_CANDIDATE_FILES == 5
    assert MIN_REPAIR_PROPOSAL_CONFIDENCE == 0.70
    assert MAX_MODEL_CALLS == 2
    assert MAX_SESSION_REPAIRS == 2
    assert MAX_SESSION_VERIFICATION_RUNS == 3
    assert MAX_SESSION_PROPOSAL_REQUESTS == 2
