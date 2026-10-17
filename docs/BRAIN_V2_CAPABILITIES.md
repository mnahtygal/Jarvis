# Brain v2 Phase 12 capability registry and Developer bridge

`core/capability_registry.py` is a static inventory of functionality already
present in Jarvis. Every immutable entry has a fixed machine-readable ID, a
planner category, an enabled flag, a future-executable flag, and a short safe
description. Registry lookups do not probe hardware, databases, models, memory,
skills, or networks.

`enabled` means the capability exists in this build. For most capabilities,
`executable` still describes readiness for a future controlled planner runtime.
Phase 12 adds two narrow exceptions: Brain may execute the three allowlisted
read-only Developer Agent capabilities directly, and may continue six fully
specified Developer operations after a separate explicit approval. Explicit
memory writes, camera capture, image measurement, and all other Developer Agent
operations remain manual-only or confirmation-stopped.

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

## Phase 2 explicit-approval continuation

Brain may propose exactly one fully specified action for these capabilities:

- `developer.write_file`
- `developer.patch_file`
- `developer.run_command`
- `developer.gradle_test`
- `developer.git_stage`
- `developer.git_commit`

The proposal executes nothing. It is held in bounded process-local memory for at
most five minutes and is replaced by a newer Developer proposal. An unrelated
request, cancellation, validation failure, expiry, or execution clears it.
Approval phrases are fixed and deterministic (`approve`, `yes, approve`,
`proceed`, `execute it`, or `run it`); generic `yes` is not approval. Approval is
single-use and authorizes only the stored capability and arguments.

At approval time the bridge rechecks both registry entries, the explicit Phase 2
allowlist, confirmation/non-autonomous metadata, argument shape, workspace root,
and the relevant file, command, Gradle, or Git policy. Patch and Git proposals
also carry current-state seals. A changed source, index, worktree, registry, or
workspace fails closed. `git_commit` additionally requires current sealed
verification evidence from a successful approved `run_command` verification or
`gradle_test`; it never stages files itself.
Git seals use two matching bounded passes over porcelain status, tracked and
cached diffs, and untracked file contents. Git-command output and aggregate
untracked content each have a 256 KiB bound; overflow or concurrent change is a
hard refusal, never a truncated fingerprint.

The supported deterministic request forms are intentionally narrow: create a new
file with inline bounded content; replace one JSON-quoted exact string in a file;
run an argv-only command after `Run command:`; run the fixed Gradle test in one
project; stage explicit space-separated files; or commit already-staged content
with a message. Existing canonical Developer Agent policy remains authoritative.
Approval does not enable a shell, arbitrary commands, alternate Gradle tasks,
stage-all, push, amend, or history rewriting.

`developer.repair_loop`, `developer.propose_repair`, and
`developer.bounded_session` remain non-executable from Brain. They may be
recognized and confirmation-stopped, but a later approval cannot dispatch them.
There is no multi-action queue, approval-all, autonomous tool selection, or
repair/session loop.

Pending state, Developer prompts, and approval/cancellation text are not written
to durable conversation history, project memory, semantic memory, or exact
personal memory. Raw Developer prompts are not printed, and Brain status contains
only safe lifecycle fields. The current API exposes no
caller/session identifier, so this state is scoped to the single local Jarvis
process/user conversation. Multi-user approval isolation requires future session
identity plumbing and is not implied here.

Ambiguous developer requests use the `developer_unsupported` route, return an
unsupported result, and execute neither a tool nor the LLM fallback. Multi-step
developer planning and autonomous repair remain out of scope.
