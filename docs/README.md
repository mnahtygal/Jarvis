# Jarvis Documentation

This index separates current operating documentation from design proposals and
historical checkpoints. When documents disagree, use `AGENTS.md`, the current
root roadmap/version, and the current documents listed under Start Here.

## Start Here

- [Project overview](../README.md)
- [Engineering playbook](../AGENTS.md)
- [Version history](../VERSION.md)
- [Current roadmap](../ROADMAP.md)
- [Current architecture](ARCHITECTURE.md)
- [API reference](API.md)
- [Development guide](DEVELOPMENT.md)

## Architecture

- [Architecture overview](Architecture/Overview.md)
- [Brain and router](Architecture/Brain.md)
- [Memory](Architecture/Memory.md) and [memory schema](Architecture/MEMORY_SCHEMA.md)
- [Voice](Architecture/Voice.md)
- [Vision](Architecture/Vision.md) and [vision pipeline](Architecture/VISION_PIPELINE.md)
- [Scan Mat](Architecture/ScanMat.md) and [calibration](Architecture/SCANMAT_CALIBRATION.md)
- [Project memory](Architecture/PROJECT_MEMORY.md)
- [OpenSCAD generation](Architecture/OPENSCAD_GENERATION.md)
- [Maker Lab architecture](Architecture/MAKERLAB_ARCHITECTURE.md)
- [Plugin architecture](Architecture/PLUGIN_ARCHITECTURE.md)
- [Security model](Architecture/SECURITY_MODEL.md)
- Decisions: [local-first](Decisions/ADR-0001-LocalFirst.md),
  [PostgreSQL + pgvector](Decisions/ADR-0002-PostgresMemory.md), and
  [llama.cpp](Decisions/ADR-0003-llamacpp.md)

Root `ARCHITECTURE.md`, `API.md`, `HARDWARE.md`, and `SOFTWARE_STACK.md` are
short legacy summaries. The `docs/` architecture and API references are the
current detailed sources.

## Vision and Maker

- [Current Vision Lab and Scan Mat behavior](VISION.md)
- [Vision Lab overview](VisionLab.md)
- [Maker Lab](MakerLab.md)
- [Manual scan station — historical workflow](MANUAL_SCAN_STATION.md)
- [Phase 2 definition](Phase2.md)
- [Phase 3 architecture proposal](PHASE3_ARCHITECTURE.md)
- [Future ideas](FUTURE_IDEAS.md)
- Hardware: [workspace](../hardware/README.md),
  [design](../hardware/docs/hardware_design.md),
  [bill of materials](../hardware/docs/bill_of_materials.md),
  [printing settings](../hardware/docs/printing_settings.md), and
  [OpenSCAD/STL revisions](../hardware/openscad/README.md)

## Operations

- [Ubuntu startup and service lifecycle](UBUNTU_STARTUP.md)
- [Boot history](BOOT_HISTORY.md)
- [Jetson setup notes](JETSON_SETUP.md)
- [Deployment](Operations/Deployment.md)
- [Troubleshooting](Operations/Troubleshooting.md)
- [Backups](Operations/Backups.md)
- [Memory operations](Memory.md)
- [Voice](Voice.md)

## Development

- [Development workflow](Development/Workflow.md)
- [Coding standards](Development/CodingStandards.md)
- [Test strategy](Testing/TestStrategy.md)
- [Vision testing](Testing/VisionTesting.md)
- [Project glossary](PROJECT_GLOSSARY.md)
- [MartyBench shift-handoff benchmark](MARTYBENCH_V2_SHIFT_HANDOFF.md)
- Root references: [contributing](../CONTRIBUTING.md),
  [Codex prompts](../CODEX_PROMPTS.md), and
  [engineering principles](../JARVIS_PRINCIPLES.md)

## Historical Checkpoints

These files describe the system at their recorded dates. Fixed device paths,
service mechanisms, routes, and incomplete-feature lists are historical facts,
not current operating instructions.

- [Early build sessions](early_sessions.md)
- [API/UI dashboard — 2026-06-11](JARVIS_API_UI_DASHBOARD_CHECKPOINT_2026-06-11.md)
- [Device status dashboard — 2026-06-12](JARVIS_DEVICE_STATUS_DASHBOARD_CHECKPOINT_2026-06-12.md)
- [Camera snapshot — 2026-06-13](JARVIS_CAMERA_SNAPSHOT_CHECKPOINT_2026-06-13.md)
- [Local vision — 2026-06-13](JARVIS_LOCAL_VISION_CHECKPOINT_2026-06-13.md)
- [Voice hardening — 2026-06-13](JARVIS_VOICE_HARDENING_CHECKPOINT_2026-06-13.md)
- [Services — 2026-06-24](JARVIS_SERVICES_CHECKPOINT_2026-06-24.md)
- [Scan Mat mode — 2026-06-28](JARVIS_SCAN_MAT_MODE_2026-06-28.md)
- [System snapshot — 2026-06-28](JARVIS_SYSTEM_DOCUMENTATION.md)
- [Architecture review — 2026-07-03](JARVIS_ARCHITECTURE_REVIEW_2026-07-03.md)
- [Phase 2 sprint summary — 2026-07-04](PHASE2_SUMMARY.md)
- [Changelog](CHANGELOG.md)

The older [docs roadmap](ROADMAP.md), phase files
([Phase 1](Phase1.md), [Phase 3](Phase3.md), [Phase 4](Phase4.md)), and root
phase copies are retained as planning history. The root [current
roadmap](../ROADMAP.md) controls present priorities.

## Investigations and Reference

- [Insta360 gimbal investigation](CAMERA_GIMBAL_INVESTIGATION.md)
- [AI lab notes](AI_LAB_NOTES.md)
- [Brain next steps](JARVIS_BRAIN_NEXT_STEPS.md)
- [Boot history](BOOT_HISTORY.md)

Investigation documents preserve observations from a particular setup. They
should not override current role-based camera or service documentation.
