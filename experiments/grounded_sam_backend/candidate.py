"""Grounding DINO candidate filtering, deduplication, and ambiguity policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .config import DetectorGuardrails


@dataclass(frozen=True)
class DetectionCandidate:
    box: tuple[float, float, float, float]
    confidence: float
    label: str
    prompt: str
    area_ratio: float
    touches_boundary: bool
    accepted: bool
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateSelection:
    selected: DetectionCandidate | None
    candidates: tuple[DetectionCandidate, ...]
    ambiguous: bool


def evaluate_candidate(
    *, box: Iterable[float], confidence: float, label: str, prompt: str,
    image_width: int, image_height: int, guardrails: DetectorGuardrails,
) -> DetectionCandidate:
    values = tuple(float(value) for value in box)
    if len(values) != 4:
        raise ValueError("Detector boxes must contain exactly four coordinates.")
    x1, y1, x2, y2 = values
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    image_area = float(image_width * image_height)
    area_ratio = (width * height) / image_area if image_area else 0.0
    margin = guardrails.boundary_margin_px
    touches_boundary = (
        x1 <= margin or y1 <= margin
        or x2 >= image_width - margin or y2 >= image_height - margin
    )
    reasons = []
    if x2 <= x1 or y2 <= y1:
        reasons.append("invalid_box_geometry")
    if area_ratio < guardrails.minimum_area_ratio:
        reasons.append("area_too_small")
    if area_ratio > guardrails.maximum_area_ratio:
        reasons.append("area_too_large")
    if touches_boundary:
        reasons.append("touches_image_boundary")
    return DetectionCandidate(
        box=values, confidence=float(confidence), label=label, prompt=prompt,
        area_ratio=area_ratio, touches_boundary=touches_boundary,
        accepted=not reasons, rejection_reasons=tuple(reasons),
    )


def box_iou(first: DetectionCandidate, second: DetectionCandidate) -> float:
    ax1, ay1, ax2, ay2 = first.box
    bx1, by1, bx2, by2 = second.box
    width = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    height = max(0.0, min(ay2, by2) - max(ay1, by1))
    intersection = width * height
    first_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    second_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def select_candidate(
    candidates: Iterable[DetectionCandidate], *, guardrails: DetectorGuardrails,
) -> CandidateSelection:
    all_candidates = tuple(candidates)
    accepted = sorted(
        (candidate for candidate in all_candidates if candidate.accepted),
        key=lambda candidate: candidate.confidence, reverse=True,
    )
    deduplicated: list[DetectionCandidate] = []
    for candidate in accepted:
        if not any(
            box_iou(candidate, existing) >= guardrails.duplicate_iou_threshold
            for existing in deduplicated
        ):
            deduplicated.append(candidate)
    if not deduplicated:
        return CandidateSelection(None, all_candidates, False)
    ambiguous = (
        len(deduplicated) > 1
        and deduplicated[0].confidence - deduplicated[1].confidence
        <= guardrails.ambiguity_score_delta
    )
    return CandidateSelection(None if ambiguous else deduplicated[0], all_candidates, ambiguous)
