# Jarvis Vision

Last updated: 2026-07-04

## What Is Jarvis?

Jarvis is a local-first AI engineering assistant for software development, workshop projects, 3D printing, laser engraving, electronics, Raspberry Pi builds, SDR, data engineering, and practical maker work.

Jarvis is not just a chatbot. It is a local AI workbench that combines:

- local language models
- local vision models
- voice input/output
- PostgreSQL memory
- pgvector semantic memory
- camera workflows
- Scan Mat analysis
- calibration
- bounding-box measurement foundations
- a React operations dashboard
- command-line startup and health tools

## Why Jarvis Exists

Jarvis exists to make a local workstation feel like an intelligent engineering partner while keeping control, data, and tooling on the user's own machine.

The project is built for tasks where context matters:

- remembering project decisions
- inspecting parts and workbench images
- debugging local systems
- writing code
- documenting experiments
- generating starter maker artifacts
- keeping a long-running workshop assistant recoverable

## Problems Jarvis Solves

Jarvis is intended to help with:

- local software engineering workflows
- camera-based inspection and documentation
- Scan Mat capture and measurement foundations
- interactive calibration
- object bounding-box measurement from rectified scans
- maker project memory
- local model experimentation
- voice-driven assistant workflows
- operational visibility into a local AI stack

## Who Jarvis Is For

Jarvis is for builders who want an AI assistant that can live with their tools:

- software engineers
- makers
- 3D printing users
- electronics hobbyists
- Raspberry Pi builders
- data engineers
- local AI experimenters
- workshop owners who need practical project memory

## Why Local-First?

Local-first is a core principle, not a convenience.

Local operation means:

- private project data stays local
- camera captures stay local
- memory stays inspectable
- model behavior can be debugged
- the system can keep working without cloud services
- hardware and workflow assumptions are explicit

Cloud services may be useful in some projects, but Jarvis should not depend on them unless explicitly requested.

## How Jarvis Differs From ChatGPT, Claude, Gemini, and Copilot

Jarvis is not trying to compete as a general cloud assistant. Its value is different.

| Jarvis | Cloud assistants |
| --- | --- |
| Runs locally | Run remotely |
| Uses local files, devices, and models | Use provider infrastructure |
| Has project/workshop memory in PostgreSQL | Usually session/account memory |
| Can inspect local camera workflows | Usually detached from local hardware |
| Has boot, status, and recovery scripts | Hidden operations |
| Designed for a specific workstation and maker lab | Designed for broad general use |

Jarvis can use ideas from cloud assistants, but it should remain understandable, modular, and locally recoverable.

## Guiding Principles

- Local-first.
- Offline-capable where practical.
- Modular.
- Maintainable.
- Understandable.
- Testable.
- Recoverable.
- GitHub-synchronized.
- Boring, reliable code over clever code.
- Useful failures over hidden failures.
- Proven calibration before measurement claims.

## Long-Term Vision

The long-term vision is a personal AI operating system for engineering and making:

- a local assistant that can talk, see, remember, and help build
- a maker lab that connects scans, notes, measurements, and generated starter models
- a memory system that records useful project context
- a dashboard that makes the local AI stack visible and recoverable
- practical agentic workflows for engineering tasks

Jarvis should become a trustworthy local companion for repeated work, not a novelty demo.

## Current Vision Foundation

The July 3-4 development sprint moved Jarvis from a promising Vision Lab prototype toward a real workshop foundation.

Completed foundations:

- Professional React architecture with pages, components, hooks, services, config, and types.
- Mission Control as a read-only operations view.
- Vision Lab as the primary camera, Scan Mat, calibration, diagnostics, and measurement workspace.
- Camera diagnostics and manual overhead scan station profile.
- UVC Extension Unit investigation for the Insta360 Link.
- Calibration engine, API, profile storage, and interactive calibration UI.
- Scan Mat diagnostics for understanding detection success and failure.
- Measurement Engine foundation with bounding-box measurement v0.

The next practical step is Phase 2.3B Measurement Overlay: showing bounding boxes and measurement labels directly on rectified Scan Mat artifacts.

## Known Camera Limitations

Jarvis currently assumes the Insta360 Link is manually positioned overhead for Scan Mat work.

Known findings:

- `/dev/video0` is the video capture node.
- `/dev/video1` is the metadata node.
- Standard V4L2 pan/tilt controls exist and accept values.
- Those controls do not physically move the Insta360 Link gimbal on Thor.
- No Insta360 HID interface is exposed.
- A UVC Extension Unit exists and likely controls vendor-specific gimbal behavior.

Gimbal automation is not part of the current workflow. Manual overhead mode remains the stable path until vendor-specific UVC extension commands are mapped.

## Phase 3 Direction

Phase 3 planning should build on the Vision Foundation:

- Measurement Overlay.
- Feature Detection.
- CAD Automation.
- OpenSCAD Generator.
- STL Generation.
- Laser/CNC workflow.
- Multiple camera support.
- Plugin architecture.
- Future Maker Lab vision.

## Intentionally Out Of Scope

For the current phase, Jarvis should not prioritize:

- cloud sync
- robotics
- uncontrolled automation
- production CAD claims
- replacing PostgreSQL + pgvector
- large UI framework rewrites
- complex autonomous agents
- hidden startup behavior
- restart/shutdown controls in Mission Control

Those may be revisited later, but only after Scan Mat, Vision Lab, memory, and Maker Lab foundations are stable.
