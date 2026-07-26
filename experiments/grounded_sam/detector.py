"""Grounding DINO detection and candidate guardrails."""

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .config import DetectorGuardrails


@dataclass(frozen=True)
class DetectionCandidate:
    box: tuple[float, float, float, float]
    score: float
    prompt: str
    area_ratio: float
    touches_boundary: bool
    accepted: bool
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_candidate(
    *,
    box: Iterable[float],
    score: float,
    prompt: str,
    image_width: int,
    image_height: int,
    guardrails: DetectorGuardrails,
) -> DetectionCandidate:
    """Evaluate a detector result before it can be sent to SAM."""

    x1, y1, x2, y2 = (float(value) for value in box)

    box_width = max(0.0, x2 - x1)
    box_height = max(0.0, y2 - y1)
    image_area = float(image_width * image_height)
    area_ratio = (box_width * box_height) / image_area

    margin = guardrails.boundary_margin_px
    touches_boundary = (
        x1 <= margin
        or y1 <= margin
        or x2 >= image_width - margin
        or y2 >= image_height - margin
    )

    reasons: list[str] = []

    if x2 <= x1 or y2 <= y1:
        reasons.append("invalid_box_geometry")

    if area_ratio < guardrails.minimum_area_ratio:
        reasons.append("area_too_small")

    if area_ratio > guardrails.maximum_area_ratio:
        reasons.append("area_too_large")

    if touches_boundary:
        reasons.append("touches_image_boundary")

    return DetectionCandidate(
        box=(x1, y1, x2, y2),
        score=float(score),
        prompt=prompt,
        area_ratio=area_ratio,
        touches_boundary=touches_boundary,
        accepted=not reasons,
        rejection_reasons=tuple(reasons),
    )


def select_best_candidate(
    candidates: Iterable[DetectionCandidate],
) -> DetectionCandidate | None:
    """Return the highest-scoring accepted candidate."""

    accepted = [
        candidate for candidate in candidates
        if candidate.accepted
    ]

    if not accepted:
        return None

    return max(accepted, key=lambda candidate: candidate.score)


class GroundingDinoDetector:
    """Lazy-loading Grounding DINO adapter."""

    def __init__(
        self,
        *,
        model_id: str,
        device: Any,
        guardrails: DetectorGuardrails,
        box_threshold: float,
        text_threshold: float,
    ) -> None:
        self.model_id = model_id
        self.device = device
        self.guardrails = guardrails
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        self.processor = None
        self.model = None

    def load(self) -> None:
        """Load the processor and model only when needed."""

        from transformers import (
            AutoModelForZeroShotObjectDetection,
            AutoProcessor,
        )

        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.model = (
            AutoModelForZeroShotObjectDetection
            .from_pretrained(self.model_id)
            .to(self.device)
            .eval()
        )
