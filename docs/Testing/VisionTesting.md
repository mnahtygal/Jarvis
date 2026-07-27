# Vision Testing

Always preserve:
- Raw image
- Annotated image
- Rectified image

Regression tests should compare image dimensions, detected work area, and calibration accuracy.

Synthetic OpenCV fixtures should cover ordered mat corners, invalid and clipped
mat geometry, grid-only backgrounds, uneven lighting, both threshold polarities,
noise, narrow objects, multiple candidates, cross-strategy consensus, overlapping
distinct contours, the 64-candidate cutoff, score-floor boundaries, artifact
write failures, endpoint status mapping, border rejection, and rotated-object
dimension stability. Verify that `contour_px` remains complete and
`simplified_contour_px` never exceeds 256 points. Keep physical validation
separate and record actual versus reported dimensions and percent error.
