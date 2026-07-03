# Jarvis Changelog

This changelog summarizes major project milestones. It is not yet tied to formal tagged releases.

## Unreleased - Documentation Sprint 1.0

### Added

- Top-level architecture reference.
- Developer guide.
- Release-oriented roadmap.
- Vision statement.
- Ubuntu startup documentation.
- Boot history documentation.
- Initial changelog.

### Updated

- README improved to reflect current architecture and startup flow.

## 2026-07-03 - Professional Architecture Cleanup

### Added

- Mission Control read-only operations page inside the existing React UI.
- `ui-app/src/pages/` for page-level components.
- `ui-app/src/components/` for reusable UI primitives.
- `ui-app/src/hooks/` for reusable React state/effects.
- `ui-app/src/services/jarvisApi.ts` as centralized frontend HTTP client.
- `ui-app/src/config/appConfig.ts` for frontend constants.
- `StatusDot`, `MissionSection`, and page extraction cleanup.

### Changed

- `JarvisUI.tsx` reduced to shell/state/page composition responsibilities.
- Mission Control reuses `/api/status/dashboard`; no second dashboard model was introduced.
- Runtime/generated artifacts are now covered by root `.gitignore` rules.

## 2026-07-03 - Boot V3

### Added

- `core/boot/boot-v3.sh`.
- Thor AI Workstation boot banner.
- Service startup through `scripts/start-jarvis.sh`.
- UI readiness wait.
- Text and vision LLM endpoint checks.
- Running model process report.
- System resource report.
- VS Code startup.

### Changed

- Firefox is intentionally not launched by Boot V3. Firefox restores its own session.

## 2026-06-28 - Scan Mat Mode

### Added

- Scan Mat capture endpoint.
- OpenCV scan-mat analysis.
- Raw, annotated, and rectified artifact display in Vision Lab.
- Scan modes for object inspection, measurement help, OCR, 3D print inspection, jet ski parts, and workbench status.

## 2026-06-24 - Service Cleanup

### Added

- Status helper scripts.
- Restart helper script.
- Smoke-test helper script.
- Dashboard Vision status card.
- Service layout documentation for text model, vision model, API, and UI.

## 2026-06-13 - Local Vision

### Added

- Camera snapshot capture.
- Latest snapshot preview.
- Local vision analysis through Gemma vision server.
- Vision analysis activity-log output.

## 2026-06-12 - Device Status Dashboard

### Added

- Device status skill.
- `/api/status/devices`.
- Device status in `/api/status/dashboard`.
- Devices card in React dashboard.
- Samson Q2U, Insta360 Link, PipeWire, and dock power readiness reporting.

## 2026-06-11 - API/UI Dashboard

### Added

- `/api/status/dashboard`.
- Brain, model, memory, and MartyBench status endpoints.
- API-backed React dashboard cards.
- Initial component split with reusable status cards.

## Earlier Milestones

- Local Flask API.
- Brain/router/skills architecture.
- PostgreSQL exact memory.
- PostgreSQL + pgvector semantic memory.
- llama.cpp text runtime.
- Voice input/output path.
- MartyBench evaluation work.

