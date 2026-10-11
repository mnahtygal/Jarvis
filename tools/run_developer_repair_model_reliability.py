#!/usr/bin/env python3
"""Run five proposal-only checks against the real structured repair model."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.developer_agent import (  # noqa: E402
    RepairProposalRequest,
    Workspace,
    propose_repair,
)


CALL_COUNT = 5


def main() -> int:
    observations: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="jarvis-repair-reliability-") as temporary:
        root = Path(temporary)
        source = root / "example.py"
        source.write_text("VALUE = 1\n", encoding="utf-8")
        workspace = Workspace(root)
        request = RepairProposalRequest(
            verification_summary="pytest failed with one assertion",
            failure_output="AssertionError: expected 2, got 1",
            candidate_files=("example.py",),
            file_excerpts={"example.py": "VALUE = 1"},
        )

        for number in range(1, CALL_COUNT + 1):
            proposal = propose_repair(request, workspace=workspace)
            parse_success = proposal.status not in {
                "invalid_model_output",
                "model_failure",
            }
            observations.append({
                "call": number,
                "parse_success": parse_success,
                "schema_success": parse_success,
                "proposal_type": proposal.proposal_type,
                "confidence": proposal.confidence,
                "validation_status": proposal.status,
                "valid": proposal.valid,
            })

        source_unchanged = source.read_text(encoding="utf-8") == "VALUE = 1\n"

    successes = sum(
        observation["parse_success"] is True for observation in observations
    )
    print(json.dumps({
        "calls": observations,
        "parse_successes": successes,
        "schema_successes": successes,
        "source_unchanged": source_unchanged,
    }, indent=2))
    return 0 if successes == CALL_COUNT and source_unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
