# Jarvis Roadmap

## Phase 1: Foundation — Completed

Completed foundation items:

- Thor environment
- Local LLMs
- PostgreSQL + pgvector
- Brain/router architecture
- React UI
- Voice pipeline
- Vision pipeline
- GitHub synchronization
- Documentation baseline

## Phase 2: Maker & Workshop Assistant — Current

Phase 2 turns Jarvis into a practical engineering partner for the workshop.

### Phase 2A: Scan Mat Stabilization

Status: completed foundation.

Goals:

- Capture raw image.
- Detect the 24 inch wide × 18 inch high grid mat.
- Save annotated image.
- Save rectified top-down image.
- Display all outputs in Vision Lab.
- Store metadata for each scan.

Exit criteria:

- User can capture a scan and see raw, annotated, and rectified outputs in the UI.
- Scan output paths are predictable.
- Failures are visible and understandable.

### Phase 2B: Calibration and Measurement

Status: active. Calibration and bounding-box measurement foundations exist;
automatic object measurement, overlays, and validation are next.

Goals:

- Use mat dimensions for pixel-to-inch/mm conversion.
- Estimate calibration quality.
- Add measurement overlays.
- Support basic object dimensions.
- Store measurement metadata.
- Validate measurements against known reference objects.
- Add OCR for labels, markings, and dimensions.

Exit criteria:

- Jarvis can produce useful first-pass measurements from rectified images.
- Measurement output includes assumptions and confidence indicators.

### Phase 2C: Scan History and Project Memory

Goals:

- Store scan records.
- Associate scans with projects.
- Persist notes and generated artifacts.
- Search prior scans and projects.

Exit criteria:

- Marty can return to a prior part/project and see scan history, notes, images, and generated files.

### Phase 2D: OpenSCAD Starter Generation

Goals:

- Generate starter OpenSCAD files from measured scans.
- Use editable parameters.
- Include source scan IDs and assumptions.
- Provide preview-ready simple geometry.
- Support a conservative scan-to-reverse-engineering workflow.

Exit criteria:

- Jarvis can generate a simple editable OpenSCAD starting point from a scan.

### Phase 2E: Maker Lab

Status: planned after measurement inputs are trustworthy.

Goals:

- Add Maker Lab UI area.
- Support 3D printing workflows.
- Support laser engraving notes/settings.
- Support electronics and Raspberry Pi build logs.
- Support SDR project notes.

Exit criteria:

- Jarvis becomes a project workspace, not just a chat interface.

## Phase 3: Practical Agentic Workflows

Only after Phase 2 is stable.

Possible workflows:

- Guided repair sessions
- Part comparison
- Scan-to-model workflows
- Automated documentation generation
- Local code maintenance tasks
- Optional camera positioning
- Optional hardware control

## Deferred Until Later

Do not prioritize yet:

- Cloud sync
- Mobile app
- robotics
- autonomous camera movement
- complex multi-agent orchestration
- replacing the UI framework
- replacing PostgreSQL memory
