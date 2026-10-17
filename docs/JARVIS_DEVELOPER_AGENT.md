# Jarvis Developer Agent

## Purpose

The Developer Agent is a controlled, local-first tool boundary for future software
development workflows. Phase 1 provides read-only inspection. Phase 2 adds two
explicit, bounded file-mutation tools. Phase 3 adds a confirmation-gated command
boundary with fixed command grammars, not a generic shell. Phase 4 adds a bounded,
confirmation-gated verify/repair/reverify orchestrator for predefined repairs.
Phase 5 adds explicit-path staging and one verification-gated local commit.
Phase 6 adds one bounded, data-only LLM-assisted repair proposal.
Phase 7 connects those boundaries into one explicitly approved, bounded autonomous
developer session. Phase 8B adds one dedicated offline Android/Gradle unit-test
verification capability without widening the generic command grammar. Phase 8C
hardens repair-model structured output at generation time.

Brain v2 Phase 12 has a narrow natural-language bridge for the three Phase 1
read-only tools, six Phase 2 single-action explicit-approval continuations, and
one Phase 3 explicitly approved bounded session. It does not expose unrestricted
autonomous developer mode.

## Brain v2 Phase 1 natural-language bridge

The following requests may execute after deterministic parsing and validation
against both the Brain and canonical Developer Agent registries:

- `developer.list_files`
- `developer.read_file`
- `developer.git_status`

The existing Developer Agent executor remains authoritative for argument schemas,
workspace containment, symlink handling, sensitive-file refusal, output bounds,
and safe errors. Brain does not accept LLM-generated capability selections or
argument dictionaries.

## Brain v2 Phase 2 explicit approval

Brain can hold one fully specified proposal for `developer.write_file`,
`developer.patch_file`, `developer.run_command`, `developer.gradle_test`,
`developer.git_stage`, or `developer.git_commit`. The initial request returns
`confirmation_required` and executes nothing. A separate exact approval response
causes one attempt through the canonical executor after all registry, workspace,
argument, file, command, Gradle, and Git checks are rerun. Approval is single-use,
argument-bound, expires after five minutes, and cannot approve multiple actions.

Cancellation clears the proposal. A newer Developer request replaces it, while a
materially unrelated request deterministically invalidates it without entering
the conversational model route. Changed
patch sources, Git state, workspace identity, or registry metadata fail closed.
Successful verification evidence is output-free and bound to the current
workspace status before it can support a later commit. Commit never auto-stages.
The Git seal hashes porcelain status, the tracked worktree diff, the cached diff,
and untracked file names and contents twice. Each Git command is capped at 256
KiB and all untracked content is capped at 256 KiB per pass. Any overflow,
unreadable or symlinked untracked path, concurrent change, or unequal pass fails
closed rather than hashing truncated state.

The bridge keeps confirmation-gated registry entries `executable=False`; that
flag continues to mean they are unavailable to autonomous planning. The separate
fixed Phase 2 allowlist plus an exact, single-use approval is the only Brain
execution gate for those six tools. `developer.repair_loop` and
`developer.propose_repair` remain unavailable through direct Brain approval.

Pending payloads live only in bounded process memory. All Developer bridge turns,
including approval and cancellation text, bypass durable conversation history,
project memory, semantic memory, and exact/personal memory. Raw Developer prompts
are not printed to the console. Brain status contains safe lifecycle fields only.
Restarting the local Jarvis process clears every pending approval.
Only structured Developer results with both `tool_invoked=true` and
`tool_success=true` may report an execution-success lifecycle state. Chat-model
text cannot prove that a file, command, test, project, or Git operation ran.
The current local API has no session identifier, so
the pending slot belongs to the one local process/user conversation. `/text` and
`/ask` continue to return ordinary strings; no UI changes are required.
Concurrent independent users and multi-user approval isolation are not supported.

Ambiguous developer requests execute nothing, and multi-step or autonomous
developer plans remain unsupported.

## Brain v2 Phase 3 approved bounded session

Brain may propose exactly one `developer.bounded_session` using the existing
Phase 7 implementation. It uses the same single pending slot, exact approval
phrases, five-minute expiry, interruption rules, atomic single-use consumption,
and memory/privacy exclusions as Phase 2. The capability remains
`executable=False`, is absent from the generic executor dispatch table, and is
reachable only through an exact one-item Phase 3 allowlist plus matching Brain and
Developer Agent registry metadata and the canonical session handler.

For Python, Brain accepts an explicit source and explicit test path, freezes
`pytest -q <test-path>` through the existing command policy, and makes only the
source writable. For Gradle, the explicit form freezes one Java/Kotlin source,
one Java/Kotlin test, one project root, and the existing reviewed offline
`developer.gradle_test` behavior.
Every candidate must already exist and remain unchanged between confirmation and
approval. Tests are always readable but non-writable in Phase 3. No model can add
a candidate, writable path, command, task, flag, workspace, or retry.

The canonical session verifies before requesting a repair. Green verification
returns immediately without a model call or mutation. A failure may use the
existing Phase 6 proposal path and exact patch/write tools, with the unchanged
hard ceilings of two repairs, three verification runs, and two proposal requests.
Pytest verification uses a fresh non-writing bytecode-cache namespace on every
run so a same-size rapid repair cannot be masked by a pre-existing `.pyc` file.
Model unavailability, malformed output, low confidence, protected/out-of-scope
paths, stale snapshots, policy failure, and exhausted limits stop safely. Applied
repairs are reported honestly and are not rolled back when final verification
fails.

