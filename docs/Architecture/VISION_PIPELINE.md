# Vision Pipeline

Camera
→ Capture
→ OpenCV preprocessing
→ Mat detection
→ Perspective correction
→ Rectified usable-region mask
→ Grid/background suppression
→ Bounded segmentation strategies
→ Contour filtering and consensus scoring
→ Calibrated rotated measurement

The fixed C920 overhead path binds the `workbench` role and logical camera ID
`logitech_c920` to a dedicated profile. Each rectified image carries a JSON
sidecar with stable camera identity, capture negotiation, source geometry,
outer-boundary corners, homography, 1440×1080 output geometry, physical
609.6×457.2 mm mat dimensions, profile ID, timestamp, status, and confidence.
Measurement rejects missing or mismatched provenance; device-node numbering is
deliberately excluded from identity matching. The current provenance contract
validates camera/profile/capture/geometry identity; Accuracy v2 does not compare
newly detected corners with the profile's stored reference corners.
→ Debug mask and overlay
→ Optional Gemma Vision analysis
→ Project memory

Artifacts:
- Raw image
- Annotated image
- Rectified image
- Metadata JSON

Never overwrite source captures.

Measurement is deterministic and single-frame. It uses synthetic regression
tests for dark/light objects, rotation, narrow parts, border cases, grid-only
backgrounds, noise, and uneven lighting. Temporal stabilization is deferred
until measurement history has a safe per-camera persistence boundary.

Known limitations: one primary flat object, contrast-dependent classical vision,
no depth/thickness, no internal-feature metrology, and no production accuracy
claim. Synthetic regressions validate deterministic behavior, but separate
physical ruler/caliper validation remains required.
