# Jarvis Development Checkpoint — November 28, 2026

## Milestone 1: Controlled Exact-Memory and Preference Capture v1

Historical snapshot: the explicit legacy command limitations below were superseded by Milestone 2 later the same morning.

Status: merged, deployed and live-validated on Thor.

- Starting documentation baseline: `094a2a4` (November 27 checkpoint).
- Production implementation: `f1c3b390c7db11bf79d49a368738b9cf9f2a99ed`.
- Feature branch: `feature/brain-v2-controlled-exact-memory`.
- Main merged fast-forward only; local and remote main matched at deployment.
- Nine files committed, 291 insertions and 85 deletions.
- No schema migration, native launcher changes, or security configuration changes.

## Implementation

The audit identified an implicit router path, `_try_natural_memory()`, that could upsert exact facts or preferences and append memory history without an explicit command. It was removed, including its call site. Ordinary personal statements now use conversational routing with existing recall paths available. This also eliminates the implicit preference overwrite of the legacy preferred-database key.

The request classifier and router now recognize whole-word legacy memory commands rather than matching arbitrary prefixes such as Remembering, Noteworthy, or Saved. Explicit remember, note, save, update and forget paths remain separate legacy operations.

The observe-only `memory_capture_result()` policy covers PROJECT_NOTE, EXACT_FACT and PREFERENCE. Eligible candidates after a successful, good ordinary response report approval_required without creating a proposal, approval ID or write authority. Declined candidates and unsuccessful/lower-quality evaluations report skipped; Developer Agent requests remain separate. Other successful, good requests report not_applicable.

Independent review rejected an initial regex-based response replacement because it could discard useful explanations. The corrected orchestrator preserves the model reply and, after evaluation, appends a deterministic application-generated notice for LLM fallback replies with approval_required and exact-fact/preference classification:

> Memory status: This turn did not save or update long-term memory.

Context guidance distinguishes conversation history and recall from durable writes. The model cannot authorize storage. No extra LLM calls are introduced.

## Committed inventory

- core/context.py
- core/memory_persistence.py
- core/orchestrator.py
- core/request_classifier.py
- core/router.py
- docs/ARCHITECTURE.md
- tests/test_controlled_exact_memory.py
- tests/test_memory_persistence.py
- tests/test_route_trace.py

Pre-existing modified launcher binary and unrelated untracked artifacts were excluded and preserved.

## Verification

Codex High initially reported 379 targeted passing tests. After review refinement, 391 targeted tests passed (12 additional cases). Independent Thor verification passed the PostgreSQL guard self-test (1 test) and selected regression suite (186 tests), for 187 independent passes. These suites overlap and should not be added as unique test counts.

Python compilation and git diff --check passed. Independent source review verified removal of the implicit write path, retention notice placement, context guidance, real-router regression coverage and unchanged guard configuration.

Final targeted and independent outer pytest processes reported zero blocked PostgreSQL attempts in startup/session, collection/import, setup, call and teardown. Earlier initial development runs had three intercepted call-phase attempts (two legacy semantic duplicate lookups and one unstubbed session-topic write). All were reported intercepted before connection. The three corrective guard self-test child runs intentionally triggered 21 synthetic probes (3 startup/session, 6 collection/import, 3 setup, 6 call, 3 teardown). The guard is process-local Python protection, not OS-level database isolation.

The 27 previously reproduced baseline failures were outside this targeted suite; no claim that the full repository suite is green.

## Deployment

Only jarvis-api.service was restarted. Old PID 43980, new PID 667948. Three initial connection refusals during startup were followed by a successful /health response. AppArmor verified: jarvis-api-entry (enforce).

All six services active after deployment: postgresql, jarvis-api, jarvis-llama, jarvis-vision, nginx, tailscaled. Final API health after live testing: {"status":"ok"}.

## Live acceptance tests

Four ordinary statements were submitted through the production loopback /text endpoint, with Brain v2 status queried immediately after each.

| Input | Decision | Persistence | Processing ms |
| --- | --- | --- | ---: |
| My favorite test color is ultraviolet. | preference | approval_required | 8773 |
| I work at Example Test Company. | exact_fact | approval_required | 4527 |
| I prefer Python. | preference | approval_required | 5392 |
| I like baseball. | preference | approval_required | 5377 |

All four used llm_fallback, had good evaluation, returned useful conversational replies and displayed the retention notice. Brain v2 reported 2.0-phase12. The ultraviolet response referenced yesterday's lunar dashboard discussion, consistent with continued conversational context.

Read-only repeatable-read snapshots before and after the four tests matched in every table. Fingerprints use MD5 of sorted per-row MD5 hashes of JSONB row representations.

