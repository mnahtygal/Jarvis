# Jarvis Development Checkpoint — November 27, 2026

## Session summary

Friday morning, NVIDIA Thor. Steps 117–135 completed. Production database recovery was validated, installed runtime configuration was backed up, and Brain v2 controlled project-note capture was implemented, independently reviewed, merged and deployed.

- Starting baseline: `921aca3`
- Feature branch: `feature/brain-v2-controlled-memory-capture`
- Validated production code: `00b1b90fcd2bfa759861b5188b136e685e0135bf`
- Feature commit: Enforce controlled Brain v2 project-note capture
- Local and remote main matched at the feature commit before this documentation update.
- Implementation workflow: Codex High, followed by independent source review, corrective implementation and Thor regression testing.

## Steps 117–120 — PostgreSQL backup and recovery

PostgreSQL 16.15, cluster 16/main, database jarvis, pgvector 0.6.0. Custom-format logical dump and globals export (role passwords excluded). Archive contents and SHA-256 manifest verified.

Private backup location on Thor: `~/jarvis-backups/postgres/20261127-062129/`.

Restored into a temporary database using template0 and pg_restore with exit-on-error and single-transaction. Both extensions (plpgsql and vector) and all five tables restored. Restored size 8,631 kB. Production API remained active.

| Table | Production rows | Restored rows | Data checksum |
|---|---:|---:|---|
| conversation_history | 1267 | 1267 | Match |
| memories | 9 | 9 | Match |
| memory_history | 31 | 31 | Match |
| semantic_memories | 16 | 16 | Match |
| session_state | 4 | 4 | Match |
| Total | 1327 | 1327 | 5/5 matched |

All 16 semantic embeddings populated, each with 384 dimensions. Approved memory ID 16 retained its exact content, project_note source type and approved_project_note capture metadata.

The logical data fingerprints matched at validation time. This is not a bare-metal or independent-host recovery exercise.

## Steps 121–123 — Runtime backup and cleanup

Private backup location: `~/jarvis-backups/runtime-20261127-062406/`.

- runtime-config.tar.gz: Jarvis environment and PKI, Nginx configuration, installed API entry and candidate sandbox launchers.
- systemd-apparmor.tar.gz: API, text LLM and vision service units, API overrides and AppArmor profile.
- Archive inventories and SHA-256 manifest verified; all four checksums passed.
- The first archive omitted systemd/AppArmor because of relative wildcard expansion; corrected with a supplemental archive using absolute paths.
- Files were created with private permissions (0600).
- Temporary restore database removed after successful verification; only postgres and jarvis remained.
- All six production services active; API health returned status ok.

**Security:** Runtime archives contain private keys and potentially credentials. Never commit them to GitHub. Encrypt independent copies. Both backups remain on Thor's primary drive; off-drive protection and runtime configuration restore testing are outstanding. Role passwords are not in the globals export.

## Steps 124–131 — Controlled project-note capture

The former automatic path from process_request through persist_project_note to semantic duplicate lookup and insertion has been removed. The replacement project_note_capture_result receives the classification decision, not the candidate text, and cannot write to the database.

| Request condition | Capture status |
|---|---|
| Successful, good ordinary response; project_note with should_store=True | approval_required |
| Declined project-note candidate | skipped |
| Failed evaluation or Developer Agent request | skipped |
| Successful non-project request | not_applicable |

Confidence does not authorize storage. Model output, HTTP fields/headers, localhost origin and caller-supplied identifiers do not re-enable the retired path. The status is observational: no pending proposal or approval ID is created. Trusted local console and ApprovedMemoryPersistence remain the supported explicit project-note approval path.

Semantic retrieval, memory observability and shared duplicate detection are preserved. Normalized-text duplicate detection and similarity threshold 0.96 remain; test coverage includes a nonduplicate at 0.959.

The separate legacy explicit semantic commands (remember/note/save), natural and explicit exact-memory writes, update/forget commands, and conversation history remain unchanged. This is not a universal memory approval boundary.

### Test protection corrective work

The initial autouse fixture was insufficient for imports/collection. Replaced by an early pytest plugin configured in pytest.ini; default discovery excludes live root-level PostgreSQL smoke scripts. The guard patches psycopg2 connection entry points and counts attempts by phase. Self-tests exercise an earlier Python wrapper alias, collection, fixture lifecycle and mock compatibility, with a sentinel protecting synthetic probes if plugin loading fails.

