# Brain v2 Phase 10 plan validation

The Phase 9 planner proposes bounded diagnostic plans. The Phase 10 validator
independently checks the resulting `PlanResult` structure. Both components are
observe-only: neither executes steps, changes routing, or calls databases,
models, memory, skills, tools, cameras, or network services.

A required plan is valid only when it contains two to five sequentially ordered
steps, non-empty fixed action labels, no exact duplicate action/category pairs,
and only supported categories. Supported categories are memory, runtime, system,
camera, vision, llm, comparison, and summary. The planner's `unknown` category
is intentionally unsupported for execution readiness.

Validation statuses are `not_required`, `valid`, `too_few_steps`,
`too_many_steps`, `unsupported_category`, `invalid_order`, `duplicate_step`, and
`malformed`. Brain v2 status exposes only the validation status alongside the
existing safe planner count and category metadata.

Validation is diagnostic in Phase 10. Valid and invalid plans both continue to
the existing router exactly once, and the router response remains unchanged.
