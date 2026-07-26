"""Rectify fixed-station captures with an already-validated homography."""

import argparse
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .provenance import (
    CalibrationProvenanceError,
    EXPECTED_CAMERA_ROLE,
    EXPECTED_LOGICAL_CAMERA_ID,
    EXPECTED_RECTIFIED_HEIGHT,
    EXPECTED_RECTIFIED_WIDTH,
    EXPECTED_SOURCE_HEIGHT,
    EXPECTED_SOURCE_WIDTH,
    load_and_validate_c920_provenance,
)


def validate_capture_against_reference(
    capture: dict[str, Any],
    reference: dict[str, Any],
) -> None:
    """Reject capture identity/mode mismatches; ignore runtime node number."""

    mismatches = []
    camera = capture.get("camera") or {}
    checks = (
        ("logical_camera_id", camera.get("id"), EXPECTED_LOGICAL_CAMERA_ID),
        ("camera_role", capture.get("role"), EXPECTED_CAMERA_ROLE),
        ("backend", capture.get("backend"), reference.get("backend")),
        ("mode_status", capture.get("mode_status"), "requested"),
        (
            "requested_mode",
            capture.get("requested_mode"),
            reference.get("requested_mode"),
        ),
        (
            "negotiated_mode",
            capture.get("negotiated_mode"),
            reference.get("negotiated_mode"),
        ),
        (
            "stable_camera_identity",
            camera.get("stable_identity"),
            reference.get("stable_camera_identity"),
        ),
    )
    for label, actual, expected in checks:
        if actual != expected:
            mismatches.append(
                f"{label}: expected {expected!r}, received {actual!r}"
            )
    if capture.get("mode_mismatches"):
        mismatches.append(
            f"mode_mismatches: {capture.get('mode_mismatches')!r}"
        )
    if mismatches:
        raise CalibrationProvenanceError(
            "Capture does not match frozen C920 calibration: "
            + "; ".join(mismatches)
        )


def rectify_with_frozen_homography(
    image: np.ndarray,
    reference: dict[str, Any],
) -> np.ndarray:
    if image is None:
        raise ValueError("Source image cannot be None.")
    height, width = image.shape[:2]
    if (width, height) != (EXPECTED_SOURCE_WIDTH, EXPECTED_SOURCE_HEIGHT):
        raise CalibrationProvenanceError(
            "Source geometry mismatch: "
            f"expected {EXPECTED_SOURCE_WIDTH}x{EXPECTED_SOURCE_HEIGHT}, "
            f"received {width}x{height}."
        )
    homography = np.asarray(reference.get("homography"), dtype=np.float64)
    if homography.shape != (3, 3):
        raise CalibrationProvenanceError(
            f"Expected a 3x3 frozen homography; received {homography.shape}."
        )
    return cv2.warpPerspective(
        image,
        homography,
        (EXPECTED_RECTIFIED_WIDTH, EXPECTED_RECTIFIED_HEIGHT),
    )


def frozen_provenance(
    capture: dict[str, Any],
    reference: dict[str, Any],
    *,
    reference_path: Path,
) -> dict[str, Any]:
    result = deepcopy(reference)
    camera = capture.get("camera") or {}
    result.update(
        {
            "created_at": capture.get("captured_at"),
            "runtime_device": capture.get("device"),
            "backend": capture.get("backend"),
            "requested_mode": capture.get("requested_mode"),
            "negotiated_mode": capture.get("negotiated_mode"),
            "mode_status": capture.get("mode_status"),
            "mode_mismatches": capture.get("mode_mismatches") or [],
            "stable_camera_identity": camera.get("stable_identity"),
            "rectification_source": "frozen_calibrated_homography",
            "reference_provenance_path": str(reference_path.resolve()),
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preserve and rectify fixed C920 captures using an existing "
            "validated homography."
        )
    )
    parser.add_argument(
        "--capture-response",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument(
        "--reference-provenance",
        type=Path,
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if len(args.capture_response) != 3:
        raise ValueError("Exactly three capture responses are required.")
    reference = json.loads(
        args.reference_provenance.read_text(encoding="utf-8")
    )
    load_and_validate_c920_provenance(
        args.reference_provenance,
        rectified_width=EXPECTED_RECTIFIED_WIDTH,
        rectified_height=EXPECTED_RECTIFIED_HEIGHT,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for index, response_path in enumerate(args.capture_response, start=1):
        response = json.loads(response_path.read_text(encoding="utf-8"))
        capture = response.get("capture") or {}
        validate_capture_against_reference(capture, reference)
        source_path = Path(capture.get("file_path", ""))
        image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Could not decode source capture: {source_path}")
        rectified = rectify_with_frozen_homography(image, reference)

        raw_path = args.output_dir / source_path.name
        rectified_path = (
            args.output_dir / f"{source_path.stem}_mat_rectified.jpg"
        )
        metadata_path = rectified_path.with_suffix(".metadata.json")
        response_copy = (
            args.output_dir / f"capture_{index:02d}_scan_response.json"
        )
        shutil.copy2(source_path, raw_path)
        shutil.copy2(response_path, response_copy)
        if not cv2.imwrite(str(rectified_path), rectified):
            raise OSError(f"Could not write rectified image: {rectified_path}")
        metadata = frozen_provenance(
            capture,
            reference,
            reference_path=args.reference_provenance,
        )
        metadata_path.write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )
        load_and_validate_c920_provenance(
            metadata_path,
            rectified_width=rectified.shape[1],
            rectified_height=rectified.shape[0],
        )
        print(f"Preserved capture {index}: {raw_path}")
        print(f"Rectified capture {index}: {rectified_path}")
        print(f"Provenance {index}: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
