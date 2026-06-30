# Maker Lab

Maker Lab is the future workspace for Jarvis-assisted physical projects.

## Purpose

Maker Lab should help Marty build, repair, measure, document, and generate starter files for real workshop projects.

## Target Workflows

- 3D printing
- OpenSCAD starter generation
- laser engraving prep
- electronics project notes
- Raspberry Pi builds
- SDR experiments
- repair documentation
- part comparison

## Relationship to Vision Lab

Vision Lab captures and processes visual data.

Maker Lab uses that data to create useful project artifacts.

Example flow:

```text
Capture part
  ↓
Detect mat
  ↓
Rectify image
  ↓
Calibrate measurement
  ↓
Create project record
  ↓
Generate OpenSCAD starter model
  ↓
Iterate with real caliper measurements
```

## OpenSCAD Starter Files

Generated OpenSCAD should be editable and assumption-driven.

It should include:

- source scan ID
- units
- parameters
- rough dimensions
- assumptions
- TODO notes

## Project Memory

Maker Lab should remember:

- project name
- related scans
- notes
- generated files
- print settings
- laser settings
- parts used
- next steps

