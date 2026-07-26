# C920 SIM868 regression fixtures

These are the three successful fixed-overhead Logitech C920 validation
captures from July 26, 2026. They were copied from live Jarvis before the
Grounded SAM experiment was changed.

| Sample | Raw capture | Rectified input |
|---|---|---|
| 1 | `snapshot_20260726_105242.jpg` | `snapshot_20260726_105242_mat_rectified.jpg` |
| 2 | `snapshot_20260726_105303.jpg` | `snapshot_20260726_105303_mat_rectified.jpg` |
| 3 | `snapshot_20260726_105304.jpg` | `snapshot_20260726_105304_mat_rectified.jpg` |

Each rectified image has its original calibration-provenance sidecar, saved
Scan Mat API response, and OpenCV measurement response. The `sam2_raw_mask`
and `sam2_cleaned_mask` PNG files were produced with:

- `IDEA-Research/grounding-dino-base`
- `facebook/sam2-hiera-base-plus`
- prompt: `a SIM868 cellular GPS development board`

The metric scale is derived only from the provenance-backed 609.6 x 457.2 mm
mat and 1440 x 1080 rectified image:

```text
2.3622047244094486 pixels/mm
0.42333333333333334 mm/pixel
```

The caliper dimensions are validation references only. They were not used to
choose the prompt, alter a mask, or derive the scale.
