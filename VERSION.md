# VERSION.md

# Jarvis Version History

This document tracks major project milestones rather than individual Git commits.

---

# Current Snapshot

**Version:** 2.3.0-dev

**Codename:** Measurement Validation

**Sprint:** Phase 2 Maker & Workshop Assistant

**Status:** Phase 2 active

Vision and Scan Mat foundations stable; measurement refinement in progress

## Platform

- Ubuntu 24.04 LTS
- NVIDIA Jetson AGX Thor
- Python
- Flask
- React
- TypeScript
- Vite
- PostgreSQL
- pgvector
- llama.cpp

## Current Milestone

Vision Lab multi-camera and Scan Mat stabilization complete

## Next Milestone

Phase 2.3B  
Automatic object measurement, overlays, and validation

---

# Version 2.1.0
**Status:** Complete

## Phase
Phase 2 – Professional Architecture

## Completed
### Foundation
- ✅ Jetson AGX Thor development environment
- ✅ Local llama.cpp model serving
- ✅ Qwen3 30B (Text)
- ✅ Gemma 3 4B Vision
- ✅ Flask API
- ✅ React/Vite Dashboard
- ✅ PostgreSQL + pgvector memory
- ✅ Voice pipeline
- ✅ Vision pipeline
- ✅ GitHub integration
- ✅ Comprehensive documentation

### Vision Lab
- ✅ Camera capture
- ✅ Local vision analysis
- ✅ Scan Mat Mode
- ✅ OpenCV mat detection
- ✅ Perspective correction
- ✅ Raw image display
- ✅ Annotated image display
- ✅ Rectified image display

### Engineering
- ✅ AGENTS.md
- ✅ Architecture documentation
- ✅ ADRs (Architecture Decision Records)
- ✅ CODEX_PROMPTS.md
- ✅ Standard AI-assisted development workflow

### Professional Architecture
- ✅ Boot V3 startup system
- ✅ Ubuntu autostart environment
- ✅ Mission Control dashboard
- ✅ React pages architecture
- ✅ Shared component architecture
- ✅ Custom hooks architecture
- ✅ Frontend services layer
- ✅ Frontend configuration layer
- ✅ Repository cleanup
- ✅ Documentation Sprint 1.0
- ✅ Professional Git workflow
- ✅ VS Code + Codex development workflow

---

# Version 2.2.0
**Status:** Complete

## Calibration Engine
- ✅ 2.2A Camera Diagnostics & Config Fix
- ✅ 2.2B Manual Overhead Scan Mat Stabilization
- ✅ 2.2C UVC Extension Unit Investigation
- ✅ Calibration engine foundation
- ✅ Calibration API
- ✅ Calibration profile storage
- ✅ Interactive calibration UI
- ✅ Pixel-to-mm conversion
- ✅ Calibration confidence score
- ☐ Calibration overlay

---

# Version 2.3.0
**Status:** In Progress

## Measurement Engine
- ✅ 2.3A Measurement Engine foundation
- ✅ Measurement API
- ✅ Vision Lab measurement UI
- ✅ Bounding-box measurement v0
- ✅ Vision Lab multi-camera selector
- ✅ Role-based Logitech C920 workbench camera
- ✅ Role-based Insta360 Link face camera
- ✅ Dynamic V4L2 camera resolution
- ✅ Samson Q2U PipeWire preference
- ✅ Scan Mat stabilization at 609.6 × 457.2 mm
- ✅ Reliable API/UI restart lifecycle with API readiness checks
- ☐ 2.3B Measurement Overlay
- ☐ Automatic object isolation and measurement refinement
- ☐ Measurement validation against known objects
- ☐ Diameter estimation
- ☐ Measurement history

## Sprint Completed
- ✅ React pages/components/hooks/services/config structure
- ✅ Professional frontend architecture
- ✅ API service layer
- ✅ Hook extraction for dashboard, API health, calibration, and measurement
- ✅ Mission Control read-only operations view
- ✅ Vision Lab calibration, diagnostics, and measurement workflow
- ✅ Camera diagnostics and manual scan station profile
- ✅ Insta360 Link UVC Extension Unit investigation documented
- ✅ Scan Mat diagnostics

---

# Version 2.4.0
**Status:** Planned

## OpenSCAD Generation
- ☐ Primitive detection
- ☐ Parameter extraction
- ☐ Starter OpenSCAD generation
- ☐ Editable model output

---

# Version 2.5.0
**Status:** Planned

## Maker Lab
- ☐ Project workspace
- ☐ Scan history
- ☐ Project memory
- ☐ CAD comparison
- ☐ Export workflows

---

# Version 3.0.0
**Status:** Vision

## Engineering Assistant
- Local software engineering assistant
- Electronics assistant
- Raspberry Pi assistant
- 3D printing assistant
- Laser engraving assistant
- SDR assistant
- Data engineering assistant
- GM engineering toolkit

---

## Release Philosophy

Every milestone should meet the following criteria before release:

- Feature implemented
- Documentation updated
- Validation completed
- Manual testing on Thor
- Git review completed
- Clean commit history
- GitHub synchronized

---

*"Architect with ChatGPT.

Build with Codex.

Validate on Thor.

Document everything."*
