# Jarvis

Jarvis is a local-first AI engineering assistant running on NVIDIA Jetson AGX
Thor. It combines local language and vision models, voice, persistent memory,
camera/workshop workflows, and a controlled Developer Agent without requiring
cloud inference for normal operation.

Last updated: 2026-10-19

## Current Status

Jarvis has two active development tracks:

- **Maker & Workshop Assistant** — Vision Lab, Scan Mat, calibration, measurement,
  and workshop tooling remain active Phase 2 work.
- **Developer Agent** — bounded Python repair sessions now work end-to-end on
  Thor with candidate isolation, explicit approval, verification limits, and
  exact passing-byte promotion.

The 2026-10-19 repair benchmark is the current Developer Agent milestone:
Jarvis repaired an existing failing Python project, verified the candidate inside
the hardened sandbox, promoted only the passing source, and independently finished
with all 6 project tests passing.

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
hardware/                      Workshop hardware sources and notes
docs/                          Current docs plus clearly labeled history
```

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

Dated checkpoint and investigation documents are retained as historical records;
they do not override the current canonical documents above.
