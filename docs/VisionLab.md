# Vision Lab

Vision Lab is the UI and workflow area for camera, image, vision model, and OpenCV experiments.

## Purpose

Vision Lab helps Jarvis see and understand workshop objects.

It supports the path from image capture to future scan-based CAD generation.

## Current Vision Stack

- Camera capture
- Local vision model analysis
- OpenCV Scan Mat workflow
- Flask API endpoints
- React/Vite display

## Scan Mat Outputs

Each successful scan should eventually produce:

- raw image
- annotated image
- rectified image
- metadata JSON

## Raw Image

The original camera capture.

This is the source of truth and should not be overwritten.

## Annotated Image

An OpenCV output showing detected mat boundaries, corners, contours, object boxes, or other diagnostic overlays.

This image is for debugging and trust-building.

## Rectified Image

A perspective-corrected top-down image of the mat.

This image is the basis for measurement and future OpenSCAD generation.

## Metadata

Scan metadata should include:

- scan ID
- timestamp
- raw image path
- annotated image path
- rectified image path
- mat detection status
- detected corners
- calibration data when available
- errors or warnings

## Development Rule

If the UI does not display what OpenCV is seeing, do not trust the scan pipeline.

