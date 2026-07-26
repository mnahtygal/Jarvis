"""Command-line runner for the isolated Grounding DINO experiment."""

import argparse
import json
from pathlib import Path

import torch
from PIL import Image

from .config import ExperimentConfig
from .detector import GroundingDinoDetector
from .inference import detect_with_prompts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run guarded multi-prompt Grounding DINO detection."
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Path to the input image.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/grounded_sam_detection.json"),
        help="Path for the JSON diagnostics.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.image.is_file():
        raise FileNotFoundError(f"Image not found: {args.image}")

    config = ExperimentConfig()
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print(f"Device: {device}")
    print(f"Image: {args.image}")
    print(f"Detector: {config.detector_model_id}")
    print(f"Prompts: {len(config.prompts)}")
    print("Loading image and detector...")

    image = Image.open(args.image)

    detector = GroundingDinoDetector(
        model_id=config.detector_model_id,
        device=device,
        guardrails=config.guardrails,
        box_threshold=config.box_threshold,
        text_threshold=config.text_threshold,
    )

    result = detect_with_prompts(
        detector=detector,
        image=image,
        prompts=config.prompts,
    )

    diagnostics = result.to_dict()
    diagnostics["image"] = str(args.image)
    diagnostics["device"] = str(device)
    diagnostics["model_id"] = config.detector_model_id

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(diagnostics, indent=2),
        encoding="utf-8",
    )

    print(f"Inference time: {result.inference_seconds:.3f} seconds")
    print(f"Candidates: {len(result.candidates)}")

    for index, candidate in enumerate(result.candidates, start=1):
        status = "ACCEPTED" if candidate.accepted else "REJECTED"
        print(
            f"{index:02d}. {status} "
            f"score={candidate.score:.4f} "
            f"area={candidate.area_ratio:.4f} "
            f"prompt={candidate.prompt!r} "
            f"box={candidate.box} "
            f"reasons={candidate.rejection_reasons}"
        )

    if result.selected is None:
        print("Selected candidate: NONE")
        print(f"Diagnostics: {args.output}")
        return 2

    print("Selected candidate:")
    print(json.dumps(result.selected.to_dict(), indent=2))
    print(f"Diagnostics: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
