# PROMPTS.md

# Jarvis Codex Prompt Library

This document contains standardized prompts for OpenAI Codex when working on the Jarvis repository.

## General Rules

Always begin prompts with:

> Follow AGENTS.md and the project documentation.

Unless explicitly requested:
- Do not commit.
- Preserve existing behavior.
- Make the smallest practical change.
- Update documentation if appropriate.
- Run validation.
- Show the complete diff.

Validation:
```
python -m compileall .
npm run lint
npm run build
```

## New Feature

```text
Implement the following feature following AGENTS.md.

Goal:
<describe feature>

Requirements:
- Preserve existing behavior.
- Keep the implementation modular.
- Update documentation if required.

Validation:
- python -m compileall .
- npm run lint
- npm run build

Show the complete diff before committing.
Do not commit.
```

## Bug Fix

```text
Fix the following bug following AGENTS.md.

Problem:
<describe issue>

Requirements:
- Find the root cause.
- Preserve existing functionality.
- Keep the fix minimal.

Run validation.
Show the diff.
Do not commit.
```

## Architecture Review

```text
Review the implementation.

Do not modify code.

Report:
- Current architecture
- Strengths
- Weaknesses
- Technical debt
- Recommendations
```

## Refactor

```text
Refactor the implementation.

Requirements:
- No behavior changes.
- Improve readability.
- Reduce duplication.
- Preserve public interfaces.

Run validation.
Show the diff.
Do not commit.
```

## Documentation Update

```text
Update repository documentation.

Review existing docs first.
Update only what is affected.
Do not invent functionality.
Show the documentation diff.
Do not commit.
```

## Vision Review

```text
Review the Vision Lab subsystem.

Do not modify code.

Identify:
- Camera flow
- OpenCV usage
- Vision model usage
- API endpoints
- UI components
- Recommendations
```

## Release Checklist

```text
Before completing:

✓ compile passes
✓ lint passes
✓ build passes
✓ documentation updated
✓ diff reviewed

Do not commit.
```

## Jarvis Workflow

1. Architect with ChatGPT.
2. Implement with Codex.
3. Review the diff.
4. Test on Thor.
5. Update documentation.
6. Commit.
7. Push.

**Motto**

> Architect with ChatGPT. Build with Codex. Validate on Thor.
