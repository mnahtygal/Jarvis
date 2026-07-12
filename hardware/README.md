# Jarvis Hardware Workspace

This directory keeps inspectable workshop hardware notes and design artifacts.
OpenSCAD source files are the editable design records; STL files preserve
printable revisions and are not substitutes for source geometry.

## Current Camera Architecture

- Logitech HD Pro Webcam C920: fixed `workbench` camera for Vision Lab and Scan Mat
- Insta360 Link: `face` camera; retained independently from the workbench station
- Camera roles are resolved by V4L2 device name; `/dev/video*` numbers are not permanent
- Samson Q2U: preferred microphone, resolved by stable PipeWire name

## Contents

- [`openscad/`](openscad/README.md): camera-mount OpenSCAD and STL revisions
- [`docs/`](docs/hardware_design.md): hardware design, bill of materials, and printing notes

The current workbench mat is 24 inches wide × 18 inches high
(609.6 × 457.2 mm). Camera mounting and calibration should remain fixed while
validating measurements.
