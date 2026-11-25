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

### Project-note approval engine

`core/memory_approval.py` supplies a standalone, in-memory engine for
`project_note` proposals in the `project` category. The default capacity is
64 pending proposals per engine, with one per interaction and a 1,000-character
candidate limit. A second candidate for a live interaction is rejected so the
user can finish reviewing the original. Proposals expire after 120 seconds on
a monotonic clock. Creation sweeps expired entries, and the owner can call
`cleanup_expired()` during idle periods. There is no terminal history.

A future trusted local adapter should own one engine for the interaction
lifecycle. It should derive an opaque interaction ID and
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

A future trusted local adapter can bind `ApprovedMemoryPersistence` to that
engine and pass the explicit user turn to `approve_and_persist()`. This
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

Conversation routing still uses the existing capture paths. The persistence
adapter is available through the dedicated terminal console.

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
approval boundary.

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
