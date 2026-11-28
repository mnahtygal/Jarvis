# Jarvis Architecture

Last updated: 2026-11-25

Jarvis is a local-first AI engineering assistant running primarily on NVIDIA
Jetson AGX Thor. The current architecture combines Brain v2 orchestration,
local llama.cpp models, PostgreSQL memory, voice/vision/workshop skills, and a
controlled Developer Agent.

## High-Level Runtime

```text
User / UI / CLI
       |
       v
   Flask API :5000
       |
       v
core/orchestrator.py  (Brain v2)
       |
       +--> deterministic request classification
       |
       +--> ordinary conversation/status/memory/vision
       |       -> legacy router / skills / memory / local models
       |
       +--> developer request
               -> core/developer_bridge.py
               -> fixed capability grammar
               -> confirmation gate where required
               -> core/developer_agent/*
```

Supporting services:

| Service | Address |
| --- | --- |
| React/Vite UI | `http://localhost:5173` |
| Flask API | `http://127.0.0.1:5000` |
| Qwen text model | `http://127.0.0.1:8080` |
| Gemma vision model | `http://127.0.0.1:8081` |
| PostgreSQL + pgvector | local |

## Brain v2

`core/orchestrator.py` is the current top-level decision layer. It:

1. classifies the request deterministically
2. chooses context policy
3. evaluates plan/strategy metadata
4. sends recognized Developer Agent requests through the developer bridge
5. sends non-developer requests to the ordinary Jarvis router
6. records safe lifecycle/status metadata

The bridge never accepts an LLM-selected arbitrary tool name or arbitrary argument
dictionary. Recognition is intentionally narrow.

## Developer Agent

The Developer Agent is implemented under `core/developer_agent/`.

Important modules:

- `developer_session.py` — bounded repair session orchestration
- `repair_proposal.py` — strict local-model repair proposal generation
- `candidate_verification.py` — disposable candidate verification and exact
  passing-byte sealing
- `command_policy.py` — approved command grammar
- `executor.py` / `registry.py` — fixed tool dispatch and metadata
- `mutation.py` — atomic bounded file mutation
- `git_safety.py` — constrained local Git checkpoint operations

### Bounded Python repair flow

```text
canonical request
  -> confirmation_required
  -> exact approve
  -> freeze workspace/source/test/verification scope
  -> verify disposable baseline candidate
  -> if red: request bounded local-model repair proposal
  -> apply proposal to new disposable candidate
  -> verify candidate inside isolated sandbox
  -> if green: seal exact candidate bytes
  -> revalidate original identities
  -> atomically promote exact sealed bytes
  -> stop; no automatic Git
```

Current hard ceilings are two repairs, three verification runs, and two proposal
requests.

## Thor Candidate Isolation

Normal Thor startup prefers:

```text
/usr/libexec/jarvis-api-entry
```

The AppArmor transition chain is:

```text
jarvis-api-entry
  -> jarvis-api-entry//candidate_userns
  -> jarvis-api-entry//candidate_userns//candidate_runtime
```

The candidate launcher is the root-owned:

```text
/usr/libexec/jarvis-candidate-sandbox
```

Isolation setup uses fixed `/usr/bin/unshare` and `/usr/bin/bwrap`. User
namespace creation is allowed only in the narrow setup child; the API and runtime
domains deny additional user namespace creation and profile changes.

Bubblewrap supplies the candidate filesystem/process boundary. The candidate tree
is mounted read-only, temporary locations are private, the host home/project tree
is absent unless explicitly part of the fixed manifest, and networking is
disconnected by the network namespace.

The reviewed sources, build, policy, installation, and rollback notes live under
`packaging/apparmor/`.

## Frontend

The frontend lives under `ui-app/src/` and keeps page, component, hook, service,
config, and shared type layers separate. Mission Control is read-only. Vision Lab
owns workshop camera, Scan Mat, calibration, measurement, and image-analysis
workflows.

## Memory

Jarvis uses PostgreSQL for exact/persistent facts and PostgreSQL + pgvector for
semantic memory. The core runtime remains local-first; do not replace the storage
architecture casually with a cloud vector store.

