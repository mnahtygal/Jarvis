# Brain v2 Phase 12 capability registry and Developer bridge

`core/capability_registry.py` is a static inventory of functionality already
present in Jarvis. Every immutable entry has a fixed machine-readable ID, a
planner category, an enabled flag, a future-executable flag, and a short safe
description. Registry lookups do not probe hardware, databases, models, memory,
skills, or networks.

`enabled` means the capability exists in this build. For most capabilities,
`executable` still describes readiness for a future controlled planner runtime.
Phase 12 adds three narrow exceptions: Brain may execute the three allowlisted
read-only Developer Agent capabilities directly, and may continue six fully
specified Developer operations or one frozen bounded developer session after a
separate explicit approval. Explicit memory writes, camera capture, image
measurement, and all other Developer Agent operations remain manual-only or
confirmation-stopped.

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

## Read-only developer planning

Long architecture missions are not executable developer requests. A bounded
inspection envelope must provide one canonical absolute workspace and a list of
at most 16 relative source paths under the exact `Inspect these files before
making changes:` heading. The bridge revalidates this envelope and reads only
those paths through the existing `developer.read_file` capability. Each read is
limited to 32 KiB and the complete inspection is limited to 256 KiB.

Workspace containment, symlink resolution, sensitive-file rejection, UTF-8
validation, and regular-file checks remain owned by the canonical read tool.
Failed or uninspected paths are reported separately and are never represented as
inspection evidence. The local model receives only successful bounded read
results and may summarize them, but cannot select more paths or tools. Its output
is explicitly labelled as model-generated, and first-person claims of additional
file access are withheld.

Planning has no executable authority. Planning results use
`approval_kind=planning`, always have `approval_pending=false`, and never create
a `PendingDeveloperAction`. `accept plan` only acknowledges planning; it cannot
execute tools or authorize a mutation.

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
most five minutes and is replaced by a newer Developer proposal. Restarting the
local Jarvis process clears it. An unrelated request, cancellation, validation
failure, expiry, or execution clears it. While a proposal is pending, non-exact
approval text is handled deterministically, cancels the proposal, and never falls
through to conversational model generation.
Approval phrases are fixed and deterministic (`approve`, `yes, approve`,
`proceed`, `execute it`, or `run it`); generic `yes` is not approval. Approval is
single-use and authorizes only the stored capability and arguments.
An execution-success lifecycle state additionally requires structured evidence
that the canonical tool or session was invoked and succeeded; conversational
model prose is never execution evidence.

Approval lifecycle results expose `approval_kind`, `approval_pending`, and a
random payload-free `pending_action_id`. Only `_propose_action()` may return
`approval_kind=execution` with `approval_pending=true`, and it does so only after
the validated pending object has been installed. Conversational approval
language is deterministically marked planning-only when no executable action is
pending. `no_pending_action`, expiry, revalidation, and single-use behavior are
unchanged.

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

`developer.repair_loop` and `developer.propose_repair` remain non-executable from
Brain. They may be recognized and confirmation-stopped, but a later approval
cannot dispatch them directly. There is no multi-action queue, approval-all, or
arbitrary autonomous tool selection.

## Phase 3 approved bounded developer session

Phase 3 adds exactly one separate approval-enabled high-level capability:
`developer.bounded_session`. It remains `executable=False` in both registries and
has no generic executor dispatch. Brain can reach only the canonical Phase 7
session function through the one-item Phase 3 allowlist after an exact, single-use
approval and complete revalidation.

Natural-language scope construction is deterministic. The Python form identifies
one existing source file and one existing test file, freezes pytest verification
for that test, makes both files readable candidates, and makes only the source
writable. A second exact form supports the existing fixed offline Gradle
verification with one source, one test, and one explicit project root. Ambiguous,
missing, traversing, protected, unsupported, or dynamically expanding scope is
refused. The LLM never selects the workspace, candidates, writable paths,
verification command, or limits.

The proposal stores immutable scope plus snapshots and content digests for every
candidate. Approval rechecks the workspace, both registries, canonical handler,
verification policy, fixed limits, paths, snapshots, and digests before invoking
the existing session. Tests are read-only in every Phase 3 natural-language
scope. The session always verifies first, stops immediately if green, and retains
the existing limits of two repairs, three verification runs, and two proposal
requests. Phase 6 remains authoritative for structured proposals, confidence,
exact patches, protected paths, and stale-state checks.

