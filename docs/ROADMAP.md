# Jarvis Roadmap

Last updated: 2026-07-04

This roadmap is organized by releases. Dates are intentionally omitted until a release is actively scheduled.

## Jarvis 0.3 - Professional Architecture

**Status:** Substantially complete.

### Goals

- Stabilize the current local-first architecture.
- Keep Mission Control visibility-only.
- Make the repo easier to understand, maintain, and contribute to.

### Major Features

- Boot V3 documented and treated as stable.
- Mission Control read-only operations page.
- React architecture split into pages, components, hooks, services, config, and types.
- Centralized frontend API service and config.
- Repository cleanup and ignore rules.
- Documentation Sprint 1.0.
- Hook extraction for dashboard status, API health, calibration, and measurement.

### Success Criteria

- New contributor can understand the architecture from docs.
- UI builds cleanly.
- Backend compile check passes.
- Boot V3 behavior is documented and unchanged.
- Runtime/generated artifacts are ignored.

## Jarvis 0.4 - Voice Assistant

### Goals

- Harden voice input/output for daily use.
- Make voice diagnostics visible and practical.

### Major Features

- Better clipped speech handling.
- Listen diagnostics panel or logs.
- Repeatable voice test checklist.
- Microphone and PipeWire troubleshooting docs.

### Success Criteria

- Voice command path is reliable from UI.
- Failures are visible and actionable.
- Voice does not block camera or dashboard workflows.

## Jarvis 0.5 - Vision Workbench

**Status:** Active. Phase 2.3A Measurement Engine foundation is complete.

### Goals

- Stabilize camera, local vision, and Scan Mat foundations.
- Preserve raw, annotated, rectified, and metadata outputs.
- Establish a fixed manual overhead scan-station baseline before calibration.

### Major Features

- 2.2A Camera Diagnostics & Config Fix.
- 2.2B Manual Overhead Scan Mat Stabilization.
- 2.2C UVC Extension Unit Investigation.
- Camera profiles for the manual overhead scan station.
- Calibration engine, API, profile storage, and Vision Lab calibration UI.
- Scan Mat diagnostics for detection reliability.
- 2.3A Measurement Engine foundation.
- Measurement API and Vision Lab measurement UI.
- Bounding-box measurement v0.
- 2.3B Measurement Overlay.
- Persistent scan history.
- Better artifact browsing in Vision Lab.

### Success Criteria

- Scan Mat detection is repeatable.
- Measurements include unit, calibration source, pixel-to-unit ratio, confidence/quality, raw image reference, and rectified image reference.
- Jarvis does not present unproven measurements as precise.
- Measurement foundation can report bounding-box width, height, area, confidence, and diagnostics from rectified scan images.

### Next Focus

- 2.3B Measurement Overlay.
- Draw bounding boxes and measurement labels on rectified artifacts.
- Preserve measurement metadata with calibration source and confidence.
- Continue improving Scan Mat detection reliability before advanced CAD generation.

## Jarvis 0.6 - Phase 3 Architecture Planning

**Status:** Next major milestone.

### Goals

- Plan the next architecture layer for maker workflows after the Vision Foundation.
- Keep Phase 3 grounded in stable Scan Mat, calibration, and measurement foundations.
- Avoid premature automation until measurements and overlays are trustworthy.

### Major Features

- Measurement Overlay.
- Feature Detection.
- CAD Automation.
- OpenSCAD Generator.
- STL Generation.
- Laser/CNC workflow.
- Multiple camera support.
- Plugin architecture.
- Future Maker Lab vision.

### Success Criteria

- Phase 3 plans have clear boundaries, dependencies, and validation paths.
- Generated CAD remains labeled as starter geometry.
- Maker Lab workflows remain local-first and inspectable.

## Jarvis 0.7 - Agent Framework

### Goals

- Add practical, bounded engineering workflows.
- Avoid broad autonomous behavior until maker foundations are stable.

### Major Features

- Task checklists.
- Local project memory integration.
- Tool execution summaries.
- Safe workflow boundaries for coding and workshop tasks.

### Success Criteria

- Agentic workflows are inspectable and recoverable.
- No hidden cloud dependencies.
- Human approval remains clear for risky operations.

## Jarvis 0.8 - Maker Lab

### Goals

- Support real workshop workflows for 3D printing, laser engraving, electronics, Raspberry Pi builds, SDR, repairs, and part comparison.

### Major Features

- Maker Lab project pages.
- Scan-linked project notes.
- OpenSCAD starter model generation.
- Laser engraving prep notes.
- Electronics and Raspberry Pi build logs.

### Success Criteria

- Maker workflows are grounded in files, scans, measurements, and project memory.
- OpenSCAD output is clearly labeled as starter geometry, not production-ready CAD.

## Jarvis 0.9 - Memory Intelligence

### Goals

- Make Jarvis memory more practical, inspectable, and useful.

### Major Features

- Project memory records.
- Scan/project/generated model decision logs.
- Better semantic search summaries.
- Memory review UI.

### Success Criteria

- Important project context can be found days or weeks later.
- Semantic memory remains PostgreSQL + pgvector.
- Memory entries remain inspectable and explainable.

## Jarvis 1.0 - Personal AI Operating System

### Goals

- Provide a local-first personal AI workstation for engineering, making, memory, and daily project support.

### Major Features

- Stable dashboard and Mission Control.
- Reliable voice and vision workflows.
- Maker Lab.
- Practical project memory.
- Local model runtime management.
- Strong docs, tests, and recovery workflows.

### Success Criteria

- Jarvis can be restarted, inspected, debugged, and extended without tribal knowledge.
- Core workflows work offline on local hardware.
- The project is understandable as a public open-source repository.