The response contains only pass/fail state, verification and repair counts, safe
modified paths, stop reason, and confirmation that no stage/commit/push action was
performed. Brain status keeps only capability, invocation, verification kind,
counters, final state, and a safe error code. It never stores source, patches,
prompts, diagnostics, command output, or raw model output. `/text` and `/ask`
remain string-compatible; there is no UI, background task, recursive session,
planner expansion, automatic Git, or push behavior.

Successful read-only calls use the `developer_tool` route. Recognized operations
that stop for confirmation use `developer_confirmation`. Tool output is adapted
to the existing string response used by the API and UI, while Brain retains only
safe structured lifecycle metadata for status reporting.
Ambiguous or rejected pre-dispatch developer requests use
`developer_unsupported` and execute nothing.

## Architecture

The implementation is intentionally small:

- `core/developer_agent/tool_models.py` defines immutable tool results.
- `core/developer_agent/workspace.py` owns the shared workspace boundary and
  `core/developer_agent/policy.py` owns sensitive/protected path rules.
- `core/developer_agent/command_policy.py` owns the fixed executable and argument
  allowlist for command execution.
- `core/developer_agent/tools/gradle_test.py` validates one supported Gradle
  wrapper and runs one fixed Android JVM unit-test task.
- `core/developer_agent/registry.py` contains a fixed tool registry.
- `core/developer_agent/executor.py` validates arguments and uses a fixed dispatch
  table.
- `core/developer_agent/repair_loop.py` sequences approved verification commands
  and predefined repairs through that executor with hard attempt limits.
- `core/developer_agent/repair_proposal.py` builds and validates one bounded local
  model proposal without applying it.
- `core/developer_agent/developer_session.py` runs dynamic Phase 6 proposals inside
  one immutable, human-approved session scope.
- `core/developer_agent/verification.py` reduces successful verification results
  to immutable, output-free evidence.
- `core/developer_agent/git_safety.py` owns fixed local Git inspection, staging,
  and commit operations plus their isolated environment.
- `core/developer_agent/mutation.py` provides shared atomic-write behavior.
- `core/developer_agent/tools/` contains the fixed tool implementations.
- `core/capability_registry.py` advertises the matching Brain v2 capabilities.

There is no dynamic registration, dynamic import, `eval`, `exec`, or generic shell
tool. The Developer Agent receives argv lists. Phase 2's fixed `Run command:`
grammar tokenizes one user-authored string deterministically, then the existing
command-policy engine validates every resulting argument before confirmation and
again before execution.

## Phase 1 tools

### `developer.list_files`

Lists a directory inside the workspace. Results are sorted and bounded. Recursive
listings skip `.git`, `.venv`, `__pycache__`, `node_modules`, `build`, and `dist`
unless one of those directories is explicitly selected as the listing root.
Each visited directory also has a fixed scan ceiling, preventing a single unusually
large directory from consuming unbounded memory before sorting.

### `developer.read_file`

Reads bounded UTF-8 text and returns line-numbered output. It refuses directories,
binary or invalid UTF-8 files, and explicitly sensitive names: `.env`, `.env.*`,
`*.pem`, `*.key`, `credentials*`, and `secrets*`.

### `developer.git_status`

Runs only this fixed argument vector with a timeout and captured output:

```text
git status --short --branch
```

It uses the workspace root as its working directory, never enables a shell, and
sets `GIT_OPTIONAL_LOCKS=0` to prevent optional index refresh writes.

## Phase 2 tools

Phase 2 tools are enabled for explicit calls through the developer executor. Both
are marked mutating, non-read-only, and `requires_confirmation=True`. They are
marked `executable=False` for autonomous planning. No interactive confirmation UI
exists yet; a future caller must enforce a confirmation or policy gate before any
autonomous invocation.

### `developer.write_file`

Creates bounded UTF-8 text files. Existing files are refused unless
`overwrite=True`, and missing parent directories are refused unless
`create_parent_dirs=True`. Existing targets must already be bounded UTF-8 text;
binary files are not overwritten.

### `developer.patch_file`

Performs literal, case-sensitive text replacement without regular expressions,
fuzzy matching, or arbitrary diff application. `old_text` must be non-empty. The
actual exact match count must equal `expected_matches` (default `1`) or the file is
left byte-for-byte unchanged.

## Workspace and security model

The default approved root is the Jarvis repository containing the implementation.
A caller may construct a `Workspace` with another explicit project root for tests
or controlled embedding.

Every filesystem tool resolves the requested path and all symlinks before checking
containment. Absolute paths and `..` paths are accepted only when their resolved
destination remains inside the configured root. Escapes to a home directory,
`/etc`, `/proc`, or any other external location are rejected. Recursive listing
does not follow symlinks outside the root.

Tool results contain stable error codes and safe messages; raw exceptions are not
returned. File reads, line ranges, directory output, Git output, and subprocess
duration are bounded.

Mutation additionally refuses `.env*`, `*.pem`, `*.key`, `credentials*`,
`secrets*`, every path beneath `.git/`, and the three protected personal audio
tester filenames. `.gitignore` remains editable. Content and patch payload sizes
are bounded.

Git checkpoint policy additionally protects `testbrain.py` and applies the same
sensitive-name, Git-metadata, and personal audio tester restrictions to both
requested stage paths and the complete staged index.