| Table | Before | After | Identical checksum |
| --- | ---: | ---: | --- |
| memories | 9 | 9 | cd7bd448465d6af3e9bcc1c7dbc82337 |
| semantic_memories | 16 | 16 | dcd58d75e223d5e11350664bce135665 |
| memory_history | 31 | 31 | cc3fe24ae51adc3e9ccd0e00ae5fd079 |

All 56 durable-memory and memory-history records remained unchanged in final snapshots. These fingerprints also match the November 27 backup validation. The SQL snapshots were read-only; live API requests can write conversation history and session state. Matching snapshots do not prove absence of all intermediate operations. Status is process-global and can be overwritten by concurrent requests.

## Milestone 1 limitations and next mission (historical)

- Explicit legacy commands still permit immediate writes, updates and deletes. Whole-word matching does not establish genuine speaker intent; leading command-like prose can still be interpreted as a command.
- Legacy explicit preference-key normalization can map unrelated preferences to the preferred-database key.
- Candidate detection is heuristic. Missed candidates do not gain implicit write authority, but may receive no retention notice.
- The model can still make misleading claims; the application notice clarifies the result for eligible turns without rewriting model text.
- Conversation history and input logs may retain original statements, including synthetic live test inputs. No cleanup performed.
- The existing trusted local approval console and persistence adapter support project notes only. No exact-memory approval proposal or authenticated dashboard approval was added.
- Handheld isolation covered by regression tests; remote device end-to-end behavior was not revalidated in this deployment.
- Rolling back to prior code would restore implicit exact-memory writes and their overwrite risk.
- Off-drive encrypted backup, runtime restore validation and existing full-suite baseline failures remain outstanding.

Next recommended development mission: design explicit memory command authorization, then implement a trusted exact-memory approval adapter that exposes normalized key, proposed value and existing value before overwrite. Follow with authenticated dashboard integration and controlled correction/deletion. Keep each mission separately reviewed, tested and deployed.

Development ownership: operator and Bud/authorized Codex implement; other AI collaborators review only.

This checkpoint is documentation only; it does not require a service restart.

---

## Milestone 2: Explicit Memory Command Authorization v1

Status: merged, deployed and live-validated on Thor on November 28, 2026. This milestone supersedes the direct conversational write paths described in Milestone 1.

- Starting checkpoint: `fc4acfd`.
- Current stable production implementation: `ebafb7c4c03528907118f7aadfd999844abc864f`.
- Feature branch: `feature/brain-v2-explicit-memory-authorization`.
- Fast-forward merge and push to main verified; local and remote main matched at deployment.
- 20 files committed, 286 insertions and 259 deletions.
- No schema migration, API endpoint additions, UI changes, native launcher changes or security configuration changes.

### Audit and implementation

The remaining conversational mutation paths were explicit remember, note, save, update and forget commands. The router previously invoked exact-memory upserts/deletes and freeform semantic insertion. The audit also identified nontransactional old-value retrieval, history entries for nonexistent deletes, normalized update values losing case/punctuation, broad recall precedence and fail-open legacy semantic duplicate lookup. The underlying SQL and transaction redesign are deferred.

The router now removes the four durable-memory mutation calls and obsolete helper/import paths. Recognized leading whole-word legacy forms, including incomplete commands, return a fixed response:

> Long-term memory changes require trusted authorization. I haven't changed your saved memory.

No model call, candidate echo in the response, pending proposal or approval ID is needed. Leading memory commands take precedence over broad recall and Developer Agent heuristics. The existing multiline/large-request fallback remains first in the router; model replies from that path do not gain mutation authority.

Blocked deterministic commands report intent memory_write (classification only), strategy deterministic, actual route memory_authorization_required, decision explicit_memory_command, should_store=false, persistence approval_required, memory_persisted=false, target none, approval kind none, no pending approval and no action ID. Successful response evaluation means the denial was delivered, not that storage succeeded. Deletion requests use the same diagnostics without becoming capture candidates.

The capability registry disables conversational memory writes; model guidance, help and architecture documentation reflect the new boundary. Exact and semantic recall remain available. The trusted local project-note console, approval engine and approved persistence adapter remain unchanged. Direct Python calls, administrative utilities and database access remain outside this application-level boundary.

### Committed inventory

- core/brain.py
- core/capability_registry.py
- core/context.py
- core/execution_strategy.py
- core/memory_decision.py
- core/orchestrator.py
- core/request_classifier.py
- core/route_trace.py
- core/router.py
- skills/help_skill.py
- docs/ARCHITECTURE.md
- docs/BRAIN_V2_CAPABILITIES.md
- docs/BRAIN_V2_ROUTE_TRACE.md
- tests/test_capability_registry.py
- tests/test_controlled_exact_memory.py
- tests/test_execution_strategy.py
- tests/test_explicit_memory_authorization.py
- tests/test_memory_decision.py
- tests/test_orchestrator.py
- tests/test_route_trace.py

The pre-existing modified AppArmor launcher binary and unrelated untracked artifacts were excluded and preserved.

### Verification

