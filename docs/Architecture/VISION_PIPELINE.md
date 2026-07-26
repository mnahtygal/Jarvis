# Vision Pipeline

Camera
→ Capture
→ OpenCV preprocessing
→ Mat detection
→ Perspective correction

The fixed C920 overhead path binds the `workbench` role and logical camera ID
`logitech_c920` to a dedicated profile. Each rectified image carries a JSON
sidecar with stable camera identity, capture negotiation, source geometry,
outer-boundary corners, homography, 1440×1080 output geometry, physical
609.6×457.2 mm mat dimensions, profile ID, timestamp, status, and confidence.
Measurement rejects missing or mismatched provenance; device-node numbering is
deliberately excluded from identity matching.
→ Gemma Vision analysis
→ Measurements
→ Project memory

Artifacts:
- Raw image
- Annotated image
- Rectified image
- Metadata JSON

Never overwrite source captures.
