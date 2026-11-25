# Jarvis Development Checkpoint — November 25, 2026

## Executive summary

Four Brain v2 features implemented, independently tested, committed, and fast-forward merged to main. A controlled live test demonstrated explicit local approval, real PostgreSQL semantic storage, replay rejection, independent retrieval and natural-language recall through Qwen3. Production API remained active at the last service check; only the observability feature was explicitly deployed by service restart today.

## Git checkpoints

| Feature | Commit | Branch | Status |
|---|---|---|---|
| Memory retrieval observability | `9962bcc` | `feature/brain-v2-memory-observability` | Merged, deployed |
| Memory approval engine | `8bb9243` | `feature/brain-v2-memory-approval` | Merged |
| Approved memory persistence | `27fab2a` | `feature/brain-v2-approved-memory-persistence` | Merged, live console tested |
| Trusted local memory console | `998d0c8` | `feature/brain-v2-local-memory-console` | Merged, live tested |

Verified local and remote main: `998d0c8408654a84b4df4471f8c9f5bf1afe28ed`. Feature branches preserved. Four-feature total: 1,875 insertions, 27 deletions, 89 new tests.

## Validation summary

| Feature | Reported expanded suite | Independent targeted suite | New tests |
|---|---:|---:|---:|
| Observability | 157 | 36 | 19 |
| Approval | 207 | 25 | 25 |
| Persistence | 269 | 56 | 22 |
| Console | 292 | 70 | 23 |

Suites overlap; counts are not additive. Latest independent console suite: 70 passed in 4.10 seconds. Codex reported 292 tests passed with PostgreSQL blocked and zero connection attempts, successful pseudo-terminal smoke test, compilation and whitespace checks. Live persistence was tested separately with deliberate operator approval.

## Architecture delivered

- `core/memory_observability.py`, `core/context.py`, `core/orchestrator.py`: request-local semantic retrieval diagnostics; disabled/not_run/no_matches/matched/error; examined and selected counts, memory IDs, weighted scores, category labels, threshold. Internal metadata, not a new public endpoint.
- `core/memory_approval.py`: per-engine bounded pending proposals, opaque IDs, 120-second monotonic expiration, explicit matching interaction and trusted source, single-use approval/cancellation under lock. Heuristic credential and opt-out filtering. No database writes by engine alone.
- `core/approved_memory_persistence.py`: consumes genuine live approval before checking top-three semantic matches and attempting storage. Fails closed on lookup error; no automatic retries; reports uncertain commit outcome on writer failure or invalid result.
- `core/semantic_memory.py`: optional keyword-only `preserve_whitespace` retains exact reviewed content; default legacy behavior unchanged. Embedding uses cleaned text.
- `tools/local_memory_console.py`: dedicated interactive terminal session, internally generated interaction identity, dry-run default, explicit `--persist`, exact framed review, hidden input, control-character checks, session cleanup. No model output or network API in approval path.
- `docs/ARCHITECTURE.md` and corresponding regression tests updated.

## Live end-to-end evidence (Steps 109–115)

Dry run: proposal reviewed, approved, replay rejected, pending state cleared, clean exit. No memory written.

First persistence session: unrecognized approval input; pending proposal discarded on exit. Second session: explicit approval succeeded, replay rejected, no pending proposal, clean exit.

Stored record:

- ID: **16**
- Content: `Jarvis Brain v2 gained explicit memory approval on November 25, 2026.`
- Created: `2026-11-25 08:37:21.737143` (database timestamp; timezone not independently established)
- Source type: `project_note`; source ID: null
- Metadata: `{"tags":["jarvis"],"source":"brain_v2","category":"project","capture_method":"approved_project_note"}`
- Exact-text search: distance 0.0, similarity 1.0, weighted similarity 1.18, one exact match among ten returned records. Not an exhaustive table-wide count.

Natural-language recall question: `What did I tell you about explicit memory approval in Jarvis Brain v2?`

