# Brain v2 and Router Architecture

Last updated: 2026-10-19

## Purpose

The Brain layer decides how Jarvis should handle a request while keeping
conversation, memory, skills, and developer actions separate.

## Current Request Path

```text
request
  -> core/request_classifier.py
  -> core/orchestrator.py
       -> Developer Agent bridge for recognized developer requests
       -> legacy router for ordinary conversation/status/memory/vision
```

## Responsibilities

Brain v2:

- classify requests deterministically
- choose context policy
- keep developer requests out of conversational fallback
- enforce confirmation-gated Developer Agent routing
- publish safe lifecycle/status metadata
- keep model text from being mistaken for proof that a tool ran

## Developer Requests

`core/developer_bridge.py` recognizes a deliberately small grammar. It does not
accept arbitrary model-selected tools or arguments.

Sensitive developer actions and bounded sessions require a separate exact approval
turn. A pending action is single-use, expires, and is invalidated by unrelated
requests.

The canonical bounded Python session freezes:

- explicit workspace
- one source file
- one test file
- exact pytest target
- source-only mutation scope
- fixed repair/verification/proposal ceilings

See `docs/JARVIS_DEVELOPER_AGENT.md` for the current isolation and promotion
architecture.

## Ordinary Requests

Requests not classified as Developer Agent operations continue through the
ordinary Jarvis router and skills. Memory use is controlled by the Brain v2
context policy rather than loaded indiscriminately.

## Design Rules

- routing must stay readable and deterministic where possible
- developer capability selection must not come from free-form model output
- tool execution truth must come from structured tool/session results
- sensitive requests must fail closed on ambiguity
- conversation and developer approval state must not be conflated
- broader autonomy requires an explicit architecture review

## Current Validation Milestone

On 2026-10-19 Brain v2 successfully recognized the canonical explicit-workspace
bounded repair prompt, required a separate `approve` turn, and routed the session
through the hardened Developer Agent. The independently verified benchmark
finished with 6 passing project tests.
