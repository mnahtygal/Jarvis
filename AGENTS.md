# Jarvis AI Engineering Playbook

Last updated: 2026-10-19

## Mission

Jarvis is a local-first AI engineering assistant for software development,
workshop tasks, 3D printing, laser engraving, electronics, Raspberry Pi projects,
SDR, data engineering, and related engineering work.

Reliability, maintainability, safety, and local operation take priority over
flashy features.

## Current Workstreams

Jarvis has two active tracks:

1. **Maker & Workshop Assistant**
   - validate Scan Mat measurement accuracy against physical references
   - continue measurement, scan history, OpenSCAD, and Maker Lab work

2. **Developer Agent**
   - preserve the now-working bounded repair path
   - improve ergonomics and diagnostics without widening authority
   - add additional controlled benchmarks before broader mutation scope

Do not jump from the successful repair benchmark to unrestricted shell access,
package installation, autonomous Git push, recursive agents, or broad multi-file
mutation.

## Core Principles

Jarvis must remain:

- local-first
- offline-capable
- modular
- maintainable
- understandable
- testable
- recoverable
- GitHub-synchronized
- explicit about trust boundaries

Prefer simple, boring, reliable code over clever code.

## Non-Negotiables

- Do not introduce cloud dependencies unless explicitly requested.
- Do not replace PostgreSQL + pgvector without explicit architectural approval.
- Do not remove or rewrite working features without a clear reason.
- Do not break existing API routes without compatibility/migration notes.
- Do not add large frameworks casually.
- Do not hide failures.
- Do not make undocumented architecture or security changes.
- Do not install Pillow.
- Do not weaken host-wide AppArmor user-namespace restrictions to make tests pass.

Protected files include:

- `testbrain.py`
- `audio_pipeline_tester.py`
- `audio_pipeline_tester_jarvis.py`
- `audio_pipeline_tester_jarvis_v2.py`

## Preferred Development Workflow

1. Inspect the existing implementation and canonical docs.
2. Make the smallest safe change.
3. Preserve behavior and safety invariants unless the task explicitly changes them.
4. Run focused checks first.
5. Run the relevant broader checks.
6. Review `git diff --check`, status, and the actual diff.
7. Update the smallest canonical documentation set.
8. Commit/push only when the workflow calls for it.

## Required Checks

Python:

```bash
.venv/bin/python -m compileall -q api.py core skills audio tools
```

UI:

```bash
cd ui-app
npm run lint
npm run build
```

Developer Agent host-isolation changes also require live Thor verification:

```bash
/usr/libexec/jarvis-api-entry --verify-candidate-isolation
```

Codex-only success is not enough for host-policy behavior.

## Repository Areas

```text
api.py                         Flask API
core/                          Brain v2, router, memory, Developer Agent
core/developer_agent/          Controlled developer tooling/session logic
packaging/apparmor/            Thor native launchers and AppArmor profile
skills/                        Camera, vision, measurement, runtime/status skills
ui-app/                        React/Vite UI
scripts/                       Operational scripts
tools/                         Benchmarks and utilities
docs/                          Canonical docs plus historical records
```

## Developer Agent Rules

Treat the Developer Agent as a safety boundary.

Preserve:

- fixed tool registry
- deterministic request grammar
- separate exact approval
- static source/test/verification scope
- bounded model/context/payload sizes
- protected/sensitive path refusal
- two-repair / three-verification / two-proposal ceilings
- test read-only behavior
- candidate-before-original mutation ordering
- AppArmor/Bubblewrap isolation
- exact passing-byte seal/promotion
- no automatic Git stage/commit/push

The generic command tool is not a shell.

The current successful bounded repair milestone does not authorize broader autonomy.

## Vision / Measurement Rules

Vision Lab is the main camera/workshop surface.

Preserve:

- raw image
- annotated detection image
- rectified image
- metadata/diagnostics
- calibration provenance
- explicit confidence/failure states

Do not present measurement output as precise until physical validation supports it.

## Memory Rules

Persistent memory uses PostgreSQL and PostgreSQL + pgvector. Keep project memory
practical and inspectable.

## Documentation Rules

Canonical current docs are indexed in `docs/README.md`.

Update canonical docs when behavior changes. Keep dated checkpoint/experiment files
historical; do not rewrite history just to make old documents agree with today.

Docs should let Marty return days or weeks later and understand what is actually
true now.

## Git Rules

Keep commits focused. Avoid secrets, credentials, `.env`, model files, logs,
large generated artifacts, or runtime camera output.

## Agent Behavior

When acting as an AI coding agent:

- read relevant files first
- distinguish evidence from assumptions
- make minimal changes
- preserve trust boundaries
- run checks
- report the real result
- never claim a host-specific success that was not verified on the host