Qwen3 response: `Based on your saved memory, **Jarvis Brain v2 gained explicit memory approval on November 25, 2026**. This is noted in the exact long-term memory under project documentation. Let me know if you need further details!`

| Diagnostic | Value |
|---|---|
| Intent | memory_recall |
| Execution strategy | semantic_memory |
| Actual route | llm_fallback |
| Retrieval status | matched |
| Examined / selected | 4 / 3 |
| Selected IDs | 16, 4, 3 |
| Weighted scores | 1.0313853384806007, 0.6801937493624184, 0.5161398176509209 |
| Categories | project, project, hardware |
| Threshold | 0.5 |
| Memory decision | none; should_store=False |
| Automatic project-note persistence | False |
| Elapsed | 6.11 seconds |

Fact recalled correctly; model inaccurately described semantic record as exact memory. Weighted ranking scores can exceed 1 due to boosts. Test called the local orchestrator, not HTTP or the confined production service. Normal conversation history may still persist.

## Operations and security

Observability deployment restarted only jarvis-api; API health recovered and AppArmor enforcement was confirmed. Subsequent standalone features required no service restart. Last verified API state active at merge of `998d0c8`. LooLoo/handheld code unchanged; remote device behavior not independently revalidated today.

Earlier inspection: Nginx LAN and Tailscale TLS sites, exact route allowlists and catchall 404; tailnet destination check on Tailscale site only. No security configuration changes today. No claim of whole-server tailnet-only exposure. Handheld v2 proxy configured but corresponding Flask route not established. Tailscale netfilter warning deferred.

Existing unrelated working-tree items deliberately preserved:

```text
 M packaging/apparmor/jarvis-api-entry
?? FETCH_HEAD
?? approval_probe.py
?? approval_probe2.py
?? developer-agent-greenfield-2026-10-17
?? scripts/jarvis-restart.sh.bak.before-hermes
?? scripts/start_jarvis_llama_server.sh.pre-security-audit
?? ui-app/vite.config.ts.pre-security-audit
```

## Usage

From `~/jarvis`:

```bash
.venv/bin/python -m tools.local_memory_console
# Explicitly enable real storage only when intended:
.venv/bin/python -m tools.local_memory_console --persist
```

Commands: `help`, `propose memory <text>`, `approve memory <proposal_id>`, `cancel memory <proposal_id>`, `status`, `exit`. Input hidden. Review text carefully; approve only the current ID within expiry. Never retry an uncertain commit without inspecting storage.

## Remaining limitations and next priorities

1. Back up PostgreSQL memory data, with restore verification. Git does not back up memory records.
2. Improve console usability: consider separate visible command input and hidden candidate entry without compromising terminal control filtering or exact review. Actual testing exposed hidden-input mistakes.
3. Retire or gate legacy implicit project-note capture, then address legacy exact-memory auto-writes and explicit-router safeguards separately. Existing paths remain active; approval is not universal. Conversation history can retain text even when a proposal is declined.
4. Establish an authenticated interaction-bound dashboard approval flow with CSRF defenses, sanitized status/logging and strict separation from model and handheld outputs. TTY presence is not proof of human identity; terminal recording is possible. Process-local Python trust is not a security sandbox.
5. Add atomic duplicate protection and semantic memory correction/deletion design. Existing duplicate lookup and insert are separate and can race; heuristic checks are not comprehensive privacy protection.
6. Improve retrieval relevance and factual source attribution. Investigate unrelated memories near threshold and overconfident no-match responses.
7. Revalidate actual production API and remote LooLoo behavior before claiming full deployment of the approval workflow. Do not expose approval over HTTP prematurely.

## Resume point

Start from synchronized main at `998d0c8` (or the subsequent documentation-only checkpoint commit if this file is committed). Keep unrelated files untouched, use explicit staging paths, and preserve existing security controls. Focus on Jarvis; no need to reopen other local agent projects.

Development collaboration: ChatGPT GPT-6.2 Medium and Codex GPT-6.2 Sol Medium (model labels reported by operator); inference on Thor via local Qwen3/llama.cpp and local embeddings.
