# Brain v2 Phase 9 observe-only planner

`core/planner.py` applies deterministic phrase combinations before routing. It
returns no plan for ordinary single-step requests. Recognized bounded patterns
include sequenced health/model checks, capture plus image analysis, memory versus
runtime comparisons, retrieval comparisons, and inspect-plus-summary requests.

Plans contain two to five immutable steps. Every action and category is a fixed
internal label; no command content enters BrainResult metadata or Brain v2
status. Categories are limited to memory, runtime, system, camera, vision, llm,
comparison, summary, and unknown.

Phase 9 does not execute plan steps. It performs no model, database, memory,
skill, network, or tool calls. The original command still reaches the existing
router exactly once, and its response remains unchanged. Status reports only
whether a plan was suggested, its step count, categories, and heuristic
confidence. Exceptions retain the same diagnostic planner metadata.
