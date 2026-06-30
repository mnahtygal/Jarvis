# Contributing to Jarvis

## Development Style

Jarvis is built carefully and locally first.

Every change should be understandable, reversible, and tested on the actual Thor environment when possible.

## Standard Workflow

1. Pull latest from GitHub.
2. Create or inspect the task.
3. Read relevant files.
4. Make minimal changes.
5. Run checks.
6. Review diff.
7. Commit with a focused message.
8. Push.

## AI-Assisted Workflow

When using Codex, Copilot, Cursor, or another coding agent:

- Reference `AGENTS.md`.
- Ask for a diff before commit.
- Do not allow automatic commits unless intentionally requested.
- Keep each task small.
- Run lint/build/compile checks.
- Paste errors back into the discussion before guessing.

Recommended prompt ending:

```text
Do not commit.
Run the relevant checks.
Show me the diff before committing.
```

## Checks

Python:

```bash
.venv/bin/python -m compileall -q api.py core skills audio tools
```

UI:

```bash
cd ui-app
npm run lint
npm run build
```

## Commit Guidelines

Use focused commit messages.

Examples:

```bash
git commit -m "Add Scan Mat image display support"
git commit -m "Document Phase 2 Maker Lab roadmap"
git commit -m "Fix Vision Lab API error handling"
```

Avoid commits that mix unrelated backend, UI, docs, and cleanup changes.

## Documentation Expectations

Update documentation when changing:

- API routes
- folder structure
- setup steps
- model ports
- memory schema
- scan outputs
- UI workflow
- Maker Lab behavior

## Code Expectations

Backend:

- Keep Flask routes thin.
- Put reusable logic into skills/core/tools.
- Use type hints for new functions.
- Prefer pathlib.
- Return useful JSON errors.

Frontend:

- Keep lint clean.
- Keep UI responsive.
- Preserve dark dashboard style.
- Avoid unnecessary dependencies.

## Safety

Do not commit:

- `.env`
- passwords
- tokens
- private keys
- generated model files
- huge local artifacts
- personal data dumps

