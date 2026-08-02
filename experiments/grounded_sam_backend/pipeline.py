"""Lazy-loaded saved-image Grounding DINO + SAM2 measurement pipeline."""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any

from core.grounded_sam_contract import grounded_sam_failure, grounded_sam_result

from .candidate import DetectionCandidate, evaluate_candidate, select_candidate
from .config import WorkerModelConfig
from .lifecycle import LoadedModels, ModelLoadFailure
from .mask_measurement import measure_cleaned_mask, validate_and_clean_mask
from .provenance import ProvenanceMismatch, load_validated_provenance


DEPENDENCIES = {
    "torch": "torch",
    "transformers": "transformers",
    "opencv": "opencv-python-headless",
    "numpy": "numpy",
    "pillow": "Pillow",
}


def dependency_probe() -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for label, distribution in DEPENDENCIES.items():
        try:
            versions[label] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[label] = None
    return {"available": all(versions.values()), "versions": versions}


def load_models(config: WorkerModelConfig | None = None) -> LoadedModels:
    """Import and load the ML stack only after an analyze request arrives."""

    settings = config or WorkerModelConfig()
    try:
        import torch
        from transformers import (
            AutoModelForZeroShotObjectDetection,
            AutoProcessor,
            Sam2Model,
            Sam2Processor,
        )
    except ImportError as exc:
        raise ModelLoadFailure("dependency_missing", f"Missing ML dependency: {exc.name}") from exc
    device = "cuda" if settings.device == "auto" and torch.cuda.is_available() else settings.device
    if device == "auto":
        device = "cpu"
    dtype_by_name = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }
    if settings.dtype not in dtype_by_name:
        raise ModelLoadFailure("model_load_failed", f"Unsupported model dtype: {settings.dtype}")
    torch_dtype = dtype_by_name[settings.dtype]
    try:
        detector_processor = AutoProcessor.from_pretrained(
            settings.detector_model_id, local_files_only=settings.local_files_only
        )
        detector_model = AutoModelForZeroShotObjectDetection.from_pretrained(
            settings.detector_model_id, local_files_only=settings.local_files_only
        ).to(device=device, dtype=torch_dtype).eval()
        segmenter_processor = Sam2Processor.from_pretrained(
            settings.segmenter_model_id, local_files_only=settings.local_files_only
        )
        segmenter_model = Sam2Model.from_pretrained(
            settings.segmenter_model_id, local_files_only=settings.local_files_only
        ).to(device=device, dtype=torch_dtype).eval()
    except OSError as exc:
        raise ModelLoadFailure(
            "model_unavailable", "Configured Grounded SAM model files are unavailable locally."
        ) from exc
    except Exception as exc:
        raise ModelLoadFailure("model_load_failed", "Grounded SAM model initialization failed.") from exc
    return LoadedModels(
        value={
            "torch": torch,
            "detector_processor": detector_processor,
            "detector_model": detector_model,
            "segmenter_processor": segmenter_processor,
            "segmenter_model": segmenter_model,
            "config": settings,
        },
        device=str(device),
        dtype=settings.dtype,
        dependency_versions=dependency_probe()["versions"],
    )


