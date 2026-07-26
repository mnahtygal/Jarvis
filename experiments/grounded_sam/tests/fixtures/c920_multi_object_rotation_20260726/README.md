# C920 multi-object rotation validation

This directory is reserved for the timestamped Grounded SAM generalization
validation started July 26, 2026.

The completed three-image C920 benchmark remains unchanged in:

```text
../c920_sim868_20260726/
```

## Fixed calibration contract

- Logical camera: `logitech_c920`
- Role: `workbench`
- Stable discovery is authoritative; `/dev/videoN` is never an identity key.
- Requested and negotiated mode: MJPG 1920 x 1080 at 30 FPS
- Rectified output: 1440 x 1080
- Physical mat: 609.6 x 457.2 mm
- Scale: 2.3622047244094486 px/mm
- Profile: `logitech_c920_overhead_scan_mat`
- Geometry: `scan_mat_geometry_v1`
- Homography: `opencv_perspective_outer_boundary_v1`

Captures that do not match this contract must be rejected.

## Planned groups

- `sim868/rotation_000/` — three captures
- `sim868/rotation_030/` — three captures
- `sim868/rotation_060/` — three captures
- `sim868/rotation_090/` — three captures
- `plain_rectangle/rotation_000/` — three captures
- `irregular_object/rotation_000/` — three captures

Each completed capture group will preserve raw, rectified, provenance, raw
SAM2 mask, cleaned mask, diagnostic overlay, and measurement JSON artifacts.

Physical placement is confirmed by the user before each group. Prompts are
recorded before inference and are never chosen using caliper agreement.

## Completed validation

All 18 captures were completed on July 26, 2026:

- SIM868 at approximate 0, 30, 60, and 90 degree rotations, using
  `a SIM868 cellular GPS development board`.
- Golden Corral gift card at 0 degrees, using
  `a Golden Corral gift card`; calipers: 85.45 x 53.67 mm.
- Raspberry Pi NVMe HAT at 0 degrees, using
  `a Raspberry Pi NVMe HAT`; footprint calipers: 87.48 x 55.81 mm;
  maximum height: 16.39 mm.

Each group contains three raw captures, rectified images, capture responses,
provenance sidecars, raw and cleaned masks, overlays, per-sample JSON, and an
aggregate result JSON. The live mat detector returned the known
`no_quadrilateral_candidates` result for these captures, so rectification
used the frozen homography from the already-validated fixed station. Capture
identity and geometry were still validated for every image.

The robust-body estimator met the 1.5 mm within-group range target for every
dimension. It did not meet the full accuracy/generalization criteria:
SIM868 width drift across rotations was 3.267%, and the elevated NVMe HAT
errors were 2.671% length and 4.349% width. The result is therefore
`refine_further`, not a production-trim change or global trim recommendation.
See `capture_plan.json` and each group aggregate for exact values.
