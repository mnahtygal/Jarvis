# Phase 3 Architecture

Last updated: 2026-07-04

## Purpose

Phase 3 architecture planning defines the next layer after the Vision Foundation. It should build on stable camera, Scan Mat, calibration, and measurement foundations without jumping into uncontrolled automation.

Phase 3 should remain:

- local-first
- offline-capable where practical
- inspectable
- recoverable
- grounded in files, scans, measurements, and project memory

## Dependencies

Phase 3 assumes these Phase 2 foundations exist:

- Vision Lab workflow
- manual overhead scan station
- camera profiles
- raw, annotated, and rectified Scan Mat artifacts
- Scan Mat diagnostics
- calibration profile storage
- Measurement Engine foundation
- bounding-box measurement v0

The immediate next step before most Phase 3 work is:

```text
Phase 2.3B Measurement Overlay
```

## Vision

Jarvis should become a practical local maker workstation that can inspect objects, measure them, preserve project context, and generate starter fabrication assets.

Phase 3 should move from "Jarvis can see and measure" toward "Jarvis can help turn observed objects into useful maker artifacts."

## Measurement Overlay

Goal:

- Display bounding boxes and measurement labels over rectified Scan Mat images.

Expected capabilities:

- overlay measured width and height
- show calibration confidence
- show measurement method
- preserve raw, annotated, rectified, and overlay artifacts
- keep measurement metadata JSON-safe
- avoid claiming precision beyond calibration quality

Validation:

- compare measurements against known objects
- record calibration source
- record confidence/quality
- keep failed overlays debuggable

## Feature Detection

Goal:

- Detect useful object features beyond the outer bounding box.

Possible features:

- holes
- circular features
- straight edges
- notches
- slots
- labels/markings
- symmetry hints

Constraints:

- feature detection should be diagnostic and tentative at first
- every detected feature needs confidence
- raw and overlay artifacts should be retained

## CAD Automation

Goal:

- Turn measurements and detected features into starter CAD assumptions.

Important boundary:

CAD output is starter geometry, not production-ready geometry.

Expected inputs:

- calibrated measurements
- bounding boxes
- feature detections
- object orientation
- user-provided notes
- project memory

Expected outputs:

- editable dimensions
- assumptions
- TODO comments
- links to source scan IDs/artifacts

## OpenSCAD Generator

Goal:

- Generate simple editable OpenSCAD starter models from measured objects.

Preferred style:

- named parameters
- units documented
- source scan ID included
- assumptions visible
- TODO comments included
- simple primitives before complex geometry

Initial target:

- rectangular plates
- spacers
- brackets
- covers
- simple hole patterns

## STL Generation

Goal:

- Allow starter CAD to become previewable/printable STL artifacts when tooling is available.

Rules:

- STL generation should not imply production readiness.
- Generated models should keep source metadata.
- Failures should return useful errors.
- Local tooling should be preferred.

## Laser/CNC Workflow

Goal:

- Extend measurements and feature detection toward 2D fabrication prep.

Possible workflows:

- outline extraction
- cut/engrave boundary suggestions
- material notes
- scale verification
- export preparation

Constraints:

- no unsafe machine-control automation
- no direct hardware control without a separate safety design
- generated paths must be reviewed by a human

## Multiple Camera Support

Goal:

- Support more than one camera/profile without breaking the current manual overhead workflow.

Architecture direction:

- camera profiles remain explicit
- active profile remains inspectable
- each profile records device, mode, calibration, and limitations
- multiple cameras should not require changing Boot V3

Possible profiles:

- manual overhead Scan Mat camera
- handheld inspection camera
- future fixed side-view camera
- future microscope/detail camera

## Plugin Architecture

Goal:

- Let Jarvis add bounded maker/workshop capabilities without turning the core into a monolith.

Candidate plugin areas:

- OpenSCAD generation
- slicer integrations
- laser prep
- electronics notes
- Raspberry Pi project helpers
- SDR project helpers
- part comparison

Constraints:

- plugins must remain local-first by default
- plugin failures must be visible
- plugin data should be inspectable
- no hidden cloud dependencies

## Future Maker Lab Vision

Maker Lab should become the place where scans, measurements, generated artifacts, and project memory come together.

Expected Maker Lab concepts:

- project workspace
- scan history
- measurement history
- generated OpenSCAD files
- STL artifacts
- notes and assumptions
- part comparison
- repair logs
- electronics/Raspberry Pi/SDR project records

Maker Lab should remain practical and workshop-focused, not a marketing page or generic project dashboard.

## Open Questions

- How should scan history be stored: PostgreSQL, filesystem metadata, or both?
- What minimum calibration confidence should allow measurement overlays?
- Which features should be detected before OpenSCAD generation starts?
- Should overlay artifacts be generated backend-side, frontend-side, or both?
- How should multiple camera profiles be selected in the UI?

## Near-Term Sequence

Recommended order:

1. Phase 2.3B Measurement Overlay.
2. Measurement history schema.
3. Feature detection diagnostics.
4. OpenSCAD starter generator for simple shapes.
5. Maker Lab project workspace.
6. Phase 3 plugin architecture design.
