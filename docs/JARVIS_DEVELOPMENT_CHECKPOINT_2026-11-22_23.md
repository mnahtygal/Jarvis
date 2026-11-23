# Jarvis Development Checkpoint — November 22–23, 2026

**System:** NVIDIA Thor (Ubuntu 24.04), Jarvis local-first assistant
**Repository:** `mnahtygal/Jarvis`
**Recorded production branch:** `main`
**Last verified local and remote commit:** `808a714` — `merge: integrate Brain v2 routing with secure API deployment`
**Scope:** Work observed and validated over November 22–23, 2026. This is a checkpoint record, not a claim that every change in the November 22 baseline was written during these two days.

## Executive summary

The November 22 working Jarvis state was backed up and committed as a recoverable checkpoint. On November 23, the API was deployed behind the native AppArmor launcher, preserving handheld authentication. A Brain v2 mixed-intent routing fix was integrated, tested, fast-forwarded into `main`, and pushed to GitHub. Production Flask, Qwen3 text inference, Gemma vision, authenticated handheld chat, and API image analysis were verified. Finally, a real-world personalized-memory failure involving Olivia and the LooLoo app was investigated and corrected by adding a single semantic memory to PostgreSQL/pgvector, without changing application code.

## November 22 — known-good baseline

- Backed up the working tree to `/home/mnahtygal/jarvis-backups/jarvis-20261122-190732/jarvis-working-tree.tar.gz` (approximately 319 MB); gzip integrity check passed.
- Created `checkpoint/jarvis-2026-11-22` at commit `55cbc6d`, based on prior `main` commit `18a62e4`.
- Checkpoint captured previously accumulated API, handheld, developer-session UI, documentation, and startup changes. Not all checkpoint changes were newly authored on November 22.
- Kept pre-existing untracked files and the locally modified native launcher binary out of the checkpoint commit.
- Completed a narrow Brain v2 mixed-intent fix on `feature/brain-v2-mixed-intent-routing` at `7ccad5b`: 17 lines added to `core/router.py` and 38 lines of tests in `tests/test_runtime_identity_mixed_intent.py`. Requests such as “What model are you using, and tell me a joke?” should no longer be consumed solely by the deterministic runtime-status response.

## November 23 — API security deployment

- Used security branch `feature/api-apparmor-service`, rooted at checkpoint `55cbc6d`.
- Native launcher fix `f27a389`: retained only approved inherited `JARVIS_HANDHELD_TOKEN` for API mode through launcher environment sanitization; kept candidate-isolation verification mode separate. Added launcher regression tests.
- Backed up original installed launcher, unit, and AppArmor policy under `/home/mnahtygal/jarvis-backups/api-apparmor-20261123-051712/`.
- Installed the secure launcher at `/usr/libexec/jarvis-api-entry`; installed executable SHA-256 was recorded as `95ec8cdea2bb385810e5fb068a9c93cd9eb5428665a2fbaddbabcdc10d0c615a`.
- Configured `jarvis-api.service` to start via the secure launcher using systemd drop-in `20-secure-launcher.conf`, while retaining existing handheld environment configuration. Observed process profile: `jarvis-api-entry (enforce)`.
- Production validations: Flask `/health` returned `{"status":"ok"}`; invalid handheld credential returned HTTP 401; valid handheld chat returned HTTP 200; saved-image Gemma 3 analysis returned HTTP 200; Qwen3 and Gemma model servers returned healthy on ports 8080 and 8081.
- Documentation commits: `5aae7a8` deployment record and `8a19a25` production verification update in `docs/SECURE_API_DEPLOYMENT_2026-11-23.md`.

## November 23 — branch integration and validation

- Merged `feature/brain-v2-mixed-intent-routing` into `feature/api-apparmor-service` with merge commit `808a714`. The two branches had no overlapping changed files relative to checkpoint `55cbc6d`.
- Regression checks: **197 passed** (routing, launcher, handheld, and Developer Agent approval/bridge/planning tests); secure candidate-isolation launcher **10 passed**; UI tests **16 passed**; `git diff --check` passed.
- Fast-forwarded local `main` from `18a62e4` to `808a714`, then pushed normal non-force update to `origin/main`. The local and remote branch pointers were verified equal at `808a714`.
- Relative to previous `main` `18a62e4`, integrated diff reported **21 files changed, 1,487 additions, 8 deletions**. Relative to checkpoint `55cbc6d`, the post-checkpoint feature/security work added **279 lines** across routing, tests, launcher C code, and deployment documentation. These are Git diff counts, not a precise measure of code typed during the two calendar days.

## November 23 — live Brain v2 production check

- Restarted **only** `jarvis-api.service` to load the updated Python sources. New Flask PID at validation: `602487` (previously `587107`). After startup, `/health` was healthy, AppArmor was still enforced, and model ports 8080 and 8081 remained healthy.
- Live `POST /text` with `use_voice: false`:
  - **Model-only question:** “What model are you using?” → HTTP 200; Jarvis identified Qwen3 30B / llama.cpp.
  - **Mixed-intent question:** “What model are you using, and tell me a short joke?” → HTTP 200; Jarvis identified Qwen3 and supplied a joke.
