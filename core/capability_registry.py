"""Static, non-executing capability registry for Brain v2."""

from __future__ import annotations

from dataclasses import dataclass

from core.planner import PlanStep


@dataclass(frozen=True)
class Capability:
    capability_id: str
    category: str
    enabled: bool
    executable: bool
    description: str
    read_only: bool = False
    mutating: bool = False
    requires_confirmation: bool = False


_CAPABILITIES = (
    Capability("memory.recall_exact", "memory", True, True, "Recall an exact saved fact"),
    Capability("memory.search_semantic", "memory", True, True, "Search semantic memory"),
    Capability("memory.write_explicit", "memory", True, False, "Store an explicit memory command"),
    Capability("runtime.health", "runtime", True, True, "Inspect Jarvis runtime health"),
    Capability("runtime.identity", "runtime", True, True, "Inspect runtime identity"),
    Capability("runtime.active_model", "runtime", True, True, "Inspect the active local model"),
    Capability("runtime.brain_status", "runtime", True, True, "Inspect brain runtime status"),
    Capability("system.status", "system", True, True, "Inspect local system status"),
    Capability("system.time", "system", True, True, "Read local time and date"),
    Capability("camera.status", "camera", True, True, "Inspect active camera status"),
    Capability("camera.capture", "camera", True, False, "Capture a camera image"),
    Capability("vision.describe", "vision", True, True, "Describe an existing image"),
    Capability("vision.measure", "vision", True, False, "Measure an object in an image"),
    Capability("help.docs", "system", True, True, "Show Jarvis help and documentation"),
    Capability("llm.respond", "llm", True, True, "Generate a local model response"),
    Capability("developer.list_files", "developer", True, True, "List workspace files", True),
    Capability("developer.read_file", "developer", True, True, "Read workspace text files", True),
    Capability("developer.git_status", "developer", True, True, "Inspect workspace Git status", True),
    Capability(
        capability_id="developer.write_file",
        category="developer",
        enabled=True,
        executable=False,
        description="Write bounded workspace text files",
        read_only=False,
        mutating=True,
        requires_confirmation=True,
    ),
    Capability(
        capability_id="developer.patch_file",
        category="developer",
        enabled=True,
        executable=False,
        description="Patch exact text in workspace files",
        read_only=False,
        mutating=True,
        requires_confirmation=True,
    ),
    Capability(
        capability_id="developer.run_command",
        category="developer",
        enabled=True,
        executable=False,
        description="Run an allowlisted workspace command",
        read_only=False,
        mutating=True,
        requires_confirmation=True,
    ),
    Capability(
        capability_id="developer.repair_loop",
        category="developer",
        enabled=True,
        executable=False,
        description="Run a bounded predefined verify and repair sequence",
        read_only=False,
        mutating=True,
        requires_confirmation=True,
    ),
)

_CAPABILITY_BY_ID = {
    capability.capability_id: capability
    for capability in _CAPABILITIES
}

_PLAN_STEP_CAPABILITIES = {
    ("runtime", "check runtime health"): ("runtime.health",),
    ("runtime", "inspect runtime state"): ("runtime.health",),
    ("runtime", "inspect runtime identity"): ("runtime.identity",),
    ("system", "inspect active model"): ("runtime.active_model",),
    ("system", "inspect requested state"): ("system.status",),
    ("camera", "capture workbench image"): ("camera.capture",),
    ("camera", "capture image"): ("camera.capture",),
    ("vision", "analyze captured image"): ("vision.describe",),
    ("vision", "analyze result"): ("vision.describe",),
    ("memory", "retrieve relevant memory"): ("memory.search_semantic",),
    ("memory", "retrieve relevant information"): ("memory.search_semantic",),
    ("comparison", "compare results"): ("llm.respond",),
    ("summary", "summarize result"): ("llm.respond",),
    ("summary", "return description"): ("llm.respond",),
    ("summary", "summarize comparison"): ("llm.respond",),
}


def get_capability(capability_id: str) -> Capability | None:
    """Return an immutable capability definition, or None when unknown."""

    if not isinstance(capability_id, str):
        return None
    return _CAPABILITY_BY_ID.get(capability_id)


def list_capabilities() -> tuple[Capability, ...]:
    """Return all static capabilities in deterministic order."""

    return _CAPABILITIES


def capabilities_for_category(category: str) -> tuple[Capability, ...]:
    """Return capabilities assigned to a fixed planner category."""

    if not isinstance(category, str):
        return ()
    return tuple(
        capability
        for capability in _CAPABILITIES
        if capability.category == category
    )


def is_capability_available(capability_id: str) -> bool:
    capability = get_capability(capability_id)
    return bool(capability and capability.enabled)


def resolve_plan_step_capabilities(step: PlanStep) -> tuple[str, ...]:
    """Resolve a fixed planner step to capability IDs without executing it."""

    if not isinstance(step, PlanStep):
        return ()
    return _PLAN_STEP_CAPABILITIES.get((step.category, step.action), ())


def get_capabilities_response() -> str:
    """Return a concise deterministic registry summary."""

    category_labels = {
        "memory": "Memory",
        "runtime": "Runtime",
        "system": "System",
        "camera": "Camera",
        "vision": "Vision",
        "llm": "LLM",
        "developer": "Developer",
    }
    lines = ["Jarvis Brain v2 capabilities:"]
    for category, label in category_labels.items():
        capabilities = capabilities_for_category(category)
        if not capabilities:
            continue
        lines.append(f"{label}:")
        for capability in capabilities:
            if not capability.enabled:
                readiness = "disabled"
            elif capability.executable:
                readiness = "future-executable"
            else:
                readiness = "manual-only"
            lines.append(f"- {capability.capability_id} [{readiness}]")
    lines.append("Planning remains observe-only; no capabilities are executed.")
    return "\n".join(lines)