Brain v2 records request-scoped semantic retrieval diagnostics in internal result
metadata. A `ContextVar` isolates concurrent requests and is reset on every exit
path. Each completed or failed retrieval attempt replaces the previous snapshot
within the same request. The snapshot includes the outcome, counts, and the
threshold used for that attempt (normally `0.50`). The selected IDs, weighted
scores, and category labels share the same order. Invalid IDs and non-finite
scores use null placeholders, and unrecognized category labels use `unknown`.
The snapshot carries no memory contents, prompts, credentials, conversation
history, or embeddings. It stays in internal result metadata. Public Brain and
dashboard status, Flask and handheld chat responses, and application logs exclude it.

### Controlled project-note capture

Brain v2 still classifies durable-looking project ideas as `project_note`
candidates, and semantic retrieval remains available under the request's context
policy. Ordinary conversation no longer performs the former automatic duplicate
lookup or semantic-memory insert. There is no confidence threshold, model output,
HTTP field or header, localhost origin, or caller-supplied interaction identifier
that can re-enable that retired path.

A detected candidate on an ordinary request evaluated as successful and good
produces `approval_required`, with target `none` and `memory_persisted=false`.
The status records the decision. `approval_kind` remains `none` and
`approval_pending` remains false. The request creates no proposal or approval
ID. Public Brain v2 status may show the status and memory type.
Developer Agent requests and unsuccessful or lower-quality evaluations retain
`skipped`, along with declined capture candidates. Successful, good requests
outside the supported capture types report `not_applicable`.

### Controlled exact-memory and preference capture

Ordinary statements about personal facts, workplaces, likes, and preferences
previously called `remember()` and could upsert an exact-memory row and append
to `memory_history`. Those statements now follow ordinary routing with the
existing recall paths available. The classifier still observes `exact_fact`
and `preference` candidates, which share the capture statuses above. Candidate
recognition and confidence provide no write authority. Existing saved facts
remain available to recall, including through legacy key normalization.

Successful LLM replies for detected exact facts and preferences with
`approval_required` include a separate, application-generated note stating that
the turn did not save or update long-term memory. The reply text stays intact,
including negations, quotes, and explanations. The application evaluates the
reply before appending the note. This clarification depends on heuristic
candidate classification, so some ordinary statements receive no note.
The model can still produce misleading wording. The note reports the actual
result for the turn and applies equally to replies without a save claim.

Future exact-memory approval needs a trusted review surface that shows the
normalized key, proposed value, and any existing value before an operator
authorizes an overwrite. The local memory console and approved persistence
adapter support project notes only. Conversation history still records ordinary
user and assistant turns, and the existing heard-command log can contain the
original input. Capture status applies to durable memory writes separately from
conversation retention.

### Explicit memory command authorization

Chat and voice cannot directly insert, overwrite, update, or delete durable
exact or semantic memories. Leading whole-word `remember` (including
`remember this` and `remember that`), `note` (including `note that`),
`save` (including `save this`), `update my`, and `forget that` forms
receive a fixed authorization response. Incomplete forms receive the same
response. Leading command-like prose can also match this syntax.

Leading memory commands take precedence over Developer Agent heuristics.
The router handles them before keyword-based recall and other narrow shortcuts,
so terms such as `database`, `wife`, `workplace`, and `ship` leave the
authorization response in place. The existing multiline and
large-request fallback runs first. Model responses from that path have no
mutation authority. HTTP metadata, origin, prior turns, and Developer Agent
approvals cannot authorize a memory change.

A blocked command uses route `memory_authorization_required` and decision
`explicit_memory_command` with `should_store=false`, including deletion
requests. `approval_required` describes the boundary. The result reports
`memory_persisted=false`, target `none`, no pending approval, and no action ID.
The status contains no candidate text. The existing HTTP `heard` field, input
logs, conversation history, and session state keep their existing behavior.

Conversational save, update, and forget are unavailable until an authorized
workflow exists. The trusted local console can approve new project notes
only. The router has no durable-memory mutation calls. Trusted in-process
Python callers, standalone administrative or migration utilities, and direct
database access are outside this application boundary. The underlying SQL and
database privileges retain their existing behavior.

### Project-note approval engine

`core/memory_approval.py` supplies a standalone, in-memory engine for
`project_note` proposals in the `project` category. The default capacity is
64 pending proposals per engine, with one per interaction and a 1,000-character
candidate limit. A second candidate for a live interaction is rejected so the
user can finish reviewing the original. Proposals expire after 120 seconds on
a monotonic clock. Creation sweeps expired entries, and the owner can call
`cleanup_expired()` during idle periods. There is no terminal history.

