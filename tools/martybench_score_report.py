# tools/martybench_score_report.py

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "benchmarks" / "results" / "martybench_v2_shift_handoff"

VARIANTS = ["basic", "messy", "conflict", "memory"]


@dataclass
class ScoreRecord:
    run_id: str
    run_dir: Path
    variant: str
    total_score: Optional[int]
    max_score: Optional[int]
    verdict: str
    is_scored: bool


SCORE_PATTERNS = {
    "total": re.compile(r"^Total:\s*(?:(\d+)\s*)?/\s*(\d+)\s*$", re.IGNORECASE),
    "verdict": re.compile(r"^Pass\s*/\s*Partial\s*/\s*Fail:\s*(.*)$", re.IGNORECASE),
}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="replace")


def _variant_from_run_id(run_id: str) -> str:
    for variant in VARIANTS:
        if run_id.endswith(f"_{variant}"):
            return variant

    return "unknown"


def _parse_score_summary(run_dir: Path) -> ScoreRecord:
    run_id = run_dir.name
    variant = _variant_from_run_id(run_id)
    score_text = _read_text(run_dir / "score_summary.md")

    total_score: Optional[int] = None
    max_score: Optional[int] = None
    verdict = ""

    for raw_line in score_text.splitlines():
        line = raw_line.strip()

        total_match = SCORE_PATTERNS["total"].match(line)
        if total_match:
            score_value = total_match.group(1)
            max_value = total_match.group(2)
            total_score = int(score_value) if score_value else None
            max_score = int(max_value) if max_value else None
            continue

        verdict_match = SCORE_PATTERNS["verdict"].match(line)
        if verdict_match:
            verdict = verdict_match.group(1).strip()

    is_scored = total_score is not None and bool(verdict)

    return ScoreRecord(
        run_id=run_id,
        run_dir=run_dir,
        variant=variant,
        total_score=total_score,
        max_score=max_score,
        verdict=verdict,
        is_scored=is_scored,
    )


def collect_score_records() -> List[ScoreRecord]:
    if not RESULTS_DIR.exists():
        return []

    records: List[ScoreRecord] = []

    for run_dir in sorted(RESULTS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue

        if not (run_dir / "score_summary.md").exists():
            records.append(
                ScoreRecord(
                    run_id=run_dir.name,
                    run_dir=run_dir,
                    variant=_variant_from_run_id(run_dir.name),
                    total_score=None,
                    max_score=None,
                    verdict="",
                    is_scored=False,
                )
            )
            continue

        records.append(_parse_score_summary(run_dir))

    return records


def _fmt_score(record: ScoreRecord) -> str:
    if record.total_score is None or record.max_score is None:
        return "unscored"

    return f"{record.total_score}/{record.max_score}"


def _fmt_verdict(record: ScoreRecord) -> str:
    return record.verdict if record.verdict else "unscored"


def _latest_by_variant(records: List[ScoreRecord]) -> Dict[str, ScoreRecord]:
    latest: Dict[str, ScoreRecord] = {}

    for record in records:
        current = latest.get(record.variant)
        if current is None or record.run_id > current.run_id:
            latest[record.variant] = record

    return latest


def _best_by_variant(records: List[ScoreRecord]) -> Dict[str, ScoreRecord]:
    best: Dict[str, ScoreRecord] = {}

    for record in records:
        if record.total_score is None:
            continue

        current = best.get(record.variant)
        if current is None or (current.total_score is not None and record.total_score > current.total_score):
            best[record.variant] = record

    return best


def build_report(records: List[ScoreRecord]) -> str:
    scored = [record for record in records if record.is_scored]
    unscored = [record for record in records if not record.is_scored]
    latest = _latest_by_variant(records)
    best = _best_by_variant(records)

    lines = [
        "# MartyBench Score Report",
        "",
        "## Summary",
        "",
        f"- Total runs found: {len(records)}",
        f"- Scored runs: {len(scored)}",
        f"- Unscored runs: {len(unscored)}",
        "",
        "## Latest Run By Variant",
        "",
        "| Variant | Run ID | Score | Verdict |",
        "|---|---|---:|---|",
    ]

    for variant in VARIANTS:
        record = latest.get(variant)
        if not record:
            lines.append(f"| {variant} | none | unscored | unscored |")
            continue

        lines.append(
            f"| {variant} | {record.run_id} | {_fmt_score(record)} | {_fmt_verdict(record)} |"
        )

    lines.extend(
        [
            "",
            "## Best Scored Run By Variant",
            "",
            "| Variant | Run ID | Score | Verdict |",
            "|---|---|---:|---|",
        ]
    )

    for variant in VARIANTS:
        record = best.get(variant)
        if not record:
            lines.append(f"| {variant} | none | unscored | unscored |")
            continue

        lines.append(
            f"| {variant} | {record.run_id} | {_fmt_score(record)} | {_fmt_verdict(record)} |"
        )

    lines.extend(
        [
            "",
            "## All Runs",
            "",
            "| Run ID | Variant | Score | Verdict | Status |",
            "|---|---|---:|---|---|",
        ]
    )

    for record in sorted(records, key=lambda item: item.run_id, reverse=True):
        status = "scored" if record.is_scored else "needs scoring"
        lines.append(
            f"| {record.run_id} | {record.variant} | {_fmt_score(record)} | {_fmt_verdict(record)} | {status} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "A run is considered scored only when `score_summary.md` has both a filled-in total score and a filled-in verdict after `Pass / Partial / Fail:`.",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize MartyBench score summaries.")

    parser.add_argument(
        "--write",
        action="store_true",
        help="Write martybench_score_report.md under benchmarks/results/.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = collect_score_records()

    if not records:
        print("No MartyBench result runs found.")
        return 1

    report = build_report(records)

    if args.write:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / "martybench_score_report.md"
        output_path.write_text(report, encoding="utf-8")
        print(f"Score report written to: {output_path}")
        print()

    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
