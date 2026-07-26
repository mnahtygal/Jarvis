"""Configuration for the isolated Grounded SAM experiment."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GroundTruth:
    long_side_mm: float = 65.1
    short_side_mm: float = 30.3


@dataclass(frozen=True)
class DetectorGuardrails:
    minimum_area_ratio: float = 0.0005
    maximum_area_ratio: float = 0.25
    boundary_margin_px: int = 8


@dataclass(frozen=True)
class ExperimentConfig:
    detector_model_id: str = "IDEA-Research/grounding-dino-base"
    segmenter_model_id: str = "facebook/sam2-hiera-base-plus"

    prompts: tuple[str, ...] = (
        "a small blue circuit board.",
        "an electronic circuit board.",
        "a microcontroller development board.",
        "an embedded computer board.",
        "a printed circuit board.",
    )

    box_threshold: float = 0.20
    text_threshold: float = 0.15

    guardrails: DetectorGuardrails = field(
        default_factory=DetectorGuardrails
    )
    ground_truth: GroundTruth = field(default_factory=GroundTruth)
