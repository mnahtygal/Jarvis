# Camera Gimbal Investigation

Last updated: 2026-07-04

## Purpose

This document records current findings about Insta360 Link gimbal control on Thor. It is intentionally diagnostic and does not define any movement commands.

## Current Findings

| Finding | Status |
| --- | --- |
| Camera model | Insta360 Link |
| Capture node | `/dev/video0` |
| Metadata node | `/dev/video1` |
| Driver | `uvcvideo` |
| Format | `1920x1080 / MJPG / 30 fps` |
| Standard V4L2 pan/tilt controls | Present |
| V4L2 values can be changed | Yes |
| Physical gimbal moves from V4L2 pan/tilt | No |
| Insta360 HID interface exposed | No |
| UVC Extension Unit detected | Yes |
| Extension Unit ID | `9` |
| Extension GUID | `faf1672d-b71b-4793-8c91-7b1c9b7f95f8` |
| Extension controls | `11` |

## V4L2 Controls

Standard controls exist:

```text
pan_absolute
tilt_absolute
zoom_absolute
```

Observed behavior:

- values can be read
- values can be set
- setting pan/tilt values does not physically move the Insta360 Link gimbal on Thor

Conclusion:

```text
Standard V4L2 pan/tilt controls are not sufficient for physical gimbal control.
```

## HID Interface

No usable Insta360 HID interface is exposed for gimbal control in the current Thor environment.

Conclusion:

```text
Do not build a HID-based control path unless future diagnostics discover a supported interface.
```

## UVC Extension Unit

Diagnostics indicate a UVC Extension Unit:

```text
Unit ID: 9
GUID: faf1672d-b71b-4793-8c91-7b1c9b7f95f8
Controls: 11
```

Likely conclusion:

```text
Real gimbal movement requires vendor-specific UVC extension-unit commands.
```

## Current Project Decision

Jarvis will not attempt gimbal movement in Phase 2.2B.

Current path:

```text
manual overhead camera positioning
  -> stable scan station
  -> known-good profile
  -> calibration baseline
```

## Future Investigation

Future UVC extension-unit work should:

- identify each vendor-specific control
- document safe read-only probes first
- avoid movement commands until controls are mapped
- require explicit manual approval before physical movement tests
- keep movement code out of Boot V3 and startup scripts

