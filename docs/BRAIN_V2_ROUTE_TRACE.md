# Brain v2 Phase 8 route attribution

`core/route_trace.py` keeps a fixed route label in a ContextVar during each
orchestrated request. The orchestrator starts with `unknown`, calls the existing
router once, captures the label, and restores the enclosing trace in `finally`.
Direct router callers still receive strings; outside an active trace, setters
do not retain state. Nested and concurrent requests have independent traces.

Labels: `exact_memory`, `semantic_memory`, `memory_write`, `runtime_status`,
`system`, `help_docs`, `camera_vision`, `chat`, `llm_fallback`, and `unknown`.
Explicit semantic saves use `memory_write`; semantic reads/search use
`semantic_memory`. A branch label identifies the selected handler, not successful
execution or a specific LLM backend. If a handler raises before a label is set,
the failed lifecycle records `unknown`. Evaluation remains separate.

`BrainResult.actual_route`, its metadata, and the latest Brain v2 snapshot carry
the captured label. `brain v2 status` now includes `Actual route` and version
`2.0-phase8`. The command displays the previous completed snapshot and then
becomes the latest request itself. Other response text and router condition
order are unchanged. Expected strategy may differ: `hello` expects `llm` under
the existing classifier but actually uses `chat`.

No commands, responses, prompts, memory values, or exception text enter the
trace. Status remains process-local; context source names describe the policy,
not proof that those stores were queried. No API or persistence changes.
