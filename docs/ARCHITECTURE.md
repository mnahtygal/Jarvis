# Jarvis Architecture

Last updated: 2026-10-19

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
