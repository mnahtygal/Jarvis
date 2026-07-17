# Jarvis Changelog

This changelog summarizes major project milestones. It is not yet tied to formal tagged releases.

## Unreleased - Architecture Lab v1

### Added

- Added Architecture Lab with Overview, Project Tree, Call Flow, and Statistics views.
- Added fixed read-only API routes for the generated Graphify project-tree and call-flow HTML artifacts.
- Added a dedicated architecture status endpoint while preserving architecture status in the dashboard payload.
- Added centralized frontend architecture API helpers and Architecture Lab navigation.
- Added focused tests for allowed, missing, and arbitrary architecture artifact requests.

### Notes

- Graphify remains a separate local installation and generated output remains under ignored runtime storage.
- Graphify execution and refresh controls are intentionally deferred.

## Unreleased - July 3-4 Phase 2 Development Sprint

### Project Architecture

- Added professional React structure with `pages/`, `components/`, `hooks/`, `services/`, `config/`, and `types/`.
- Added centralized frontend API service layer in `ui-app/src/services/jarvisApi.ts`.
- Added frontend configuration layer in `ui-app/src/config/appConfig.ts`.
- Extracted page-level components for Home, Mission Control, Vision Lab, and Placeholder pages.
- Extracted reusable UI primitives including Mission sections and status indicators.
- Added reusable hooks for dashboard status, API health, calibration, and measurement.
- Preserved in-memory page navigation; React Router was not introduced.

### Mission Control

- Added Mission Control as a read-only page inside the existing React UI.
- Reused `/api/status/dashboard`; no second dashboard model was created.
- Displayed core services, runtime, devices, MartyBench, camera diagnostics, and calibration/measurement status.
- Kept Mission Control visibility-only with no restart, shutdown, or control buttons.

### Camera System

- Added camera diagnostics backend skill and `/api/status/camera-diagnostics`.
- Added camera diagnostics to dashboard status.
- Documented Thor/Insta360 Link device mapping: `/dev/video0` video capture and `/dev/video1` metadata.
- Documented UVC driver, standard V4L2 pan/tilt/zoom controls, and their physical gimbal limitation.
- Documented Insta360 UVC Extension Unit findings: Unit ID 9, GUID `faf1672d-b71b-4793-8c91-7b1c9b7f95f8`, 11 controls.
- Added manual overhead scan station profile in `config/camera_profiles.json`.
- Added manual scan station documentation and camera gimbal investigation notes.

### Scan Mat And Vision

- Preserved raw, annotated, and rectified scan-mat artifact workflow.
- Added Scan Mat diagnostics including image size, edge pixels, contour counts, candidate quad counts, selected area ratios, failure reasons, and suggestions.
- Displayed Scan Mat Diagnostics in Vision Lab.
- Improved Vision Lab as the main camera, Scan Mat, calibration, measurement, and diagnostic workspace.

### Calibration

- Added backend calibration foundation in `core/calibration.py`.
- Added calibration status skill and `/api/status/calibration`.
- Added calibration state to dashboard payload.
- Added `POST /api/calibration/apply` for applying calibration from known mat dimensions and detected corners.
- Added `GET /api/calibration/profile` for active camera profile inspection.
- Stored calibration in the active camera profile.
- Added interactive Vision Lab calibration controls.

### Measurement

- Added backend measurement foundation in `core/measurement.py`.
- Added measurement status skill and `/api/status/measurement`.
- Added `POST /api/measurement/analyze` for measuring an existing rectified/artifact image.
- Added dashboard measurement status.
- Added Vision Lab measurement UI.
- Added bounding-box measurement v0 with width, height, area, confidence, method, bounding-box pixels, and diagnostics.
- Marked Phase 2.3A Measurement Engine foundation complete.

### Documentation

- Updated roadmap and version history for the Vision Foundation state.
- Added Phase 2 summary documentation.
- Added Phase 3 architecture planning documentation.
- Marked Phase 2 architecture as substantially complete.
- Marked Phase 2.3B Measurement Overlay as the next focused milestone.

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