Successful mutations write a temporary file in the validated target directory,
flush and sync it, revalidate containment and protection immediately before the
mutation, and atomically link or replace the target. Existing file modes are
preserved. Concurrent changes detected during patching or overwrite validation
cause a safe refusal.

## Phase 3 command tool

### `developer.run_command`

Runs only policy-approved argv vectors at the fixed workspace root. It is enabled
for explicit executor calls but is marked mutating, `requires_confirmation=True`,
and `executable=False`. Brain v2 advertises the same manual-only capability.
Natural language may recognize the operation, but stops with
`confirmation_required`; there is no planner mapping, retry loop, approval
continuation, or autonomous invocation.

Allowed command forms are:

```text
pwd
git status --short --branch
git diff
git diff --check
git diff --cached
git diff --cached --check
git branch --show-current
python|python3 -m pytest [approved options and workspace targets]
pytest [approved options and workspace targets]
python|python3 -m compileall [-q] <workspace paths...>
python|python3 -m py_compile <workspace Python files...>
```

Git arguments must exactly match one of the listed read-only forms. Python accepts
only `-m` followed by `pytest`, `compileall`, or `py_compile`; `-c`, stdin, script
paths, arbitrary modules, and interpreter flags are rejected. The standalone
`pytest` spelling is translated to the current trusted Python interpreter. Pytest
allows only a small option set used for repository verification, validates all
test and ignore paths inside the workspace, disables third-party plugin autoload,
uses fixed workspace root/config boundaries, and ignores ambient `PYTEST_ADDOPTS`
and `PYTHONPATH` values. Safe-path mode prevents workspace files from shadowing the
approved `pytest`, `compileall`, or `py_compile` modules. Compileall additionally
ignores symlinks whose targets leave the workspace.

Executables are selected by policy rather than by a user-supplied path. Python
uses the interpreter already running Jarvis. Git and `pwd` resolve only from the
fixed system path `/usr/local/bin:/usr/bin:/bin`. Absolute executable paths and
alternate spellings are rejected.

The child receives no stdin, always runs with the workspace root as `cwd`, and
gets a minimal environment containing only a fixed `PATH`, workspace-scoped
`HOME`, UTF-8 locale settings, a safe active-virtualenv marker when applicable,
and command-specific safety variables. Git uses `GIT_OPTIONAL_LOCKS=0`, disables
global/system configuration, prompts, pagers, filesystem-monitor helpers, external
diff drivers, and text conversion commands.

The default timeout is 60 seconds and the hard maximum is 300 seconds. A timed-out
child is terminated, then killed if it does not exit during the bounded grace
period. Stdout and stderr are drained independently so a full pipe cannot deadlock
the process. Their combined in-memory capture defaults to 128 KiB and cannot
exceed 1 MiB; excess output is discarded while byte counts and truncation metadata
are retained. Results expose separate captured streams, exit status, timeout state,
byte counts, truncation state, and command family without returning raw exceptions.

Shell syntax, argument files, unknown executables, user-controlled `cwd` or
environment, pytest plugin/config injection flags, mutation-capable Git commands,
package installers, network clients, privilege tools, file mutation utilities,
service/process controls, and unrestricted interpreters are rejected.

## Phase 4 repair loop

`run_repair_loop(...)` is an explicit Python API for a controlled sequence:

```text
verify -> apply one predefined repair -> reverify -> stop or repeat
```

The caller supplies one verification argv list and the complete ordered repair
sequence. Every repair is a fully specified `developer.patch_file` or
`developer.write_file` request. The loop decides only when to apply the next
repair; it does not generate paths, source text, patch bodies, or fixes. There is
no LLM interpretation or LLM-generated repair in Phase 4.

The API validates the complete request before execution, rejects unknown fields
and tool IDs, and requires `approved=True` before running even the initial
verification. The hard limits are three repair attempts and four verification
runs (initial verification plus at most three reverification cycles). Callers may
choose a lower repair limit but cannot raise it. A deterministic fingerprint
prevents applying the same supplied repair twice in one loop.

Verification always calls `developer.run_command`, so the Phase 3 argv grammar,
workspace checks, timeout, environment, and output bounds remain authoritative.
Mutation always calls the existing developer executor and its `patch_file` or
`write_file` implementation, preserving all workspace, protected-path, size, and
atomic-write policies. The loop has no direct subprocess or filesystem mutation
path and cannot dispatch Git mutation, package management, network, deletion, or
shell tools.

The loop stops on verification success, rejected or timed-out verification,
rejected or failed repair, exhausted repairs, a duplicate repair, the attempt
limit, or an unexpected executor failure. Its immutable result contains only safe
summary metadata: status, counts, per-cycle outcomes, and the final exit code. It
does not retain command output, source contents, patch bodies, or raw exceptions.

Brain v2 advertises `developer.repair_loop` as enabled, mutating,
`requires_confirmation=True`, and `executable=False`. Natural language may
recognize the operation but stops with `confirmation_required`; there is no
planner mapping, approval continuation, interactive confirmation UI, or
autonomous Brain entry point. Phase 4 remains a manual/internal API whose caller
must explicitly approve the supplied sequence.

## Phase 5 controlled Git checkpoint

Phase 5 provides two dedicated tools instead of broadening the Phase 3 command
grammar:

### `developer.git_stage`

Stages an explicitly approved, bounded list of canonical repository-relative
regular files. `approved=True` is required. Directories, `.`, option-like values,
wildcards, caller pathspec magic, absolute paths, traversal, symlinks, missing
files, protected paths, duplicates, and tracked deletions are refused. Explicit
new source files and modified tracked files are supported.

