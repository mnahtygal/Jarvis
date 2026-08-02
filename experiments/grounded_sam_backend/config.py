"""Runtime configuration without validation ground truth or fixed prompts."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DetectorGuardrails:
    minimum_area_ratio: float = 0.0005
    maximum_area_ratio: float = 0.25
    boundary_margin_px: int = 8
    ambiguity_score_delta: float = 0.025
    duplicate_iou_threshold: float = 0.72


@dataclass(frozen=True)
class WorkerModelConfig:
    detector_model_id: str = "IDEA-Research/grounding-dino-base"
    segmenter_model_id: str = "facebook/sam2-hiera-base-plus"
    box_threshold: float = 0.20
    text_threshold: float = 0.15
    device: str = "auto"
    dtype: str = "float32"
    local_files_only: bool = True
    guardrails: DetectorGuardrails = field(default_factory=DetectorGuardrails)
