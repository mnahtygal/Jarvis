# Phase 2 Summary

> **Historical sprint summary (2026-07-04).** For current Phase 2 status, see
> the repository [roadmap](../ROADMAP.md), [version history](../VERSION.md), and
> [documentation index](README.md).

Last updated: 2026-07-04

## Status

Phase 2 architecture is substantially complete after the July 3-4 development sprint.

Current version:

```text
2.3.0-dev
Codename: Vision Foundation
Sprint: July 3-4 Development Sprint
```

Phase 2.3A Measurement Engine foundation is complete. Phase 2.3B Measurement Overlay is next.

## Major Accomplishments

### Project Architecture

- React app organized into pages, components, hooks, services, config, and shared types.
- Mission Control added as a read-only operations view.
- Frontend API calls centralized in `services/jarvisApi.ts`.
- Frontend constants centralized in `config/appConfig.ts`.
- Reusable hooks added for dashboard status, API health, calibration, and measurement.
- Vision Lab established as the primary camera, Scan Mat, calibration, diagnostics, and measurement workspace.

### Camera System

- Camera diagnostics skill and status endpoint added.
- Manual overhead scan station documented.
- Camera profile storage added in `config/camera_profiles.json`.
- Insta360 Link investigation documented.
- Current Thor mapping confirmed:
  - `/dev/video0` is the real video capture node.
  - `/dev/video1` is the metadata node.
  - driver is `uvcvideo`.
- Standard V4L2 pan/tilt controls exist but do not physically move the Insta360 Link gimbal.
- UVC Extension Unit discovered:
  - Unit ID: 9
  - GUID: `faf1672d-b71b-4793-8c91-7b1c9b7f95f8`
  - Controls: 11

### Calibration

- Calibration engine foundation added.
- Calibration status endpoint added.
- Calibration apply endpoint added.
- Active profile calibration storage added.
- Vision Lab interactive calibration UI added.
- Calibration records mm-per-pixel, pixels-per-mm, confidence, and timestamp.

### Measurement

- Measurement Engine foundation added.
- Measurement status endpoint added.
- Measurement analysis endpoint added.
- Vision Lab measurement UI added.
- Bounding-box measurement v0 added for rectified scan images.
- Measurement results include pixel bbox, millimeter bbox, area, confidence, method, and diagnostics.

### Vision

- Scan Mat artifact workflow preserved.
- Raw, annotated, and rectified outputs remain central.
- Scan Mat diagnostics added to explain detection success/failure.
- Vision Lab now shows calibration, measurement, and detection diagnostics in one workflow.

## Architecture Before Vs After

### Before

- `JarvisUI.tsx` carried more UI rendering and workflow state.
- Dashboard status existed, but Mission Control was not a dedicated operations view.
- Scan Mat produced useful artifacts but limited diagnostic detail.
- Calibration and measurement were not profile-backed workflows.
- Camera gimbal behavior was not clearly documented.

### After

- UI is split into page-level components and reusable primitives.
- Workflow state is moving into dedicated hooks.
- Frontend HTTP calls are centralized.
- Mission Control is a read-only status surface.
- Vision Lab supports camera, Scan Mat, calibration, diagnostics, and measurement.
- Calibration persists to the active camera profile.
- Measurement foundation can analyze rectified images.
- Camera limitations are explicitly documented.

## Lessons Learned

- Visibility-first architecture prevents premature control features.
- Manual overhead camera positioning is the stable Scan Mat path until Insta360 gimbal commands are mapped.
- Scan Mat diagnostics are necessary before tuning detection algorithms.
- Calibration confidence must travel with every measurement.
- Measurement should remain conservative until overlays and validation are stronger.
- Keeping Boot V3 stable reduced operational risk during UI/backend iteration.

## Camera Investigation Summary

The Insta360 Link works as a UVC camera on Thor, but its gimbal is not controlled by standard V4L2 pan/tilt controls.

Confirmed:

- `/dev/video0` captures image frames.
- `/dev/video1` is metadata.
- V4L2 pan/tilt/zoom controls are visible.
- Pan/tilt values can be set/read.
- The physical gimbal does not move.
- No Insta360 HID interface is exposed.
- UVC Extension Unit exists and likely requires vendor-specific command mapping.

Current strategy:

- use manual overhead mode
- keep camera fixed after alignment
- calibrate from known Scan Mat dimensions
- defer gimbal automation

## Remaining Technical Debt

- Measurement overlay is not implemented yet.
- Measurement history is not persisted yet.
- Bounding-box detection is simple and can confuse shadows, grid marks, or background artifacts.
- Scan Mat detection needs more reliability work before CAD automation.
- UVC Extension Unit commands are not mapped.
- Maker Lab remains mostly planned.
- React Router is intentionally not introduced yet.
- Some docs still use older release labels alongside the newer 2.x milestone language.

## Ready For Phase 3

Jarvis is ready to begin Phase 3 architecture planning because the core Vision Foundation now exists:

- camera diagnostics
- manual scan station
- camera profiles
- Scan Mat artifacts
- Scan Mat diagnostics
- calibration engine
- measurement engine foundation
- Vision Lab UI workflow

Phase 3 should build on this foundation without skipping validation. The immediate next implementation milestone is Phase 2.3B Measurement Overlay.