- This verifies observable production behavior; the internal route selected on the live call was not separately captured.

## November 23 — UI and personalized semantic memory

- A dashboard refresh revealed Vite UI port **5173** was not listening, while Flask port **5000** remained healthy. UI was started manually with `npm run dev -- --host 0.0.0.0` from `ui-app`; the UI was then accessible again. The Vite development UI is **not yet configured as a persistent systemd service**. LAN exposure of port 5173 should remain restricted to trusted devices.
- Initial user question in Jarvis UI: “Tell me a joke you would give Olivia using the LooLoo App.” Jarvis incorrectly said it lacked information about Olivia and LooLoo, then gave a generic joke.
- Traced normal response construction: `skills/llama_cpp_skill.py` calls `build_messages(prompt)` from `core/context.py`; the context builder supports exact memory, semantic memory, and recent history. The LLM/context connection existed; missing relevant saved facts were the primary observed issue.
- Diagnostic search: **9 exact memories** and **14 semantic memories** initially; no direct Olivia/LooLoo/Looi text matches in either store. Top semantic result for the LooLoo query was unrelated and below the 0.50 context threshold (approximately 0.412).
- Added one persistent semantic memory with source ID `jarvis-looloo-project-context-v1`, PostgreSQL row **ID 15**: Olivia is Marty's granddaughter; LooLoo is the Android AI companion Marty is developing for her, offering child-friendly conversation, jokes, and educational activities. Recorded intent: tailor applicable responses for a young child.
- After insertion, the relevant memory ranked **#1** at weighted similarity **0.756**, exceeding the context threshold of 0.50.
- Repeated the same UI request. Jarvis responded with a child-oriented puppy joke tailored for Olivia instead of claiming ignorance. This is a successful observable personalized-memory behavior test; production request-level retrieval trace was not captured.
- The memory insert is **database state, not Git content**. Re-cloning the repository alone will not restore memory ID 15. A PostgreSQL backup/export should be included in a future data backup plan.

## Verified operating state at end of session

| Component | Observed result |
| --- | --- |
| Git branch | `main` |
| Local and GitHub `main` | `808a714` at last push verification |
| Flask API | Active; `/health` OK |
| API security | `jarvis-api-entry (enforce)` |
| Text backend | Qwen3 30B via llama.cpp, port 8080 healthy |
| Vision backend | Gemma 3 4B, port 8081 healthy |
| Handheld authentication | Valid request HTTP 200, invalid credential HTTP 401 |
| Vision Flask endpoint | Saved-image analysis HTTP 200 |
| Regression suites | 197 Python + 10 isolation + 16 UI passed |
| Brain v2 mixed-intent | Live text API answered both parts of request |
| Personalized memory | Relevant semantic record ID 15, similarity 0.756; UI response improved |
| Vite dashboard | Manually restarted; persistence not configured |

## Preserved local working-tree artifacts

The following were intentionally **not committed** in the integration work: modified compiled binary `packaging/apparmor/jarvis-api-entry`; untracked `FETCH_HEAD`, `approval_probe.py`, `approval_probe2.py`, `developer-agent-greenfield-2026-10-17`, `scripts/jarvis-restart.sh.bak.before-hermes`, `scripts/start_jarvis_llama_server.sh.pre-security-audit`, and `ui-app/vite.config.ts.pre-security-audit`. Do not indiscriminately run `git add .`, `git clean`, or reset the working tree.

## Open items and next steps

1. **Developer Agent:** Its approval/bridge/planning suites passed, and launcher candidate-isolation verification passed, but a controlled, *approved* candidate execution through production Flask remains unverified. Never bypass approval to test this.
2. **Memory quality:** Add project knowledge through a reviewed, deduplicated workflow. Inspect request-policy handling and capture retrieval evidence before changing relevance thresholds or introducing automatic memory ingestion.
3. **UI operations:** Decide whether to install a persistent UI service or deploy a production-built frontend. Do not expose the Vite development server beyond trusted LAN access.
4. **Personality separation:** Review why an earlier authenticated handheld response identified itself as “LooLoo” rather than “Jarvis”; keep child-companion identity distinct from general Jarvis identity.
5. **Backups:** Ensure the live PostgreSQL memory database, service drop-ins, and installed launcher are covered by a documented recovery plan. Git alone does not capture those runtime assets.
6. **Production tests:** After future changes, recheck Flask health, AppArmor enforcement, text and vision model health, handheld authentication, UI reachability, and mixed-intent behavior.

## Recovery references

- Working-tree archive: `/home/mnahtygal/jarvis-backups/jarvis-20261122-190732/jarvis-working-tree.tar.gz`
- API/AppArmor deployment backup: `/home/mnahtygal/jarvis-backups/api-apparmor-20261123-051712/`
- Known-good pre-integration checkpoint: `checkpoint/jarvis-2026-11-22` (`55cbc6d`)
- Integrated code: `main` (`808a714` at final push verification)
- Detailed secure API deployment and rollback procedure: `docs/SECURE_API_DEPLOYMENT_2026-11-23.md`

---

**Checkpoint principle:** Preserve the working production installation. Treat code in Git, deployed security/systemd configuration, and PostgreSQL memory data as three distinct assets requiring separate verification and backup.
