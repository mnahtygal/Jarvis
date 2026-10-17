"""Controlled developer-agent tool foundation for Jarvis."""

from core.developer_agent.developer_session import (
    MAX_SESSION_MODEL_CALLS,
    MAX_MUTATION_PATHS,
    MAX_SESSION_PROPOSAL_REQUESTS,
    MAX_SESSION_REPAIRS,
    MAX_SESSION_VERIFICATION_RUNS,
    DeveloperSessionAttempt,
    DeveloperSessionRequest,
    DeveloperSessionResult,
    DiagnosticExcerpt,
    VerificationSpec,
    build_diagnostic_excerpt,
    run_bounded_developer_session,
    run_developer_session_request,
    validate_developer_session_request,
)
from core.developer_agent.executor import execute_tool
from core.developer_agent.repair_loop import (
    RepairAttempt,
    RepairResult,
    run_repair_loop,
)
from core.developer_agent.repair_proposal import (
    MIN_REPAIR_PROPOSAL_CONFIDENCE,
    RepairProposal,
    RepairProposalRequest,
    proposal_to_predefined_repair,
    propose_repair,
)
from core.developer_agent.registry import ToolDefinition, get_tool, list_tools
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.verification import VerificationEvidence
from core.developer_agent.workspace import Workspace, resolve_workspace_path

__all__ = (
    "ToolDefinition",
    "ToolResult",
    "VerificationEvidence",
    "Workspace",
    "DeveloperSessionAttempt",
    "DeveloperSessionRequest",
    "DeveloperSessionResult",
    "DiagnosticExcerpt",
    "VerificationSpec",
    "MAX_SESSION_MODEL_CALLS",
    "MAX_MUTATION_PATHS",
    "MAX_SESSION_PROPOSAL_REQUESTS",
    "MAX_SESSION_REPAIRS",
    "MAX_SESSION_VERIFICATION_RUNS",
    "build_diagnostic_excerpt",
    "execute_tool",
    "get_tool",
    "list_tools",
    "RepairAttempt",
    "RepairProposal",
    "RepairProposalRequest",
    "RepairResult",
    "MIN_REPAIR_PROPOSAL_CONFIDENCE",
    "proposal_to_predefined_repair",
    "propose_repair",
    "resolve_workspace_path",
    "run_bounded_developer_session",
    "run_developer_session_request",
    "validate_developer_session_request",
    "run_repair_loop",
)