The guard is process-local Python protection, not OS-level isolation. Fresh subprocesses, standalone scripts, other clients and pre-captured native connector references require separate protection.

### Validation evidence

| Run | Result |
|---|---|
| Initial feature suite | 192 passed |
| Initial broad suite (two Pillow-dependent Grounded SAM suites excluded) | 1002 passed, 27 failed, 7 subtests passed |
| Corrected targeted suite | 340 passed; zero DB attempts |
| Independent Thor guard self-test | 1 passed; zero outer-process DB attempts |
| Independent Thor memory regression suite | 115 passed; zero DB attempts |
| Four affected modules, corrected branch | 139 passed, 27 failed |
| Same four modules, isolated baseline 921aca3 | 139 passed, 27 failed |

All 27 earlier failures reproduced on baseline in the same execution environment. Twenty-six involved candidate verification/isolation or socket permissions; one involved a benchmark directory already existing. They remain unresolved, not newly introduced regressions in the comparison. Live Thor candidate isolation was not revalidated in this session.

Initial test-harness targeting error: seven psycopg2 calls before the blocker was active, all failed with OperationalError; Codex reported no successful connection/query/write. Subsequent initial runs intercepted 36 calls (43 total including the initial seven). Corrective comparison runs intercepted 18 calls each; synthetic guard child intercepted seven probes across startup, collection, setup, call and teardown. Corrected targeted and independent runs recorded no unexpected attempts. Test counts overlap and must not be summed as unique tests.

Python compilation and git diff --check passed. Initial UI lint/build passed. Feature commit changed nine files (391 insertions, 223 deletions). Existing unrelated modified launcher binary and untracked artifacts were excluded. Feature branch pushed; main fast-forwarded and pushed without force.

## Steps 132–135 — Production deployment and validation

Only jarvis-api.service restarted. API PID changed from 3514 to 43980. Health returned status ok; AppArmor reported jarvis-api-entry (enforce). PostgreSQL, API, text LLM, vision LLM, Nginx and Tailscale all active. API 5000 and LLM ports 8080/8081 remained loopback-only; Nginx HTTPS listened on 443.

Two live POST /text tests used an ordinary simulated lunar weather dashboard project idea. Jarvis responded normally. Semantic memory count and maximum ID remained 16, and the entire semantic table fingerprint stayed unchanged from backup validation.

The initial Brain status command returned general runtime status rather than detailed capture status. Source inspection identified the correct command: Brain v2 status. Repeating the project idea and immediately requesting detailed status produced:

- Brain version: 2.0-phase12
- Strategy: llm; actual route: llm_fallback
- Context: semantic_memory, recent_history, last_topic
- Evaluation: good
- Memory decision: project_note
- Persistence: approval_required
- Processing: 7644 ms
- Semantic memory count: 16, unchanged
- API: active

This validates the deployed automatic project-note capture gate for the tested request. The public text formatter does not expose all internal approval fields; those were covered by automated tests. Conversation history can retain the test turns. The repeated response suggests conversational continuity but does not establish which specific context item caused it.

## Next priorities

1. Control legacy natural exact-memory capture and explicitly define authorization for existing memory commands.
2. Design authenticated, interaction-bound dashboard memory approval with CSRF defenses and sanitized status/logging.
3. Add semantic correction, deletion and retention controls; address conversation history privacy separately.
4. Address non-atomic duplicate lookup/insert and uncertain writer outcomes.
5. Create encrypted independent backup copies and test runtime configuration recovery.
6. Resolve baseline candidate isolation/socket and benchmark test failures; verify Thor isolation without weakening AppArmor.
7. Improve trusted console ergonomics while preserving exact candidate review and safe terminal handling.

## Handoff

Production code baseline is 00b1b90; this checkpoint is documentation only. No schema migration was performed. A code rollback would restore legacy automatic capture, so consider the authorization implications before reverting. No backup contents, credentials, private keys or memory records are included in this checkpoint.

Related: [November 25 checkpoint](JARVIS_DEVELOPMENT_CHECKPOINT_2026-11-25.md), [Architecture](ARCHITECTURE.md).