The tool inspects the existing staged index before mutation. Any already-staged
path must be within the caller's approved set, must pass protected-file policy,
and must have only `A` or `M` status. After the fixed `git add -- <paths>` operation,
the complete staged index is inspected again. The literal-path environment and
required `--` separator prevent option and pathspec interpretation. Repositories
with configured external clean/process filters are rejected before staging so Git
cannot invoke a repository-defined filter command.

### `developer.git_commit`

Creates one local commit from the already-staged index. It requires
`approved=True`, a caller-supplied single-line message of at most 200 UTF-8 bytes,
and a `VerificationEvidence` object derived from a successful
`developer.run_command` result for `pytest`, `compileall`, or `py_compile`, or a
successful `developer.gradle_test` result for the fixed Android task. Evidence
stores only success, command family, exit code, and source; command output is not
copied into the evidence or commit result. A bare `tests_passed=True` flag is not
accepted.

Verification evidence is a trusted-manual-caller gate, not a cryptographic
attestation. It is intentionally not bound to a particular HEAD, staged index,
worktree state, timestamp, or freshness window. The trusted caller must therefore
run verification against the intended state immediately before creating a
checkpoint; Phase 5 does not claim protection against a caller that fabricates or
reuses an otherwise valid result object.

Immediately before commit, the tool runs fixed internal equivalents of
`git diff --cached --check` and NUL-delimited
`git diff --cached --name-status`. It refuses an empty index, protected or
sensitive paths, deletions, renames, copies, type changes, conflicts, whitespace
errors, and any status other than addition or modification. It commits exactly the
already-staged safe set and returns only a file count, branch, and commit SHA.

All Git subprocesses use fixed argv, a fixed system `PATH`, no shell or stdin, a
minimal environment, disabled prompts/editors/pagers, disabled external diffs and
filesystem monitors, and bounded time/output. Commit uses fixed `--no-verify` and
`--no-gpg-sign` options and overrides `core.hooksPath=/dev/null`. Hooks are disabled
because running repository-controlled hook programs would cross the controlled
tool boundary; this also suppresses hook types that `--no-verify` alone does not
bypass. No caller can supply Git flags or options.

Phase 5 has no push, branch mutation, amend, signing, deletion staging, reset,
cleanup, or history-rewriting operation. If explicit staging succeeds but a later
inspection or commit gate fails, the staged changes remain visible for manual
review; the tool never attempts a dangerous rollback. Both capabilities remain
mutating, confirmation-required, `executable=False`, and unavailable to natural
language, the planner, and autonomous Brain execution. The approval flag is a
trusted-caller gate, not an interactive confirmation UI.

## Phase 6 LLM-assisted repair proposal

Phase 6 adds the explicit Python API `propose_repair(...)`. It can return one
immutable `RepairProposal` describing an exact text patch, creation of one new
text file, or `no_fix`. A proposal is data only: this API never writes or patches
a file, runs a command, stages or commits changes, invokes the repair loop, or
dispatches any tool except the literal read-only `developer.read_file` ID.

The integration uses a dedicated llama.cpp repair request and the active local
model. It supplies a purpose-built developer-repair system prompt directly rather
than using `core.context.build_messages`. Exact memory, semantic memory, recent
conversation, last-topic state, and Marty's personal context are therefore not
loaded or sent to the repair model. Backend errors are suppressed at this boundary
and produce a stable safe failure without returning or logging raw exception text.

### Bounded untrusted context

The caller supplies a verification summary, failure output, at most five explicit
candidate paths, and optional excerpts. The limits are 4 KiB for the summary,
16 KiB for failure output, 8 KiB per excerpt, and 48 KiB for the combined repair
context. Candidate paths are at most 4,096 UTF-8 bytes. Oversized inputs are
rejected rather than silently truncated. If an excerpt is omitted for an existing
candidate, Phase 6 obtains bounded line-numbered context through
`developer.read_file` and the fixed executor; it does not call `open`,
`Path.read_text`, or a repository search. A file whose complete numbered content
fits the existing 8 KiB bound is labeled `complete_file`. A larger file uses a
bounded window around a candidate-specific `path:line` failure reference when one
is available, otherwise it uses a bounded prefix. Context records explicitly mark
their selection, completeness, and line-numbering status. Numbering expansion is
also bounded, so a large file produces useful context rather than rejecting the
whole proposal request.

Candidates must be canonical workspace-relative paths with an existing contained
parent. Absolute paths, traversal, duplicates, directories, unsafe symlinks,
`.git/`, `.env*`, key/certificate and credential/secret names, `testbrain.py`, and
the three protected audio tester files are refused before any model call. A new
path may be a write candidate, but an existing path is required for a patch.

Failure output, stack traces, filenames, source comments, and excerpts are marked
as untrusted JSON data in the prompt. The system contract tells the model that
embedded instructions cannot redefine the schema, permissions, output format, or
system behavior; it must not issue commands, claim execution, or reveal
chain-of-thought. It must choose `no_fix` when the evidence is insufficient. The
repair contract requires checking surrounding control flow, data flow, mutation
order, and original versus residual consumable state. When ordering matters, it
explicitly permits and prefers a larger exact block replacement over an ineffective
append or compensating threshold change. The reason remains a short observable
repair rationale, not hidden reasoning.

### Strict output and repair-data conversion

