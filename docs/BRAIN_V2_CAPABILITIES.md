# Brain v2 Phase 12 capability registry and Developer bridge

`core/capability_registry.py` is a static inventory of functionality already
present in Jarvis. Every immutable entry has a fixed machine-readable ID, a
planner category, an enabled flag, a future-executable flag, and a short safe
description. Registry lookups do not probe hardware, databases, models, memory,
skills, or networks.

`enabled` means the capability exists in this build. For most capabilities,
`executable` still describes readiness for a future controlled planner runtime.
Phase 12 adds one exception: Brain may execute the three allowlisted read-only
Developer Agent capabilities described below. Explicit memory writes, camera
capture, image measurement, and all other Developer Agent operations remain
manual-only or confirmation-stopped.

The planner still produces diagnostic steps. The validator first checks plan
structure, then resolves exact fixed action/category pairs to registry IDs. A
plan is execution-ready only when every step resolves and every required
capability is enabled and future-executable. Unknown steps and manual-only
capabilities make readiness false without changing validation or routing.

Registered IDs:

- Memory: `memory.recall_exact`, `memory.search_semantic`, `memory.write_explicit`
- Runtime: `runtime.health`, `runtime.identity`, `runtime.active_model`, `runtime.brain_status`
- System: `system.status`, `system.time`, `help.docs`
- Camera: `camera.status`, `camera.capture`
- Vision: `vision.describe`, `vision.measure`
- LLM: `llm.respond`

`brain capabilities` and `jarvis capabilities` return the static registry
grouped by category. Brain v2 status shows only capability IDs and readiness.
Planning remains observe-only. Non-developer requests continue through the
existing router exactly once.

## Phase 1 natural-language Developer execution

Brain uses bounded deterministic rules, not an LLM, to select these capabilities:

- `developer.list_files`
- `developer.read_file`
- `developer.git_status`

Before dispatch, the bridge requires matching enabled, executable, read-only,
non-mutating, non-confirmation metadata in both the Brain capability registry and
the canonical Developer Agent registry. The fixed Phase 1 allowlist is also
checked. The Developer Agent executor remains authoritative for argument and
workspace validation. A missing or conflicting registry entry fails closed.

Brain recognizes but does not execute natural-language requests for file writes,
patches, commands and pytest, Gradle, repair, repair proposals, staging, commits,
or bounded autonomous sessions. These requests return a safe
`confirmation_required` result; Phase 12 has no approval continuation.

Ambiguous developer requests use the `developer_unsupported` route, return an
unsupported result, and execute neither a tool nor the LLM fallback. Multi-step
developer planning and autonomous repair remain out of scope.