def analyze_saved_image(
    *, payload: dict[str, Any], models: LoadedModels,
    allowed_input_root: Path, artifact_root: Path,
    model_load_timing_ms: dict[str, Any],
) -> dict[str, Any]:
    timings: dict[str, float] = {}
    total_started = time.perf_counter()
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return grounded_sam_failure("invalid_prompt", "Worker requires a normalized prompt.")
    prompt = " ".join(prompt.split())
    try:
        image_path = _validated_input_path(payload.get("image_path"), allowed_input_root)
    except FileNotFoundError as exc:
        return grounded_sam_failure("source_image_missing", str(exc), prompt=prompt)
    except ValueError as exc:
        return grounded_sam_failure("source_image_unreadable", str(exc), prompt=prompt)

    decode_started = time.perf_counter()
    try:
        from PIL import Image

        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
            image.load()
    except Exception:
        return grounded_sam_failure(
            "source_image_unreadable", "Worker could not decode the saved source image.",
            source_image={"path": str(image_path)}, prompt=prompt,
        )
    timings["image_decode"] = _elapsed_ms(decode_started)
    width, height = image.size
    source = {
        "path": str(image_path), "sha256": _sha256(image_path),
        "width": width, "height": height,
        "provenance_path": str(payload.get("provenance_path") or ""),
    }
    provenance_started = time.perf_counter()
    try:
        provenance_path = Path(str(payload.get("provenance_path") or ""))
        provenance, calibration = load_validated_provenance(
            image_path, provenance_path, image_width=width, image_height=height
        )
    except FileNotFoundError as exc:
        return grounded_sam_failure(
            "calibration_invalid", str(exc), source_image=source, prompt=prompt,
        )
    except ProvenanceMismatch as exc:
        return grounded_sam_failure(
            "calibration_provenance_mismatch", str(exc),
            source_image=source, prompt=prompt,
        )
    timings["provenance_validation"] = _elapsed_ms(provenance_started)
    source.update({
        "calibration_profile_id": provenance.get("calibration_profile_id"),
        "logical_camera_id": provenance.get("logical_camera_id"),
        "camera_role": provenance.get("camera_role"),
        "geometry_version": provenance.get("geometry_version"),
        "homography_version": provenance.get("homography_version"),
    })

    detection_started = time.perf_counter()
    candidates = _detect(image, prompt, models)
    selection = select_candidate(candidates, guardrails=models.value["config"].guardrails)
    timings["detector"] = _elapsed_ms(detection_started)
    detector = {
        "model": models.value["config"].detector_model_id,
        "box_threshold": models.value["config"].box_threshold,
        "text_threshold": models.value["config"].text_threshold,
        "candidates": [candidate.to_dict() for candidate in selection.candidates],
        "selected_box": list(selection.selected.box) if selection.selected else None,
        "selected_label": selection.selected.label if selection.selected else None,
        "selected_confidence": selection.selected.confidence if selection.selected else None,
    }
    if selection.ambiguous:
        return grounded_sam_failure(
            "ambiguous_detector_candidates", "Multiple similarly strong detector candidates remain.",
            source_image=source, prompt=prompt, detector=detector,
            calibration=calibration, model_load_timing_ms=model_load_timing_ms,
            stage_timings_ms=timings, device=models.device, dtype=models.dtype,
            dependency_versions=models.dependency_versions,
        )
    if selection.selected is None:
        return grounded_sam_failure(
            "no_detector_candidate", "Detector returned no acceptable candidate.",
            source_image=source, prompt=prompt, detector=detector,
            calibration=calibration, model_load_timing_ms=model_load_timing_ms,
            stage_timings_ms=timings, device=models.device, dtype=models.dtype,
            dependency_versions=models.dependency_versions,
        )

    segment_started = time.perf_counter()
    try:
        mask, mask_score, mask_index = _segment(image, selection.selected, models)
    except (ValueError, IndexError) as exc:
        return grounded_sam_failure(
            "invalid_segmentation_mask", str(exc) or "SAM2 returned no usable mask.",
            source_image=source, prompt=prompt, detector=detector,
            segmenter={"model": models.value["config"].segmenter_model_id,
                       "selected_mask_score": None, "selected_mask_index": None,
                       "mask_area_pixels": None},
            calibration=calibration, model_load_timing_ms=model_load_timing_ms,
            stage_timings_ms=timings, device=models.device, dtype=models.dtype,
            dependency_versions=models.dependency_versions,
        )
    timings["segmenter"] = _elapsed_ms(segment_started)
    cleanup_started = time.perf_counter()
    try:
        cleanup = validate_and_clean_mask(mask, expected_shape=(height, width))
    except ValueError as exc:
        return grounded_sam_failure(
            "invalid_segmentation_mask", str(exc), source_image=source, prompt=prompt,
            detector=detector,
            segmenter={"model": models.value["config"].segmenter_model_id,
                       "selected_mask_score": mask_score, "selected_mask_index": mask_index,
                       "mask_area_pixels": None},
            calibration=calibration, model_load_timing_ms=model_load_timing_ms,
            stage_timings_ms=timings, device=models.device, dtype=models.dtype,
            dependency_versions=models.dependency_versions,
        )
    timings["mask_cleanup"] = _elapsed_ms(cleanup_started)
    segmenter = {
        "model": models.value["config"].segmenter_model_id,
        "selected_mask_score": mask_score, "selected_mask_index": mask_index,
        "mask_area_pixels": cleanup.raw_area,
        "cleanup": {
            "raw_area_pixels": cleanup.raw_area, "cleaned_area_pixels": cleanup.cleaned_area,
            "removed_pixels": cleanup.raw_area - cleanup.cleaned_area,
            "kernel_size": 3, "component_decisions": list(cleanup.component_decisions),
        },
    }
    measurement_started = time.perf_counter()
    measurement = measure_cleaned_mask(cleanup, pixels_per_mm=calibration["pixels_per_mm_x"])
    timings["measurement"] = _elapsed_ms(measurement_started)
    artifact_started = time.perf_counter()
    artifacts, artifact_error = _write_artifacts(image, cleanup, artifact_root, image_path.stem)
    timings["artifact_write"] = _elapsed_ms(artifact_started)
    if artifact_error:
        return grounded_sam_failure(
            "artifact_write_failed", artifact_error, source_image=source, prompt=prompt,
            detector=detector, segmenter=segmenter, measurement=measurement,
            calibration=calibration, artifacts=artifacts,
            model_load_timing_ms=model_load_timing_ms, stage_timings_ms=timings,
            device=models.device, dtype=models.dtype,
            dependency_versions=models.dependency_versions,
        )
    timings["total"] = _elapsed_ms(total_started)
    return grounded_sam_result(
        ok=True, status="ready", source_image=source, prompt=prompt,
        detector=detector, segmenter=segmenter, measurement=measurement,
        calibration=calibration, artifacts=artifacts,
        model_load_timing_ms=model_load_timing_ms, stage_timings_ms=timings,
        device=models.device, dtype=models.dtype,
        dependency_versions=models.dependency_versions,
        warnings=[
            "Experimental result; elevated objects are not precision mat-plane measurements."
        ],
        diagnostics={"saved_image_only": True, "real_models_loaded": True},
    )