Model output is capped at 32 KiB and parsed only as one strict JSON object. Markdown
fences, surrounding prose, arrays, duplicate keys, unknown fields or proposal
types, missing fields, wrong types, non-finite/out-of-range confidence, NULs, and
oversized strings are rejected. Patch/write payload strings are capped at 16 KiB
and reasons at 1 KiB. There is no `eval`, `exec`, literal evaluation, YAML, fuzzy
matching, or regex patch parsing. One correction call is allowed only after JSON
or schema failure; an unsafe target, ambiguous patch, low confidence, or other
semantic rejection is never retried. Empty/unavailable model responses and
backend failures stop immediately. There are at most two model calls.

Phase 8C also constrains repair generation with one fixed internal GBNF grammar
that expresses exactly the existing patch, write, and no-fix JSON variants. The
active llama.cpp build advertises JSON Schema response formats, but its automatic
schema/chat-template integration could not initialize the sampler for the active
Qwen template. Direct grammar sampling is therefore used instead. The grammar is
not caller-selectable and permits ordinary escaped JSON string content while
fixing the object variants, keys, proposal-type literals, and confidence number
shape. It does not replace any parser, path, payload, confidence, snapshot, or
semantic validation below.

Repair inference disables Qwen thinking through the chat-template control and
uses a repair-only deterministic profile: temperature `0.0`, top-p `0.1`, top-k
`1`, repeat penalty `1.0`, seed `0`, prompt-cache reuse disabled, and at most 1,200
generated tokens. General Jarvis conversation inference is unchanged. The system
and correction prompts both require exactly one JSON object with no Markdown or
surrounding prose. The existing one-initial-plus-one-correction hard limit remains
unchanged.

Patch proposals require a protected-policy-safe existing text file, non-empty
`old_text`, a different bounded replacement, and exactly one literal match in a
complete bounded read of the current file. Write proposals are limited to bounded
UTF-8 content at a target that does not exist; overwrite and implicit parent
creation are not proposed. `no_fix` has no path or payload fields.

`MIN_REPAIR_PROPOSAL_CONFIDENCE` is `0.70`. This model-reported number is a
heuristic, not a calibrated probability. A structurally valid proposal below the
threshold remains `valid=True` but is not eligible for conversion.
`proposal_to_predefined_repair(...)` revalidates current path and payload state,
including a private validation seal and unchanged filesystem snapshot, without
calling the executor. It then returns immutable data compatible with the Phase 4
repair loop:
`developer.patch_file` arguments with one expected match, or
`developer.write_file` arguments with `overwrite=False` and
`create_parent_dirs=False`. It does not call the executor, mutate a file, or enter
the repair loop.

The seal is a module-local identity token and the snapshot retains only path and
filesystem stat metadata; neither contains source content or secrets. Together
they conservatively reject public caller-constructed proposals and target changes
between proposal validation and conversion. They are process-local integrity
checks, not cryptographic attestations, durable proofs, or a defense against
hostile code already executing inside the Jarvis Python process. The existing
repair-loop approval and mutation validation remain the final authority.

The immediate trusted caller may inspect a full proposal. Phase 6 does not write
the prompt, raw model output, failure text, source excerpt, or repair payload to
logs, Brain status, session history, exact/semantic memory, or other persistence.
Brain v2 advertises `developer.propose_repair` as enabled, read-only,
non-mutating, confirmation-free, and `executable=False`. There is no planner,
router, natural-language, Brain-autonomous, or automatic post-repair/checkpoint
entry point. Existing approval, mutation, verification, repair-loop, and Git gates
remain authoritative.

## Phase 7 bounded autonomous developer session

`run_bounded_developer_session(...)` is the first Developer Agent API permitted to
apply an LLM-generated repair. It runs this fixed sequence:

```text
verify -> diagnose -> propose -> validate -> apply -> reverify -> stop or repeat
```

The trusted human caller must pass `approved=True` for that one call. Approval is
ephemeral and delegates only the request's immutable scope: one typed verification
specification, at most five explicit candidate read paths, at most five explicit
mutation paths, and caller-selected limits no greater than the hard maxima. A
verification specification is either the existing fixed `run_command` argv tuple
or a `gradle_test` project root; it cannot contain both. Existing
`verification_argv` callers are adapted to the `run_command` specification. With
approval missing, the session performs no verification, model call, source read,
mutation, or Git operation. Approval is neither global nor persisted.

The hard maxima are two repairs, three verification runs (the initial run plus two
reverification runs), and two Phase 6 proposal requests. Each proposal request
retains Phase 6's existing maximum of one schema-format retry, so the theoretical
session maximum is four local-model calls. A caller may lower these limits but
cannot raise them.

### Static scope, dynamic repairs

The verification kind and its kind-specific arguments, candidate read set,
mutation allowlist, and limits are validated and frozen before the first command
runs. Scope paths must be unique, canonical repository-relative file paths with
contained existing parents. The session rejects `.`, absolute paths, traversal,
wildcards and pathspec-like input, Git metadata, sensitive names, protected
personal files, directories, and unsafe symlinks. The model cannot browse, search,
add candidates, select a new verification kind, change a Gradle task or project,
or expand the mutation allowlist.

Repair payloads are dynamic: after each failed reverification, Phase 7 asks Phase 6
for a fresh proposal using the current source state and new diagnostic. A readable
candidate is not automatically writable. The exact proposed path must also be in
the frozen mutation allowlist. New-file creation works only when that exact future
path is both a candidate and pre-authorized mutation path.

