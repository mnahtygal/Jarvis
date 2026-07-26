# Grounded SAM metric measurement experiment

## Status

This experiment evaluates Grounding DINO, SAM2, component-aware mask cleanup,
and calibrated metric measurement without integrating them into live Jarvis.
The completed C920 validation uses the fixed
`logitech_c920_overhead_scan_mat` profile, 1920 x 1080 MJPG capture, a
1440 x 1080 rectified image, and a 24 x 18-inch physical mat.

The production measurement implementation and production trim default remain
unchanged.

## Measurement outputs

The experiment deliberately reports two different geometries:

- **Maximum occupied envelope** measures the full cleaned silhouette,
  including connectors, mounting tabs, and other legitimate extensions.
- **Robust body** estimates the main occupied body from mask cross-sections in
  principal-axis coordinates. It reduces sensitivity to local protrusions but
  does not redefine the visible silhouette or force agreement with calipers.

These outputs are not interchangeable. Callers must preserve their names and
meaning instead of presenting the robust body as an exact outside envelope.

## Physical-validation conclusion

Planar and low-profile measurement is promising. The Golden Corral gift card
met the two-percent mean-error target on both dimensions, and every robust
group in the 18-image validation set met the 1.5 mm within-group range target.
Grounded SAM also materially improved fixed-pose width repeatability over the
existing OpenCV benchmark.

The complete result is not yet suitable for general production measurement:

- SIM868 width means drifted 3.267 percent across the approximate rotations.
- The 16.39 mm-tall Raspberry Pi NVMe HAT was repeatable but measured
  2.671 percent long and 4.349 percent wide.

The C920 homography maps the physical mat plane. Elevated-object visible
silhouettes include height-dependent perspective, sidewalls, and lighting
boundaries that do not lie on that plane. A stable segmentation of that
silhouette therefore does not establish a precise mat-plane footprint.
Changing trim to match an elevated object's calipers would be calibration by
ground truth and is not an acceptable correction.

Elevated objects must not receive mat-plane precision claims. Until a
height-aware projection or independently validated contact-footprint method
exists, the appropriate result is a structured limitation or rejection.

The recommendation from this validation is **refine further**:

1. Keep maximum envelope and robust body as distinct outputs.
2. Classify planar/low-profile and elevated measurement cases.
3. Develop height-aware projection from camera intrinsics/extrinsics or obtain
   depth/another view for mixed-height objects.
4. Use lighting and segmentation that distinguish the mat-contact footprint
   from elevated visible silhouette and shadow.
5. Validate refinements without using caliper dimensions to tune geometry.

## Regression evidence

The timestamped validation record is in
`tests/fixtures/c920_multi_object_rotation_20260726/`. Its manifest records
the prompts, calibration contract, acceptance results, and per-group artifact
locations. Per-sample JSON records detector and SAM confidence, component
decisions, principal-axis angle, both measurement geometries, provenance, and
timings.

The raw masks are the canonical deterministic measurement inputs. Cleaned
masks verify component cleanup. Raw captures, rectified images, capture
responses, and provenance sidecars cover the capture-to-metric-space contract.
Diagnostic overlays are reproducible presentation artifacts and are not
required to recompute measurements.
