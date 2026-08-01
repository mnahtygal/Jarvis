#!/usr/bin/env python3
"""Launch the isolated Grounded SAM worker under its dedicated environment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.grounded_sam_backend.lifecycle import ModelRegistry
from experiments.grounded_sam_backend.pipeline import (
    analyze_saved_image,
    dependency_probe,
    load_models,
)
from experiments.grounded_sam_backend.service import serve
from experiments.grounded_sam_backend.worker import GroundedSamWorker

def _configured_paths() -> tuple[Path, Path]:
    payload = json.loads((PROJECT_ROOT / "config" / "vision_backends.json").read_text())
    config = payload["backends"]["grounded_sam"]
    return (
        (PROJECT_ROOT / config["allowed_input_root"]).resolve(),
        (PROJECT_ROOT / config["artifact_root"]).resolve(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8092)
    args = parser.parse_args()
    input_root, artifact_root = _configured_paths()
    worker = GroundedSamWorker(
        registry=ModelRegistry(load_models), analyzer=analyze_saved_image,
        allowed_input_root=input_root, artifact_root=artifact_root,
        dependency_probe=dependency_probe,
    )
    serve(worker, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
