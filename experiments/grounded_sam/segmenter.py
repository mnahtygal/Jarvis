"""SAM 2 box-prompted image segmentation."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import torch
from PIL import Image

from .detector import DetectionCandidate


@dataclass(frozen=True)
class SegmentationResult:
    """Best SAM 2 mask and its diagnostics."""

    mask: torch.Tensor
    score: float
    mask_index: int
    mask_area_pixels: int
    inference_seconds: float

    def diagnostics(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "mask_index": self.mask_index,
            "mask_area_pixels": self.mask_area_pixels,
            "mask_height": int(self.mask.shape[-2]),
            "mask_width": int(self.mask.shape[-1]),
            "inference_seconds": self.inference_seconds,
        }


class Sam2Segmenter:
    """Lazy-loading SAM 2 adapter for box-prompted segmentation."""

    def __init__(
        self,
        *,
        model_id: str,
        device: Any,
    ) -> None:
        self.model_id = model_id
        self.device = device
        self.processor = None
        self.model = None

    def load(self) -> None:
        """Load SAM 2 only when segmentation is requested."""

        from transformers import Sam2Model, Sam2Processor

        self.processor = Sam2Processor.from_pretrained(
            self.model_id
        )
        self.model = (
            Sam2Model.from_pretrained(self.model_id)
            .to(self.device)
            .eval()
        )

    def segment(
        self,
        *,
        image: Image.Image,
        candidate: DetectionCandidate,
    ) -> SegmentationResult:
        """Segment the object inside an accepted DINO box."""

        if not candidate.accepted:
            raise ValueError(
                "SAM 2 requires an accepted detection candidate."
            )

        if self.processor is None or self.model is None:
            self.load()

        image = image.convert("RGB")
        input_boxes = [[list(candidate.box)]]

        inputs = self.processor(
            images=image,
            input_boxes=input_boxes,
            return_tensors="pt",
        ).to(self.device)

        started = perf_counter()

        with torch.inference_mode():
            outputs = self.model(**inputs)

        masks = self.processor.post_process_masks(
            outputs.pred_masks.cpu(),
            inputs["original_sizes"].cpu(),
        )[0]

        scores = outputs.iou_scores.detach().cpu()

        flat_scores = scores.reshape(-1)
        best_index = int(torch.argmax(flat_scores).item())
        best_score = float(flat_scores[best_index].item())

        flat_masks = masks.reshape(
            -1,
            masks.shape[-2],
            masks.shape[-1],
        )
        best_mask = flat_masks[best_index].to(torch.bool)

        inference_seconds = perf_counter() - started

        return SegmentationResult(
            mask=best_mask,
            score=best_score,
            mask_index=best_index,
            mask_area_pixels=int(best_mask.sum().item()),
            inference_seconds=inference_seconds,
        )
