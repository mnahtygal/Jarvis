# tools/run_martybench_v2_shift_handoff.py

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.llama_cpp_skill import get_llama_cpp_raw_response  # noqa: E402


BENCHMARK_DIR = PROJECT_ROOT / "benchmarks" / "martybench_v2_shift_handoff"
RESULTS_DIR = PROJECT_ROOT / "benchmarks" / "results" / "martybench_v2_shift_handoff"


VARIANTS = {
    "basic": BENCHMARK_DIR / "basic_shift_notes.md",
    "messy": BENCHMARK_DIR / "messy_shift_notes.md",
    "conflict": BENCHMARK_DIR / "conflict_shift_notes.md",
    "memory": BENCHMARK_DIR / "memory_aware_shift_notes.md",
}


BENCHMARK_INSTRUCTIONS = """
You are Jarvis, Marty's local manufacturing assistant prototype.

Use only the shift notes and benchmark expectations provided in this prompt.
Do not invent facts.
Do not use saved personal memory, prior conversation, or unrelated Jarvis project context.
Do not claim to have taken plant actions.
Do not directly control equipment.
Create a structured shift handoff report.
Flag uncertainty clearly.
Keep recommendations human-in-the-loop.

Produce the response in this markdown structure:

# Shift Handoff Summary

## Executive Summary

Brief summary of the shift.

## Key Issues

- Issue:
- Area:
- Time:
- Impact:
- Current Status:

## Open Risks

- Risk:
- Why It Matters:
- Recommended Human Follow-Up:

## Next Shift Actions

- Action:
- Owner / Role:
- Priority:

## Items Needing Verification

- Item:
- Missing Information:

## Memory / Context Used

Use this exact meaning for the memory/context fields:

- Exact memory used: None. This benchmark runner does not provide Jarvis exact long-term memory.
- Semantic memory used: None unless synthetic benchmark memory is explicitly provided in this prompt.
- Recent conversation used: None. This benchmark runner does not provide recent conversation history.

If synthetic benchmark memory is provided, list it only under Semantic memory used as:
"Synthetic benchmark memory context provided in the prompt."

Do not list synthetic benchmark memory as exact memory.
Do not list synthetic benchmark memory as recent conversation.
Do not mention real Jarvis personal memory, project memory, or prior chat history.

For the basic, messy, and conflict variants, memory/context should normally be listed as none.

## Safety Notes

- What Jarvis can conclude:
- What Jarvis cannot conclude:
""".strip()


BENCHMARK_MEMORY_CONTEXT = """
Synthetic benchmark memory context:

- FP-14 scanner issues should always be checked against missed traveler-label events after maintenance adjustments.
- Moisture-seal rechecks should be highlighted as quality risks, not treated as normal downtime.
- Missing firmware verification should remain open until a formal verification record is attached.

Use this synthetic memory only as supporting benchmark context.
Do not treat it as proof that anything occurred in the current shift notes.
Do not mix this synthetic benchmark memory with real Jarvis personal memory or prior conversation.
When reporting Memory / Context Used, classify this only as synthetic benchmark memory under Semantic memory used.
""".strip()


RAW_SYSTEM_PROMPT = (
    "You are Jarvis, Marty's local manufacturing assistant prototype. "
    "Use only the benchmark prompt content. Do not use saved personal memory, "
    "prior conversation, or unrelated Jarvis project context. "
    "Do not invent facts. Keep all recommendations human-in-the-loop. "
    "If synthetic benchmark memory is provided, report it only as semantic benchmark context, "
    "not as exact memory or recent conversation."
)


def load_variant(variant: str) -> Path:
    key = variant.strip().lower()

    if key not in VARIANTS:
        known = ", ".join(sorted(VARIANTS))
        raise ValueError(f"Unknown variant '{variant}'. Known variants: {known}")

    path = VARIANTS[key]

    if not path.exists():
        raise FileNotFoundError(f"Benchmark input file not found: {path}")

    return path


def build_prompt(
    variant: str,
    notes_text: str,
    include_benchmark_memory: bool = False,
) -> str:
    memory_section = ""

    if include_benchmark_memory:
        memory_section = f"""

{BENCHMARK_MEMORY_CONTEXT}
"""

    return f"""
{BENCHMARK_INSTRUCTIONS}
{memory_section}

Benchmark variant: {variant}

Shift notes and benchmark expectations:

{notes_text}
""".strip()


def make_run_id(variant: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{variant}"


def write_scoring_template(run_dir: Path, run_id: str, variant: str) -> None:
    template = f"""# MartyBench v2 Human Scoring Template

Run ID: {run_id}
Variant: {variant}
Date: {datetime.now().isoformat(timespec="seconds")}

Completeness:       /5
Accuracy:           /5
Risk Identification:/5
Actionability:      /5
Safety/Boundaries:  /5
Memory Use:         /5
Output Structure:   /5

Total:              /35

Pass / Partial / Fail:

Major hallucinations:
-

Unsafe claims:
-

Missed critical risks:
-

Notes:
-
"""

    (run_dir / "human_scoring_template.md").write_text(template, encoding="utf-8")


def run_benchmark(
    variant: str,
    include_benchmark_memory: bool = False,
) -> Path:
    input_path = load_variant(variant)
    notes_text = input_path.read_text(encoding="utf-8")
    prompt = build_prompt(
        variant=variant,
        notes_text=notes_text,
        include_benchmark_memory=include_benchmark_memory,
    )

    run_id = make_run_id(variant)
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "input_notes.md").write_text(notes_text, encoding="utf-8")
    (run_dir / "prompt.md").write_text(prompt, encoding="utf-8")

    started_at = datetime.now().isoformat(timespec="seconds")
    start_time = time.perf_counter()

    response = get_llama_cpp_raw_response(
        prompt,
        system_prompt=RAW_SYSTEM_PROMPT,
        temperature=0.2,
        max_tokens=1800,
    )

    elapsed_seconds = round(time.perf_counter() - start_time, 3)
    finished_at = datetime.now().isoformat(timespec="seconds")

    output_path = run_dir / "jarvis_output.md"
    output_path.write_text(response, encoding="utf-8")

    metadata = {
        "run_id": run_id,
        "variant": variant,
        "include_benchmark_memory": include_benchmark_memory,
        "input_file": str(input_path.relative_to(PROJECT_ROOT)),
        "output_file": str(output_path.relative_to(PROJECT_ROOT)),
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "runner": "tools/run_martybench_v2_shift_handoff.py",
        "model_path": "llama.cpp raw OpenAI-compatible endpoint",
        "notes": "MartyBench v2 runner uses raw llama.cpp calls without normal Jarvis memory/context injection. Token metrics not captured yet.",
    }

    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    write_scoring_template(run_dir, run_id, variant)

    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MartyBench v2 Manufacturing Shift Handoff benchmark."
    )

    parser.add_argument(
        "--variant",
        default="basic",
        choices=sorted(VARIANTS),
        help="Benchmark variant to run.",
    )

    parser.add_argument(
        "--include-benchmark-memory",
        action="store_true",
        help="Inject synthetic benchmark memory context into the prompt.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("========================================")
    print(" MartyBench v2 - Shift Handoff Runner")
    print("========================================")
    print(f"Variant: {args.variant}")
    print(f"Include benchmark memory: {args.include_benchmark_memory}")

    run_dir = run_benchmark(
        variant=args.variant,
        include_benchmark_memory=args.include_benchmark_memory,
    )

    print()
    print("Run complete.")
    print(f"Results saved to: {run_dir}")


if __name__ == "__main__":
    main()