Codex High reported 440 targeted tests passed, zero failures or skips. Independent source review (steps 157 and 157A) confirmed removed mutation paths, routing precedence, diagnostics, replacement regression expectations and unchanged trusted approval, API, handheld and PostgreSQL guard files.

Independent Thor verification (step 158): PostgreSQL guard self-test 1 passed in 3.96 seconds; selected regression suite 297 passed in 5.93 seconds; total 298 independent passes. Suites overlap; do not sum them as unique tests. Python compilation and git diff --check passed.

All outer pytest processes reported zero blocked PostgreSQL connection attempts across startup/session, collection/import, setup, call and teardown. Codex reported two synthetic guard child runs with 14 intentional probes (2 startup/session, 4 collection/import, 2 setup, 4 call, 2 teardown). The guard remains process-local Python protection, not OS-level isolation. The 27 previously reproduced baseline failures remain outside these targeted suites.

Regression coverage includes all legacy command forms, incomplete commands, broad recall and Developer Agent precedence, forged HTTP/voice metadata, model-generated approval language, live/replayed console IDs, unrelated Developer Agent approvals, mixed and multiline requests, ordinary capture policy, recall and trusted project-note persistence.

### Deployment

Step 160 restarted only jarvis-api.service. Old PID 667948; new PID 687225. Three initial connection refusals during startup were followed by a healthy /health response. AppArmor: jarvis-api-entry (enforce).

All six services active: postgresql, jarvis-api, jarvis-llama, jarvis-vision, nginx, tailscaled.

### Live acceptance (step 161)

Seven ordinary explicit mutation requests and one forged HTTP authorization request were submitted to the production loopback /text endpoint using synthetic keys and values.

| Test | Result |
| --- | --- |
| Remember exact fact | Authorization required |
| Remember semantic note | Authorization required |
| Note | Authorization required |
| Save | Authorization required |
| Update synthetic device | Authorization required |
| Forget synthetic device | Authorization required |
| Bare Remember | Authorization required |
| Forged approved/source/role/interaction ID and HTTP header | Authorization required |
| Existing database preference recall | Passed — SQL Server |
| Final API health | Healthy |

All eight blocked requests returned the exact fixed response. Brain v2 2.0-phase12 reported deterministic strategy, memory_authorization_required route, context none, good evaluation, explicit_memory_command decision and approval_required persistence. Internal processing was reported as 0 ms at displayed millisecond precision for each denial, not literal zero elapsed time or end-to-end HTTP latency. Exact recall reported 12 ms, route exact_memory, decision none and persistence not_applicable.

Read-only repeatable-read before/after snapshots matched:

| Table | Before | After | Identical checksum |
| --- | ---: | ---: | --- |
| memories | 9 | 9 | cd7bd448465d6af3e9bcc1c7dbc82337 |
| semantic_memories | 16 | 16 | dcd58d75e223d5e11350664bce135665 |
| memory_history | 31 | 31 | cc3fe24ae51adc3e9ccd0e00ae5fd079 |

All 56 records remain unchanged, matching the November 27 backup validation and Milestone 1 snapshots. Final API health: {"status":"ok"}. No new approved production note was inserted during this milestone; trusted approval compatibility was verified through regression tests. Existing-key recall was tested, but live mutation attempts intentionally used synthetic keys. Matching snapshots establish final contents, not the absence of every possible intermediate operation.

### Current limitations and next mission

- All identified conversational durable-memory mutation paths are closed. Ordinary conversational saves, updates and deletes are intentionally unavailable pending trusted replacements.
- Direct Python calls, administrative utilities and database privileges are unchanged; this is not database-level access control.
- Complex/large requests may still produce misleading model-generated approval or memory claims without mutation authority. Leading command-like prose can match the deterministic authorization response.
- Existing HTTP heard fields, logs, conversation history and session state can retain blocked input and synthetic test statements. No cleanup performed.
- Brain v2 status is process-global and can be overwritten by concurrent requests.
- Exact-memory approval proposals, transactional approved mutation, key-normalization improvements and controlled deletion are not yet implemented. Existing project-note approval is separate.
- Remote device end-to-end behavior was not revalidated in this deployment.
- The 27 established baseline failures, encrypted off-drive backup and runtime restore validation remain outstanding.
- Rolling back to Milestone 1 would restore legacy direct conversational mutation paths; rolling back further may also restore implicit writes.

Next mission: Structured Exact-Memory Approval Proposals v1. Design immutable, bounded, expiring proposals for a trusted interaction, including the normalized key, proposed operation/value and reviewed existing value, without database mutation. Follow separately with transactional approved persistence (including stale-value checks and accurate history), trusted console integration, authenticated dashboard integration and controlled semantic correction/deletion.

Development ownership remains operator and Bud/authorized Codex for implementation; all other AI collaborators review only.

This update is documentation only; no service restart is required.
