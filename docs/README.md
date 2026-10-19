# Jarvis Documentation

Last updated: 2026-10-19

This index distinguishes **current canonical documentation** from historical
checkpoints and investigations. If a dated checkpoint disagrees with a canonical
document, use the canonical document.

## Start Here — Canonical

- [Project overview](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Developer Agent](JARVIS_DEVELOPER_AGENT.md)
- [Development guide](DEVELOPMENT.md)
- [Thor startup and service lifecycle](UBUNTU_STARTUP.md)
- [Current roadmap](../ROADMAP.md)
- [Version history](../VERSION.md)
- [Changelog](CHANGELOG.md)
- [Engineering playbook](../AGENTS.md)
- [Codex prompt library](../CODEX_PROMPTS.md)

## Product / Workshop

- [Vision and Scan Mat](VISION.md)
- [Vision Lab](VisionLab.md)
- [Maker Lab](MakerLab.md)
- [Memory operations](Memory.md)
- [Voice](Voice.md)
- [API reference](API.md)

## Architecture Reference

The files under `docs/Architecture/` remain useful subsystem references:

- [Overview](Architecture/Overview.md)
- [Brain](Architecture/Brain.md)
- [Memory](Architecture/Memory.md)
- [Voice](Architecture/Voice.md)
- [Vision](Architecture/Vision.md)
- [Scan Mat](Architecture/ScanMat.md)
- [Security model](Architecture/SECURITY_MODEL.md)
- [Project memory](Architecture/PROJECT_MEMORY.md)
- [OpenSCAD generation](Architecture/OPENSCAD_GENERATION.md)
- [Maker Lab architecture](Architecture/MAKERLAB_ARCHITECTURE.md)
- [Plugin architecture](Architecture/PLUGIN_ARCHITECTURE.md)

Where these older subsystem documents describe the pre-Brain-v2 request path,
use [ARCHITECTURE.md](ARCHITECTURE.md) as the current top-level authority.

## Developer Agent Current State

The canonical Developer Agent document is
[JARVIS_DEVELOPER_AGENT.md](JARVIS_DEVELOPER_AGENT.md).

The 2026-10-19 Thor milestone established:

- live AppArmor/Bubblewrap candidate isolation: 10 passing isolation tests
- bounded repair session recognition and separate exact approval
- existing-project repair with one candidate proposal and one promotion
- independent final project verification: 6 passing tests
- no test mutation and no Git stage/commit/push

## Historical Material

Dated checkpoint, phase, experiment, investigation, and sprint files are retained
as historical records. They are valuable for reconstructing decisions, but they
are **not current operating instructions**.

Examples include:

- `JARVIS_*_CHECKPOINT_*.md`
- `PHASE*_SUMMARY.md`
- older phase planning files
- camera/gimbal investigations
- early session notes
- old boot/service snapshots

Do not silently rewrite a dated historical checkpoint to match today's system.
Instead, update the canonical documents above and, when useful, add a changelog
entry.

## Documentation Maintenance Rule

When behavior changes, update the smallest relevant canonical set:

- runtime/architecture change → `README.md`, `docs/ARCHITECTURE.md`
- Developer Agent change → `docs/JARVIS_DEVELOPER_AGENT.md`
- startup/AppArmor change → `docs/UBUNTU_STARTUP.md`
- milestone/status change → `VERSION.md`, `ROADMAP.md`, `docs/CHANGELOG.md`
- development workflow change → `docs/DEVELOPMENT.md` or `CODEX_PROMPTS.md`

Historical files should stay historical.
