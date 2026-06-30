# Vision Architecture

## Purpose
The vision system lets Jarvis understand images from cameras, uploaded files, and workshop scans.

## Current Components
- Camera capture
- Local vision model
- Vision Lab UI
- OpenCV processing
- Scan Mat workflow

## Design Rules
- Always preserve raw images
- Save derived images separately
- Keep OpenCV outputs inspectable
- Do not trust measurement until calibration exists
- Prefer deterministic image processing before model interpretation

## Phase 2 Priority
Finish Scan Mat v1.1, then add calibration and measurement.