The session performs no stage, commit, push, branch, reset, restore, clean, or
checkout operation. Failed repairs are not rolled back automatically. Results
expose only verification kind, counters, safe modified paths, final stop code, and
the fact that no Git action was performed. Prompts, diagnostics, source, patches,
command output, and raw model responses remain ephemeral and absent from Brain
status and durable memory. There is no recursive session or background work.

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

## Greenfield project orchestration

Brain exposes one additional high-level capability,
`developer.greenfield_project`, for small Python/pytest projects. It is enabled,
mutating, confirmation-required, and `executable=False` in both static
registries. It has no planner mapping and no generic executor dispatch. The only
execution path is the existing single-use, five-minute Brain approval
continuation followed by the dedicated greenfield handler.

Recognition is deterministic and requires a clearly stated Python project, one
canonical absolute workspace directly beneath `/home/mnahtygal/projects`, an
exact list of two to five flat `.py` filenames, at least one source and one test,
and pytest verification. Vague requests remain conversational or unsupported.
Paths containing traversal, expansion syntax, globs, symlink roots, existing
destinations, locations inside Jarvis, `/tmp`, or any other parent are refused.

Before confirmation, recognition and proposal sealing are deterministic and
model-free. The pending action binds the exact workspace, filenames, roles,
requirements, pytest target, parent inode, and hard limits. No source or test
content is generated and no file is created until exact approval.

After approval, the existing local model may provide content only for the
caller-selected filenames. Generation uses deterministic sampling, disabled
thinking, a compact JSON grammar bound to the exact approved filename order,
strict duplicate-field/schema validation, an
8 KiB per-file limit, a 24 KiB total-content limit, and at most one correction
retry. A complete leading model reasoning envelope is removed only when it
precedes the JSON object; identical text inside generated file content is
preserved. Truncation, transport, JSON, schema, scope, size, Python, and AST
failures retain bounded reason codes. Logs contain only attempt, reason, byte and
file counts, endpoint/status, finish reason, and elapsed time.
Generated Python must parse and may import only standard-library modules,
pytest, or approved project modules; process, network, installer, dynamic-code,
and destructive-call primitives are rejected. The model cannot supply commands,
verification targets, directories, roles, limits, or extra files.
The AST checks are defense-in-depth input screening, not an operating-system
sandbox; execution retains the documented pytest trust boundary.

Approval binds the sealed deterministic proposal. The bridge rechecks the
registry, canonical handler, allowed parent inode, absent destination, exact file
and role lists, frozen `pytest -q <test files>` target, hard limits, and proposal
digest before generation. It then creates and validates an immutable,
content-inclusive manifest and rechecks model configuration, scope, limits,
parent inode, and manifest digest before filesystem mutation. Approval is
expiring, single-use,
non-replayable, and invalidated by unrelated requests under the existing policy.
Invalid approval text returns a deterministic no-execution result, including for
common approval typos after the pending action has already been cleared.

Execution creates exactly one project directory with no recursive parent
creation, writes each approved file through `developer.write_file`, and invokes
the bounded-session engine. Python verification runs inside a Bubblewrap namespace
using a read-only disposable copy of only the approved files; the original project,
broader home directory, network, Git credentials, model files, and unrelated user
files are not mounted. Its first action is isolated verification, so green
projects stop after one run without a repair-model call. Red projects retain the
existing ceiling of two candidate repairs, three total verification runs, and two
proposal requests. A passing candidate's exact bytes and SHA-256 are sealed before
cleanup and atomically promoted only after every original source/test identity and
proposal precondition is revalidated. Failed candidates leave the project source
unchanged, and the pytest target never changes.

Bootstrap failures retain already-created user-visible files and return an
honest partial-failure summary. The workflow performs no package installation,
Git initialization, stage, commit, push, branch operation, dynamic file
discovery, nested session, background execution, or durable storage of source,
tests, prompts, manifests, or repair payloads. Safe results distinguish proposals,
candidate attempts, rejected candidates, promoted repairs, verification runs,
modified source paths, final status, and confirmation that Git was untouched.