Phase 4 and Phase 7 therefore have distinct roles:

- Phase 4 runs a caller-supplied sequence of predefined repairs.
- Phase 7 generates a new repair after each failure, but only within a statically
  approved session scope.

Phase 6 remains authoritative for prompt isolation, strict JSON/schema handling,
confidence threshold, protected-path and exact-patch validation, bounded format
retry, and filesystem snapshot/seal revalidation. Phase 7 converts eligible
proposals only through `proposal_to_predefined_repair(...)`. Verification is
dispatched through the frozen specification as either `developer.run_command` or
`developer.gradle_test`; mutation is always dispatched as the converted
`developer.patch_file` or `developer.write_file` operation through the existing
fixed executor. The session module has no subprocess or direct file-write
implementation.

### Diagnostics, stopping, and results

Failed command output is adapted into an ephemeral `DiagnosticExcerpt`. Output at
or below 16 KiB is retained as captured. Larger output uses deterministic bounded
head and tail portions with explicit truncation metadata, preserves valid UTF-8,
and never exceeds Phase 6's 16 KiB failure-output boundary. Upstream command-output
truncation is also recorded in the proposal summary. Diagnostics, prompts, source
excerpts, raw model output, reasons, patch bodies, and created-file contents are
not copied into the session result or any memory, Brain status, conversation, log,
or history facility.

The session stops immediately when verification passes or on a timeout, command
policy rejection, executor failure, backend/model failure, malformed or `no_fix`
proposal, low confidence, unsafe or out-of-scope path, stale snapshot, conversion
failure, mutation rejection/failure, or any repair, verification, or proposal
limit. Results contain only safe immutable counters, per-attempt status/type/path/
confidence metadata, the authorized paths successfully changed, and a stop reason.

There is intentionally no automatic rollback. If an authorized repair is applied
and a later verification fails or times out, that modification remains in the
working tree for human inspection and manual recovery. Phase 7 never calls delete,
reset, restore, checkout, staging, commit, or push. A green session stops without
Git mutation; any Phase 5 checkpoint is a separate, later human-directed action.

Brain v2 advertises `developer.bounded_session` as enabled, mutating,
`requires_confirmation=True`, and `executable=False`. The Phase 7 Python API
remains canonical. Brain Phase 3 adds only a deterministic natural-language
proposal and explicit-approval entry point with frozen scope; there is still no
generic executor registration, planner mapping, unrestricted router entry point,
background task, recurring execution, or recursive session.

## Phase 8B dedicated Android/Gradle verification

### `developer.gradle_test`

Phase 8B adds a confirmation-required verification tool for reviewed Android
projects. Its only task is `:app:testDebugUnitTest`; callers cannot supply a task,
Gradle flag, wrapper path, command argv, environment, init script, system property,
or shell fragment. The fixed process argv is equivalent to:

```text
./gradlew --offline --no-daemon --console=plain :app:testDebugUnitTest
```

The wrapper is executed with `shell=False`, no stdin, a fixed project working
directory, a 300-second maximum timeout, process-session isolation, terminate/kill
handling, and independent bounded stdout/stderr draining. Combined captured output
defaults to 256 KiB and cannot exceed 1 MiB. Results retain safe exit, timeout,
byte-count, truncation, Gradle-version, fixed-task, and command-family metadata.

### Project, wrapper, SDK, and cache policy

The caller supplies only a project root contained by the explicit `Workspace`.
The root must be an existing canonical directory with no traversal or symlinked
path component. The tool does not search parents. `gradlew`,
`gradle/wrapper/gradle-wrapper.jar`, and
`gradle/wrapper/gradle-wrapper.properties` must be regular non-symlink files, and
`gradlew` must be executable.

Phase 8B supports only Gradle 9.5.0. The generated POSIX wrapper script and wrapper
JAR are SHA-256 allowlisted. Wrapper properties must exactly match the reviewed
Gradle 9.5.0 configuration: the HTTPS services.gradle.org binary-distribution URL,
the recorded distribution SHA-256
`553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746`,
standard `GRADLE_USER_HOME` paths, URL validation, and fixed retry/timeout values.
Unknown properties, missing or malformed hashes, another version, another URL,
and hash mismatches are refused. The matching extracted distribution and `.ok`
marker must already exist in the trusted local cache, and its distribution-level
`init.d` directory may contain only the known Gradle readme. The wrapper is never
used to select or intentionally download another version.

The Android SDK is fixed trusted local configuration at
`/home/mnahtygal/Android/Sdk`; its canonical directory and platform 37 JAR must
already exist. The tool never installs an SDK component. `ANDROID_HOME` and
`ANDROID_SDK_ROOT` are set to that validated path instead of inheriting caller
values. Thor's reviewed ARM-compatible AAPT2 launcher, QEMU entry point, and
x86-64 AAPT2 binary are also fixed-path and SHA-256 validated before the tool
writes the corresponding `android.aapt2FromMavenOverride` into its temporary
Gradle user-home properties. No caller can select that executable or property.

