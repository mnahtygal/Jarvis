"""Run a repeatable multi-sample metric-mask validation sweep."""

import argparse
from pathlib import Path

from .validation import (
    console_summary,
    load_manifest,
    run_validation,
    write_results,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare metric-mask outside-envelope and robust-body "
            "measurements with known caliper dimensions."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings, samples = load_manifest(args.manifest)
    results = run_validation(samples, **settings)
    write_results(
        results,
        json_path=args.output_json,
        csv_path=args.output_csv,
    )
    print(console_summary(results))
    print(f"JSON: {args.output_json}")
    print(f"CSV: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