def _detect(image: Any, prompt: str, models: LoadedModels) -> list[DetectionCandidate]:
    bundle = models.value
    torch = bundle["torch"]
    processor = bundle["detector_processor"]
    inputs = processor(images=image, text=prompt, return_tensors="pt")
    inputs = {name: value.to(models.device) if hasattr(value, "to") else value for name, value in inputs.items()}
    with torch.inference_mode():
        outputs = bundle["detector_model"](**inputs)
    width, height = image.size
    processed = processor.post_process_grounded_object_detection(
        outputs, inputs["input_ids"], threshold=bundle["config"].box_threshold,
        text_threshold=bundle["config"].text_threshold, target_sizes=[(height, width)],
    )[0]
    labels = processed.get("text_labels") or processed.get("labels") or []
    candidates = []
    for index, (box, score) in enumerate(zip(processed.get("boxes", []), processed.get("scores", []))):
        raw_box = box.detach().cpu().tolist() if hasattr(box, "detach") else box
        raw_score = score.detach().cpu().item() if hasattr(score, "detach") else score
        label = str(labels[index]) if index < len(labels) else prompt
        candidates.append(evaluate_candidate(
            box=raw_box, confidence=float(raw_score), label=label, prompt=prompt,
            image_width=width, image_height=height, guardrails=bundle["config"].guardrails,
        ))
    return candidates


def _segment(image: Any, candidate: DetectionCandidate, models: LoadedModels) -> tuple[Any, float, int]:
    bundle = models.value
    torch = bundle["torch"]
    processor = bundle["segmenter_processor"]
    inputs = processor(images=image, input_boxes=[[list(candidate.box)]], return_tensors="pt").to(models.device)
    with torch.inference_mode():
        outputs = bundle["segmenter_model"](**inputs)
    masks = processor.post_process_masks(outputs.pred_masks.cpu(), inputs["original_sizes"].cpu())[0]
    scores = outputs.iou_scores.detach().cpu().reshape(-1)
    index = int(torch.argmax(scores).item())
    score = float(scores[index].item())
    if not math.isfinite(score):
        raise ValueError("SAM2 returned a non-finite mask score.")
    flattened = masks.reshape(-1, masks.shape[-2], masks.shape[-1])
    return flattened[index].to(torch.bool).numpy(), score, index


def _validated_input_path(value: Any, root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FileNotFoundError("Saved source image path is required.")
    path = Path(value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Source image path is outside the worker allow-list.") from exc
    if not path.is_file():
        raise FileNotFoundError(f"Saved source image does not exist: {path}")
    if not path.name.endswith("_mat_rectified.jpg"):
        raise ValueError("Worker accepts only saved *_mat_rectified.jpg artifacts.")
    return path


def _write_artifacts(image: Any, cleanup: Any, root: Path, source_stem: str) -> tuple[dict[str, str], str | None]:
    import cv2
    import numpy as np

    root.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    prefix = root / f"{source_stem}_{token}_grounded_sam"
    paths = {
        "raw_mask_path": prefix.with_name(prefix.name + "_raw_mask.png"),
        "cleaned_mask_path": prefix.with_name(prefix.name + "_cleaned_mask.png"),
        "diagnostic_overlay_path": prefix.with_name(prefix.name + "_overlay.png"),
    }
    written: dict[str, str] = {}
    overlay = np.asarray(image.convert("RGB"))[:, :, ::-1].copy()
    tint = overlay.copy()
    tint[cleanup.cleaned > 0] = (0, 0, 255)
    overlay = cv2.addWeighted(overlay, 0.70, tint, 0.30, 0)
    values = {
        "raw_mask_path": cleanup.raw,
        "cleaned_mask_path": cleanup.cleaned,
        "diagnostic_overlay_path": overlay,
    }
    for name, path in paths.items():
        temporary = path.with_name(f".{path.stem}.tmp{path.suffix}")
        try:
            if not cv2.imwrite(str(temporary), values[name]):
                temporary.unlink(missing_ok=True)
                return written, f"Could not write Grounded SAM artifact: {path.name}"
            os.replace(temporary, path)
            written[name] = str(path)
        except OSError:
            temporary.unlink(missing_ok=True)
            return written, f"Could not write Grounded SAM artifact: {path.name}"
    return written, None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 2)