The trusted local console owns one engine for its interaction lifecycle. Any
future authenticated adapter must likewise derive an opaque interaction ID and
`InteractionSource.TRUSTED_LOCAL_USER` from its trusted user-turn boundary.
Those values must come from the adapter, never from a prompt, raw client fields,
or model output. Call `propose()` with the candidate and present its exact text
and proposal ID through the local review surface. Forward only an explicit user
turn of the form `approve memory <proposal_id>` or
`cancel memory <proposal_id>` to the corresponding method with the same
interaction ID. The engine's standalone `approve()` returns an approved
proposal for inspection. For storage, use the combined operation below.
Expired requests return `expired` while the entry is
still present and `no_matching_proposal` after cleanup.

Keep the review text out of transcript logging and public status. The
credential and retention checks cover obvious patterns and are heuristic.
State is local to one engine instance and is lost on process restart. The
engine itself has no conversation, Developer Agent, API, or database integration.

### Approved project-note persistence

The trusted local console binds `ApprovedMemoryPersistence` to that engine and
passes the explicit user turn to `approve_and_persist()`. This
operation consumes the matching live proposal itself. The interface accepts
confirmation text and the adapter's trusted interaction context. Proposal
objects, including previously approved ones, carry no storage authority.

After approval, the adapter checks the top three semantic results with the
existing project-note duplicate rule. The separate lookup and insert permit
races between different proposals or writers. A lookup failure stops storage.
The writer stores the exact reviewed text as a `project_note` in the `project`
category with fixed provenance metadata. The outcome contains only a status
and a commit-uncertainty flag. Success requires a positive integer row ID. A
writer exception or invalid result can leave commit state uncertain. Each
approval permits one attempt, with no retry after any outcome.

Ordinary conversation never calls this adapter and never creates its proposals.
The persistence adapter is available through the dedicated terminal console.

### Trusted local memory console

From the repository root, launch the console with
`.venv/bin/python -m tools.local_memory_console`. This defaults to **DRY RUN**.
Add `--persist` to enable actual semantic storage. Both input and output must
be interactive terminals. The console hides typed input and does not keep a
transcript or history. The terminal emulator and local session may still record
review output.

Type `propose memory Build a calibration fixture`. The console shows the exact
single-line candidate, proposal ID, category, and 120-second expiration.
Only the first space after `propose memory` separates the command from the
candidate. Further spaces belong to the candidate, including trailing spaces.
Long reviews are split into delimited lines. Tabs, control characters, and
Unicode format and line separators are rejected. Type
`approve memory <proposal_id>` or `cancel memory <proposal_id>`. In dry run,
approval consumes the proposal without contacting storage. `help`, `status`,
and `exit` are also available. Status shows the mode and pending proposal ID.
The console discards pending state when the session ends.

The console generates its interaction ID and owns the approval engine. TTY
presence is not proof of physical presence or authenticated human identity.
SSH sessions, PTY automation, shared terminals, and terminal recording are
outside this trust boundary. The console assumes a trusted local operator and
a terminal of stable width during review. Duplicate detection and uncertainty
handling retain the adapter's limits above.

A future dashboard integration needs its own authenticated, interaction-bound
proposal review and explicit confirmation, plus CSRF defenses and sanitized
status and logs. It must keep model output and handheld turns outside the
approval boundary. No new endpoint or authorization channel is implied by the
ordinary conversation status.

Candidate detection and credential/retention checks are heuristic. Public
status excludes candidate text. Ordinary conversation history and the existing
heard-command log can retain the original turn. Terminal emulators or local
sessions can record console review output. Pending proposals are process-local
and disappear on restart. Duplicate
lookup and insert are not atomic, and a writer failure can have an uncertain
commit outcome.

### Structured exact-memory approval proposals

`core/exact_memory_approval.py` provides a standalone in-process engine.
A frozen, slotted proposal carries a UUID4 hex ID, trusted interaction ID,
operation, normalized key, optional reviewed record, optional proposed value,
monotonic creation and expiry times, and status. A reviewed record is a frozen,
slotted snapshot with a positive integer row ID, the exact normalized key,
the stored text value, and nullable `datetime` timestamps. Timestamps can be
naive or use an immutable standard timezone. An empty stored value still
represents an existing row.

The engine accepts actual `ExactMemoryOperation` enum members:

- `CREATE` requires an absent key and a nonblank value.
- `UPDATE` requires an existing row and a nonblank value that differs from
  the reviewed value by exact string comparison.
