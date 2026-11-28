# Jarvis Development Checkpoint — November 28, 2026

## Milestone: Controlled Exact-Memory and Preference Capture v1

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

## Known limitations and next mission

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
