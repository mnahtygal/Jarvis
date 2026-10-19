# Jarvis Codex Prompt Library

Last updated: 2026-10-19

Use these templates for focused repository work. Current runtime safety and
Developer Agent behavior are documented in `docs/JARVIS_DEVELOPER_AGENT.md`.

## Standard Repository Prompt

```text
Follow AGENTS.md and the current canonical documentation.

Goal:
<describe the task>

Requirements:
- Inspect the relevant implementation first.
- Preserve working behavior.
- Make the smallest practical change.
- Preserve existing safety boundaries.
- Run focused validation and git diff --check.
- Report the root cause, changed files, and validation results.

Leave commit/push to the requested workflow.
```

## Read-Only Architecture Review

```text
Follow AGENTS.md and the current canonical documentation.

Review:
<scope>

Report:
- current architecture
- trust boundaries
- invariants
- failure modes
- concrete evidence
- smallest recommended change

This is a review-only task.
```

## Documentation Update

```text
Follow AGENTS.md and the current canonical documentation.

Update the canonical documentation for the completed behavior.

Keep dated checkpoint files historical.
Do not invent functionality.
Update only the smallest current-document set required.
Run git diff --check and report the documentation diff.
```

## Thor Host-Isolation Work

Treat repository changes and host installation as separate steps. Repository work
should validate source, parser syntax, launcher tests, hashes, and diffs before any
root-owned artifact is replaced or any AppArmor profile is reloaded. Host-specific
behavior must be verified on Thor before the milestone is declared complete.

## Jarvis Runtime Bounded-Repair Prompt

This exact compact form is useful when testing deterministic Brain recognition:

```text
Run a bounded developer session on /home/mnahtygal/projects/jarvis-repair-challenge. Source file: stock.py Test file: test_stock.py Verification: pytest -q test_stock.py Only stock.py may be modified. test_stock.py must remain read-only. Ask for approval before making any change. Do not use Git.
```

Expected approval turn:

```text
approve
```

The Developer Agent recognizer is intentionally strict and has a bounded request
length, so long free-form prose is not equivalent to the canonical form.

## Workflow

1. Architect/review with ChatGPT.
2. Implement with Codex.
3. Inspect the diff.
4. Validate on Thor when host-specific.
5. Update canonical documentation.
6. Checkpoint in Git when appropriate.

> Architect with ChatGPT. Build with Codex. Validate on Thor.