- `DELETE` requires an existing row and a proposed value of `None`.

Keys use only `memory_key.strip().lower()`, with a 256-character cap before
and after normalization. Punctuation and internal spacing remain intact.
Proposed values retain their exact spelling and spacing, up to 1,000
characters. The engine rejects controls, format characters, surrogates, and
Unicode line and paragraph separators. It applies the project-note credential
and retention opt-out patterns to keys, values, and joined fields. Screening
is heuristic. A malformed, unsafe, sensitive, or oversized existing record
cannot be reviewed or approved here, even for deletion. An authorized
administrative process must handle such records separately.

A trusted caller supplies the lookup `(normalized_key) -> ExactMemoryRecordSnapshot | None`.
`None` means absent. The engine validates inputs before lookup, checks returned
keys for exact equality, and rejects lookup failures with fixed error codes.
It runs the lookup outside its state lock and has no production lookup adapter
or database dependency. Generic representations omit keys, values, snapshots,
and interaction IDs. Trusted reviewers still need to handle these fields as
sensitive data when rendering or serializing them.

The trusted composition layer must supply the exact
`InteractionSource.TRUSTED_LOCAL_USER` enum member and derive its own
interaction ID (up to 128 characters). The enum is an in-process contract
and carries no authentication by itself. There is currently no exact-memory console, API, chat,
voice, handheld, LooLoo, or dashboard integration. Project-note approvals use
a separate engine and adapter and cannot be exchanged with exact-memory
approvals.

Each engine defaults to 64 slots across published proposals and in-flight
lookups, with one slot per interaction. The engine reserves a slot before
lookup, releases it on failure, and starts the 120-second TTL on publication
of the validated review. A hung lookup can occupy its slot until it returns
or is interrupted. A future lookup adapter must bound its own execution time.
The clock dependency must be a prompt monotonic source. Approval and
cancellation require a full match of `approve exact memory <id>` or
`cancel exact memory <id>`, using the same interaction and a lowercase
32-digit hex ID. A matching proposal is consumed once, expires at the exact
deadline, and leaves no terminal history. Expiration is cleaned lazily and
through `cleanup_expired()`.

Approval returns review data and performs no durable write. An approved
proposal object alone carries no write authority. The snapshot can become
stale at any time. A future persistence adapter must consume genuine approval
directly from its trusted engine and use transactional compare-and-swap or an
equivalent stale-record check. It must handle create-only conflicts, verify
the existing row identity and reviewed value, and record accurate
`memory_history` atomically with the mutation. It must also distinguish
failure from uncertain commit outcomes and avoid automatic retries of consumed
approvals.

### PostgreSQL protection in tests

Run automated tests from the repository root with
`.venv/bin/python -m pytest tests/…`. The repository's pytest configuration
loads the PostgreSQL guard before conftest and test-module imports. It blocks
psycopg2 connection entry points for the life of the pytest process. Fixture
mocks can substitute fake connections and restore the guard when they unwind.
The terminal summary counts blocked calls during startup/session, collection
(including test imports), fixture setup, test execution, and teardown. Counts
are process-local and reflect the active pytest phase at the time of each call.

This is Python-level protection. A reference to the original native connector
captured before plugin load can bypass it. Code run before plugin load, other
database clients, fresh subprocesses, standalone scripts, and invocations that
bypass the pytest configuration require separate protection. Default discovery
uses `tests/` and ignores the root-level live PostgreSQL smoke scripts.

## Vision / Camera Roles

Camera use is role-based rather than tied permanently to `/dev/video*` numbers.

- `workbench` — Logitech C920
- `face` — Insta360 Link

The Samson Q2U is the preferred voice microphone when available.

## Startup

`scripts/start-jarvis.sh`:

- preserves already healthy model servers
- starts the API through the installed native entrypoint when present
- otherwise falls back to the repository Python entry for non-hardened/dev hosts
- requires API health before reporting success
- starts/verifies the Vite UI

On Thor, normal operation should use the installed native API entrypoint so
Developer Agent isolation receives the intended AppArmor profile.

## Security Principle

Jarvis does not equate "agentic" with unrestricted execution. Sensitive behavior
is bounded by explicit capabilities, fixed grammars, separate approval, static
scope, verification ceilings, and fail-closed isolation.

The successful 2026-10-19 repair benchmark validates this architecture on Thor;
it does not authorize broader autonomy.