The process receives a new temporary `HOME` and `GRADLE_USER_HOME` containing no
user init scripts. Only the trusted real user's `caches`, `wrapper`, and `jdks`
directories are linked into that controlled home so existing offline dependencies,
the reviewed distribution, and local Java toolchains remain usable. A generated
Gradle-user-home property disables Java toolchain auto-download. Project-local
`init.gradle`, `init.gradle.kts`, and `init.d` are refused, as are dangerous
project `gradle.properties` Java, JVM, system-property, and Gradle-project injection
keys. Ambient `JAVA_HOME`, `JAVA_TOOL_OPTIONS`, `GRADLE_OPTS`,
`ORG_GRADLE_PROJECT_*`, proxy credentials, and arbitrary environment values are
not inherited. `--offline` makes missing plugin or dependency artifacts a safe
`offline_cache_miss` infrastructure failure; it is never relaxed to allow network
fallback.

`VerificationEvidence` accepts a successful, non-timeout, zero-exit
`developer.gradle_test` result only when its command family is exactly
`gradle_test`. Existing `pytest`, `compileall`, and `py_compile` evidence remains
unchanged. Phase 7 freezes either verification kind and its parameters before the
first attempt and dispatches the identical specification on every reverification.
The repair model cannot change the kind, root, task, flags, or environment.

### Trust boundary

Gradle necessarily executes the approved project's settings and build scripts,
the allowlisted wrapper, cached Gradle distribution, and resolved plugins. This
capability is not an OS sandbox and does not make an untrusted Android repository
safe. An approved project can create normal build outputs and trusted build logic
can perform actions beyond compilation. The boundary restricts the selected
wrapper, project root, task, flags, offline mode, environment, init-script sources,
timeout, and captured output; it assumes those reviewed project files, cached
plugins, toolchains, SDK, and real-user Gradle cache are trusted.

The capability is `enabled=True`, `read_only=True`, `mutating=False`,
`requires_confirmation=True`, and `executable=False`. “Read-only” describes its
source intent; Gradle may create `.gradle/` and `build/` artifacts. It has no
planner mapping, natural-language or router trigger, Brain invocation, package
installation, network enablement, or Git operation. `developer.run_command`
remains unchanged and still rejects `./gradlew`.

## Phase 8C repair-model structured-output reliability

The Phase 8 rerun reached real verification and live llama.cpp inference but ended
with `AGENT_REASONING_FAILURE`. Both repair responses exhausted the 1,200-token
limit inside an unclosed `<think>` block, so neither response began with JSON. The
strict parser correctly rejected both at byte one and Phase 7 applied no mutation.
This historical benchmark classification remains unchanged.

Phase 8C remediates the generation path rather than accepting malformed output.
The exact three-variant JSON Schema remains represented for review, while the
active server uses the equivalent fixed internal GBNF grammar described above.
The strict JSON parser is unchanged: it still rejects Markdown fences, surrounding
prose, duplicate or unknown fields, non-object JSON, invalid confidence, and every
other prior format violation. Semantic and filesystem validation remains the
authoritative safety boundary after constrained generation.

The manual reliability runner
`tools/run_developer_repair_model_reliability.py` makes five proposal-only calls
against a temporary deterministic fixture. It records only parse/schema success,
proposal type, confidence, validation status, and whether the fixture remained
unchanged. It never converts or applies a proposal and never stores raw output.

## Phase 8D semantic repair quality hardening

The post-Phase-8C Farkle rerun proved that the bounded mechanics worked: real
Gradle verification ran, live llama.cpp returned two accepted structured patches,
Jarvis applied both within scope, and the unchanged repair limit stopped the
session. It ended in `PARTIAL_SUCCESS` because the resulting special-case check
was placed after generic triple processing had already consumed the original count.

A prompt audit showed that this was not missing Farkle source context. The model
received the complete 23-line scorer, complete 45-line test, visible count mutation,
failing test name, and ordered candidate list in a combined 6,786-byte system/user
prompt. The observable failure is therefore primarily semantic control/data-flow
reasoning, with a contributing prompt weakness: the previous contract did not
require validating state at the proposed insertion point or explicitly encourage
replacing a larger exact block.

Phase 8D improves bounded context representation and the semantic repair contract.
Small files are sent as explicitly complete numbered files; large files use a
bounded failure-line window or bounded-prefix fallback. The prompt requires a
repair to account for earlier state mutation, distinguish original from residual
consumable state, and use a larger exact block when execution order must change.
It also requires preserving existing behavior not contradicted by failure evidence
and keeping the replacement block no broader than necessary. It does not request
or persist chain-of-thought.

Model-independent fixtures cover a generic function where state is consumed before
a later condition, complete small-file and test context, bounded large-file
fallback, failure-line selection, and validation of a larger exact-block proposal
without applying it. Proposal-only live checks remain mixed: the generic fixture
produced a semantically promising pre-mutation insertion but reported confidence
`0.0`, so the unchanged confidence gate kept it ineligible. The Farkle proposal was
valid and accepted at confidence `0.8`, but trusted inspection found that it still
appended the four-of-a-kind check after generic triple consumption. It was not
converted or applied. Phase 8D therefore improves the generic input contract but
does not claim that the active model has solved the benchmark's semantic reasoning
gap.

The 8 KiB per-file context bound, 16 KiB repair payload bound, 48 KiB total context
bound, fixed GBNF grammar, thinking control, deterministic sampling, strict parser,
`0.70` confidence threshold, one correction retry, exact one-match validation,
snapshot/seal checks, candidate and mutation scopes, and Phase 7 limits are
unchanged. No critique pass, judge model, reflection loop, extra runtime model call,
command capability, Git behavior, planner/router entry point, or autonomy expansion
is added.

## Greenfield project orchestration

