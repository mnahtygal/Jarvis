# Brain v2 Phase 11 capability registry

`core/capability_registry.py` is a static inventory of functionality already
present in Jarvis. Every immutable entry has a fixed machine-readable ID, a
planner category, an enabled flag, a future-executable flag, and a short safe
description. Registry lookups do not probe hardware, databases, models, memory,
skills, or networks.

`enabled` means the capability exists in this build. `executable` means it is
conceptually eligible for a future controlled planner runtime; it does not make
the capability executable in Phase 11. Explicit memory writes, camera capture,
and image measurement remain manual-only because they write data, operate
hardware, or require stronger input/calibration controls.

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
Plans and capabilities remain observe-only: no plan step is executed, and the
existing router still handles each request exactly once.
