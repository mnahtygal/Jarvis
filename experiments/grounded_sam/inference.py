"""Multi-prompt Grounding DINO inference."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterable

import torch
from PIL import Image

from .detector import (
    DetectionCandidate,
    GroundingDinoDetector,
    evaluate_candidate,
    select_best_candidate,
)


@dataclass(frozen=True)
class DetectionResult:
    selected: DetectionCandidate | None
    candidates: tuple[DetectionCandidate, ...]
    inference_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": (
                self.selected.to_dict()
                if self.selected is not None
                else None
            ),
            "candidates": [
                candidate.to_dict()
                for candidate in self.candidates
            ],
            "inference_seconds": self.inference_seconds,
        }


def _move_inputs_to_device(
    inputs: dict[str, Any],
    device: Any,
) -> dict[str, Any]:
    return {
        name: value.to(device)
        if hasattr(value, "to")
        else value
        for name, value in inputs.items()
    }


def detect_with_prompts(
    *,
    detector: GroundingDinoDetector,
    image: Image.Image,
    prompts: Iterable[str],
) -> DetectionResult:
    """Run each text prompt and select the best guarded candidate."""

    if detector.processor is None or detector.model is None:
        detector.load()

    image = image.convert("RGB")
    image_width, image_height = image.size
    candidates: list[DetectionCandidate] = []

    started = perf_counter()

    for prompt in prompts:
        inputs = detector.processor(
            images=image,
            text=prompt,
            return_tensors="pt",
        )
        inputs = _move_inputs_to_device(inputs, detector.device)

        with torch.inference_mode():
            outputs = detector.model(**inputs)

        processed = (
            detector.processor
            .post_process_grounded_object_detection(
                outputs,
                inputs["input_ids"],
                threshold=detector.box_threshold,
                text_threshold=detector.text_threshold,
                target_sizes=[(image_height, image_width)],
            )
        )[0]

        boxes = processed.get("boxes", [])
        scores = processed.get("scores", [])

        for box, score in zip(boxes, scores):
            if hasattr(box, "detach"):
                box = box.detach().cpu().tolist()

            if hasattr(score, "detach"):
                score = score.detach().cpu().item()

            candidates.append(
                evaluate_candidate(
                    box=box,
                    score=float(score),
                    prompt=prompt,
                    image_width=image_width,
                    image_height=image_height,
                    guardrails=detector.guardrails,
                )
            )

    inference_seconds = perf_counter() - started
    selected = select_best_candidate(candidates)

    return DetectionResult(
        selected=selected,
        candidates=tuple(candidates),
        inference_seconds=inference_seconds,
    )
