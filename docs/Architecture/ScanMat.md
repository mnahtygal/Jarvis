# Scan Mat Architecture

## Purpose
Scan Mat mode turns a known 18 x 24 inch grid mat into a calibrated workspace for detecting, measuring, and eventually modeling physical parts.

## Current Workflow
- Capture image
- Run OpenCV mat detection
- Run local vision analysis
- Return scan results

## Phase 2A Target
- Save raw image
- Save annotated image
- Save rectified top-down image
- Display all three in Vision Lab

## Phase 2B Target
- Calibrate pixels to inches/mm
- Detect grid spacing
- Measure objects
- Persist scan metadata

## Phase 2C Target
- Generate OpenSCAD starter models from measured geometry

## Safety Rule
Never claim accurate measurements until calibration is complete and visible to the user.
