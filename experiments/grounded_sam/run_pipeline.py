"""Run Grounding DINO detection followed by SAM 2 segmentation."""

import argparse
import json
from pathlib import Path

import torch
from PIL import Image

from .config import ExperimentConfig
from .detector import GroundingDinoDetector
from .inference import detect_with_prompts
from .segmenter import Sam2Segmenter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the isolated Grounded SAM pipeline."
    )
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/grounded_sam_pipeline"),
    )
    return parser.parse_args()


def save_visuals(
    *,
    image: Image.Image,
    mask: torch.Tensor,
    output_dir: Path,
) -> None:
    mask_image = Image.fromarray(
        mask.detach().cpu().numpy().astype("uint8") * 255,
        mode="L",
    )
    mask_image.save(output_dir / "mask.png")

    base = image.convert("RGBA")
    red_layer = Image.new("RGBA", base.size, (255, 0, 0, 0))
    red_layer.putalpha(mask_image.point(lambda value: 110 if value else 0))

    overlay = Image.alpha_composite(base, red_layer)
    overlay.save(output_dir / "overlay.png")


def main() -> int:
    args = parse_args()

    if not args.image.is_file():
        raise FileNotFoundError(f"Image not found: {args.image}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    config = ExperimentConfig()
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    image = Image.open(args.image).convert("RGB")

    print(f"Device: {device}")
    print(f"Image: {args.image}")
    print("Running Grounding DINO...")

    detector = GroundingDinoDetector(
        model_id=config.detector_model_id,
        device=device,
        guardrails=config.guardrails,
        box_threshold=config.box_threshold,
        text_threshold=config.text_threshold,
    )

    detection = detect_with_prompts(
        detector=detector,
        image=image,
        prompts=config.prompts,
    )

    if detection.selected is None:
        print("No accepted DINO candidate; SAM 2 was not run.")
        return 2

    print(
        f"Selected DINO candidate: "
        f"score={detection.selected.score:.4f} "
        f"box={detection.selected.box}"
    )
    print("Running SAM 2...")

    segmenter = Sam2Segmenter(
        model_id=config.segmenter_model_id,
        device=device,
    )

    segmentation = segmenter.segment(
        image=image,
        candidate=detection.selected,
    )

    save_visuals(
        image=image,
        mask=segmentation.mask,
        output_dir=args.output_dir,
    )

    diagnostics = {
        "image": str(args.image),
        "device": str(device),
        "detector_model_id": config.detector_model_id,
        "segmenter_model_id": config.segmenter_model_id,
        "detection": detection.to_dict(),
        "segmentation": segmentation.diagnostics(),
    }

    diagnostics_path = args.output_dir / "diagnostics.json"
    diagnostics_path.write_text(
        json.dumps(diagnostics, indent=2),
        encoding="utf-8",
    )

    print(
        f"SAM score: {segmentation.score:.4f}\n"
        f"Mask index: {segmentation.mask_index}\n"
        f"Mask area: {segmentation.mask_area_pixels} pixels\n"
        f"SAM inference: {segmentation.inference_seconds:.3f} seconds"
    )
    print(f"Mask: {args.output_dir / 'mask.png'}")
    print(f"Overlay: {args.output_dir / 'overlay.png'}")
    print(f"Diagnostics: {diagnostics_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
