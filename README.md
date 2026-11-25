# Jarvis

Jarvis is a local-first AI engineering assistant running on NVIDIA Jetson AGX
Thor. It combines local language and vision models, voice, persistent memory,
camera/workshop workflows, and a controlled Developer Agent without requiring
cloud inference for normal operation.

Last updated: 2026-11-25

## Current Status

Jarvis has three active development tracks:

- **Brain v2 & Memory** — deterministic routing, request-local memory retrieval
  diagnostics, explicit project-note approval, authorized semantic storage, and
  a dedicated local memory console. The complete console-to-recall lifecycle
  was validated on Thor on November 25.
- **Maker & Workshop Assistant** — Vision Lab, Scan Mat, calibration, measurement,
  and workshop tooling remain active Phase 2 work.
- **Developer Agent** — bounded Python repair sessions now work end-to-end on
  Thor with candidate isolation, explicit approval, verification limits, and
  exact passing-byte promotion.

The 2026-10-19 repair benchmark is the current Developer Agent milestone:
Jarvis repaired an existing failing Python project, verified the candidate inside
the hardened sandbox, promoted only the passing source, and independently finished
with all 6 project tests passing.

## Latest Milestones — November 22–25, 2026

| Milestone | Commit | Validation / status |
| --- | --- | --- |
| Mixed-intent routing and secure API integration | `808a714` | Deployed; text, vision and authenticated handheld API checks passed November 23 |
| Memory retrieval observability | `9962bcc` | Merged and deployed |
| Memory approval engine | `8bb9243` | Merged; independently tested |
| Approved memory persistence | `27fab2a` | Merged; live console storage verified |
| Trusted local memory console | `998d0c8` | Merged; dry-run and real persistence verified |
| November 25 development checkpoint | `0d1e128` | Documentation committed |

The November 25 session delivered four features, 89 new regression tests,
1,875 insertions and 27 deletions, excluding the final checkpoint document.
The latest expanded regression suite passed all 292 tests with PostgreSQL
connections blocked and zero attempts recorded. The independent targeted
console suite passed 70 tests. A separate, explicitly approved live database
test confirmed storage, replay rejection and natural-language recall.

## Runtime Architecture

| Service | Implementation | Address |
| --- | --- | --- |
| UI | React/Vite | `http://localhost:5173` |
| API | Flask through the hardened native entrypoint when installed | `http://127.0.0.1:5000` |
| Text model | Qwen3 30B via llama.cpp | `http://127.0.0.1:8080` |
| Vision model | Gemma 3 4B Vision via llama.cpp | `http://127.0.0.1:8081` |
| Memory | PostgreSQL + pgvector | local database |

On Thor, `scripts/start-jarvis.sh` prefers the root-owned
`/usr/libexec/jarvis-api-entry`. That entrypoint attaches the API to the reviewed
AppArmor policy used by Developer Agent candidate verification. Do not bypass it
for normal operation.

The November 23 production deployment configured `jarvis-api.service` to use
the installed secure launcher, retaining handheld authentication through the
sanitized API environment. AppArmor enforcement and loopback model services
were verified. Nginx provides TLS proxying for selected health and handheld
routes; the Tailscale-specific site has a destination-address check, but the
entire server is not necessarily tailnet-only. The Vite development UI is
not yet a persistent systemd service. Keep development access restricted.

## Brain v2

The request path is centered on `core/orchestrator.py` and deterministic request
classification. Ordinary conversation still reaches the legacy router where
appropriate. Developer requests go through `core/developer_bridge.py`, which
recognizes a deliberately small grammar and enforces explicit approval for
sensitive actions.

The bounded-session path is intentionally narrow:

```text
request -> confirmation -> exact "approve" -> initial verification
        -> local repair proposal -> isolated candidate verification
        -> exact sealed-byte promotion -> final result
```

Hard limits for the current Python bounded session are two repairs, three
verification runs total, and two proposal requests.

## Brain v2 Memory

Jarvis maintains exact key-value memory and semantic memory in PostgreSQL
with pgvector. Context policy controls retrieval for each request.
Semantic retrieval ranks candidates using similarity plus source and category
boosts, with a default context selection threshold of 0.50.

| Component | Responsibility |
| --- | --- |
| `core/memory_observability.py` | Request-local retrieval status, counts, selected IDs, weighted scores, categories and threshold |
| `core/memory_approval.py` | Bounded interaction-bound proposals, 120-second expiration, explicit single-use approval or cancellation |
| `core/approved_memory_persistence.py` | Consume live approval, check duplicates, preserve reviewed text and attempt storage once |
| `core/semantic_memory.py` | Local embeddings and pgvector storage; optional exact whitespace preservation |
| `tools/local_memory_console.py` | Dedicated interactive review and approval interface, dry-run by default |

Retrieval diagnostics are internal BrainResult metadata, not a new public API.
Weighted ranking scores may exceed 1.0 because of additive boosts.
Approved persistence fails closed on duplicate lookup errors and does not
automatically retry failures or uncertain commits.

### Local memory console

From the repository root:

```bash
# Default: no real memory storage
.venv/bin/python -m tools.local_memory_console

# Explicitly enable real storage only when intended
.venv/bin/python -m tools.local_memory_console --persist
```