`developer.greenfield_project` coordinates existing controlled primitives for
one brand-new small Python project. It is not part of the generic executor and
cannot be selected by the planner. Brain deterministically freezes the canonical
workspace, exact flat filenames, source/test roles, requirements, pytest target,
parent inode, and hard limits in a sealed proposal. Confirmation returns without
calling a model. Only after exact approval is the local model asked for strict
JSON file content. The model cannot select paths, commands, dependencies, or
additional files.

The only permitted parent is `/home/mnahtygal/projects`. The parent must already
exist, resolve to itself, and not be a symlink; the direct child project must not
exist. Approval rechecks those properties and the sealed proposal, then builds
and validates a content-inclusive immutable manifest before creating one
directory. Directory creation does not accept
`parents=True`, arbitrary absolute targets, traversal, expansion syntax, or
overwrite. Each file is then created through the existing
`developer.write_file` implementation with overwrite and parent creation both
disabled.

Hard bounds are five files total, three source files, two test files, 8 KiB per
file, and 24 KiB total generated content. Initial bootstrap may create both
source and test files. After bootstrap, tests remain readable but are excluded
from `allowed_mutation_paths`; repair proposals targeting them are rejected.
Generated Python is syntax-checked and limited to standard-library, pytest, and
approved project-module imports, with process, network, installer, dynamic-code,
and destructive-call primitives blocked before filesystem mutation.
This AST gate is defense-in-depth input screening, not an operating-system
sandbox. Ordinary JSON and workspace file persistence remain available, and the
existing pytest execution limitations below still apply.

Verification and repair reuse the existing Phase 7 session unchanged. The frozen
command is `pytest -q` followed by the exact test filenames. Verification runs
first and stops immediately when green. If red, the existing limits remain two
repairs, three verification runs total, and two proposal requests. No command
change, test rewrite, extra file, nested session, package installer, network
operation, or Git operation is permitted. Pytest may create ordinary
`.pytest_cache` artifacts; those are verifier artifacts, not manifest files or
repair scope.

If directory or file creation fails partway through, the result reports the
created filenames and leaves them visible. There is no automatic deletion or
rollback. Generated source, tests, raw prompts, model output, manifests, and
diagnostics remain process-local and are not written to Brain status or durable
memory.

## Execution limitations

Phase 2 can create or replace text only through the two explicit mutation tools.
Phase 3 commands can run tests and bytecode compilation, which may create ordinary
workspace artifacts such as `__pycache__` and `.pytest_cache`; this is why the
generic command capability remains classified as sensitive and mutating even
though its Git subset is read-only. It cannot delete files or directories, change
permissions, install packages, stage, commit, or push. The executor allows only
fixed registered IDs and arguments. Phase 4 adds only the bounded, predefined
sequence described above; it does not provide generated self-correction, planning,
or natural-language invocation. Phase 5 adds only the two dedicated local Git
checkpoint tools; the generic command tool still cannot stage, commit, or push.
Phase 6 only proposes and converts repair data; it cannot apply that data. Phase 7
can apply converted data only within the explicit static session boundary described
above and stops before any Git checkpoint operation. Phase 8B adds only the fixed
Gradle verification path described above; it does not add generic project-local
executable access. Phase 8C changes only repair-model generation format and does
not add execution, mutation, Git, planner, router, or Brain entry points. Phase 8D
changes only bounded repair context and semantic instructions; it adds no execution
or autonomy surface.

This command policy is a constrained developer workflow boundary, not an operating
system sandbox. An approved pytest command necessarily imports and executes the
selected workspace tests and local `conftest.py` files. The policy prevents using
the command API to select arbitrary interpreters, modules, plugins, executables,
working directories, or environments; it does not make repository test code
non-executable. Explicit confirmation and trusted workspace contents are therefore
required before a caller invokes pytest.

Allowed examples:

```python
execute_tool("developer.list_files", {"path": "core", "recursive": False})
execute_tool("developer.read_file", {"path": "README.md", "start_line": 1, "end_line": 20})
execute_tool("developer.git_status", {})
execute_tool("developer.write_file", {"path": "notes/todo.md", "content": "TODO\n", "create_parent_dirs": True})
execute_tool("developer.patch_file", {"path": "notes/todo.md", "old_text": "TODO", "new_text": "DONE"})
execute_tool("developer.run_command", {"argv": ["python", "-m", "pytest", "-q", "tests/test_developer_agent.py"]})
```

Rejected examples include `../` or symlink escapes, `/etc/passwd`, `.env`, binary
files, protected audio tester files, Git metadata, unknown tool IDs, unsupported
arguments, shell command strings, `python -c`, arbitrary Python modules, absolute
executable paths, pytest plugin injection, and Git mutation commands.

## Roadmap

- Phase 1: bounded read-only repository inspection
- Phase 2: confirmation-sensitive file mutation tools
- Phase 3: constrained verification command execution
- Phase 4: bounded verify/repair/reverify loop using predefined repairs
- Phase 5: controlled explicit staging and verification-gated local commit
- Phase 6: bounded LLM-assisted repair proposals (data only)
- Phase 7: bounded autonomous developer session (explicit manual approval and
  static scope)
- Phase 8A: deterministic Farkle-2 Android benchmark fixture
- Phase 8B: narrow offline Android/Gradle verification capability
- Phase 8 rerun: one human-controlled Farkle-2 four-of-a-kind repair benchmark
- Phase 8C: repair-model structured-output reliability hardening
- Phase 8D: semantic repair quality hardening

No broader phase is defined here.