The console requires interactive terminal input and output. Input is hidden;
review the exact displayed text before approving. Each session creates its own
interaction identity. Proposals expire after 120 seconds.

```text
help
propose memory Build a calibration fixture
approve memory <current_proposal_id>
cancel memory <current_proposal_id>
status
exit
```

Approval and cancellation are alternatives, not consecutive steps for the same
proposal. Use the actual generated ID. Dry-run approval never writes memory.
Persistence mode can report success, duplicate, unauthorized, lookup failure,
or persistence failure. Inspect storage before retrying an uncertain outcome.

### Live validation

On November 25, the console stored the first approval-controlled project note
as semantic memory ID **16** with source `brain_v2`, category `project`, and
capture method `approved_project_note`. Exact text retrieval returned raw
similarity 1.0 and one exact match among ten results (not a full-table duplicate
audit). Repeated approval was rejected.

A natural-language recall question through the local orchestrator selected
memory 16 first (weighted score 1.0314), with three of four examined memories
above the 0.50 threshold. Qwen3 correctly recalled the milestone in 6.11 seconds,
though it inaccurately labeled the semantic record as exact memory.

The approval console and persistence adapter are live-tested standalone
components, not yet integrated into normal Flask, dashboard, voice or handheld
conversation routes. Existing implicit memory writes remain active.

### Memory safety and limitations

- TTY presence alone does not authenticate a human; terminal recording remains
  possible. The console assumes a trusted operator.
- Credential and retention checks are heuristic, not comprehensive privacy
  protection. Conversation history may retain text even when memory is declined.
- Duplicate lookup and insertion are separate operations and can race.
- Git backs up source code, not PostgreSQL memory records or installed service
  configuration.

## Developer Agent Safety Boundary

Python bounded sessions use a fresh disposable candidate workspace. The original
project is not changed until a candidate passes verification.

On Thor the candidate path uses:

- `/usr/libexec/jarvis-api-entry`
- AppArmor parent profile `jarvis-api-entry`
- local child `candidate_userns`
- `/usr/bin/unshare --user --map-root-user --net`
- root-owned `/usr/libexec/jarvis-candidate-sandbox`
- Bubblewrap runtime profile `candidate_runtime`

The sandbox mounts only the reviewed Python runtime dependencies and candidate
tree, keeps the candidate read-only, provides private temporary storage, and uses
a disconnected network namespace. User-namespace creation and profile changes are
denied outside the narrow setup transition.

## Vision Lab

Vision Lab remains the primary workshop surface. The workbench camera is selected
by role instead of remembered `/dev/video*` numbering. Scan Mat preserves raw,
annotated, and rectified artifacts. Calibration and measurement diagnostics should
always state their assumptions and should not claim accuracy beyond physical
validation.

## Service Commands

```bash
jarvis start
jarvis stop
jarvis restart
jarvis status
jarvis ui
```

`jarvis restart` restarts the API and UI while preserving healthy model servers.

## Repository Layout

```text
api.py                         Flask API
core/                          Brain v2, routing, memory, Developer Agent
core/developer_agent/          Controlled developer tools and sessions
packaging/apparmor/            Native launchers and Thor AppArmor policy
skills/                        Runtime, vision, measurement, status skills
ui-app/                        React/Vite dashboard
scripts/                       Startup, restart, status, operational helpers
tools/                         Local memory console and engineering tools
tests/                         Regression and component tests
hardware/                      Workshop hardware sources and notes
docs/                          Current docs plus clearly labeled history
```

## Next Development Priorities

1. Back up PostgreSQL memory and verify restoration; include installed security
   and service configuration in recovery planning.
2. Improve console usability with separate visible command and protected
   candidate input while preserving exact review and terminal safety.
3. Retire or gate legacy implicit project-note capture; separately address
   exact-memory automatic writes and explicit-router safeguards.
4. Design authenticated, interaction-bound dashboard approval with CSRF
   defenses and separation from model and handheld output.
5. Add atomic duplicate protection and semantic memory correction/deletion.
6. Improve retrieval relevance and accurate memory-source attribution.
7. Revalidate production API, remote handheld behavior and UI operations.

## Documentation

Start with [docs/README.md](docs/README.md).

Current canonical references:

- [Architecture](docs/ARCHITECTURE.md)
- [Developer Agent](docs/JARVIS_DEVELOPER_AGENT.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Thor startup](docs/UBUNTU_STARTUP.md)
- [Roadmap](ROADMAP.md)
- [Version history](VERSION.md)
- [Changelog](docs/CHANGELOG.md)
- [Codex prompt library](CODEX_PROMPTS.md)

Recent development checkpoints:

- [November 22–23: secure API, mixed-intent routing and personalized memory](docs/JARVIS_DEVELOPMENT_CHECKPOINT_2026-11-22_23.md)
- [November 25: approved memory lifecycle](docs/JARVIS_DEVELOPMENT_CHECKPOINT_2026-11-25.md)
- [Secure API deployment and rollback](docs/SECURE_API_DEPLOYMENT_2026-11-23.md)

Dated checkpoint and investigation documents are retained as historical records;
they do not override the current canonical documents above.
