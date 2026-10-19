# Jarvis Development Guide

Last updated: 2026-10-19

Jarvis is developed primarily on Thor. Keep changes local-first, reviewable, and
bounded. Do not add cloud dependencies, package installers, or broader agent
authority as incidental cleanup.

## Normal Thor Workflow

```bash
cd ~/jarvis
jarvis status
jarvis start
jarvis restart
jarvis ui
```

On Thor, use the service scripts/CLI for normal operation. Do **not** replace the
normal API startup path with `python api.py`: the installed native
`/usr/libexec/jarvis-api-entry` is what attaches the API to the reviewed AppArmor
policy used by Developer Agent isolation.

## Python Checks

Use the repository virtual environment:

```bash
cd ~/jarvis
.venv/bin/python -m compileall -q api.py core skills audio tools
.venv/bin/python -m pytest -q
```

Run narrower tests first while iterating, then the broader relevant suite before a
checkpoint.

## UI Checks

```bash
cd ~/jarvis/ui-app
npm run lint
npm run build
```

Use `npm run dev` only when manually developing the UI.

## Git Workflow

Keep checkpoints focused:

```bash
git status -sb
git diff --check
git diff
git add <focused paths>
git commit -m "Focused summary"
git push origin main
```

Do not commit secrets, model files, runtime artifacts, logs, or generated camera
outputs.

## Developer Agent Development

The Developer Agent is a safety boundary, not a general shell.

When changing it:

1. preserve protected files and sensitive-path rules
2. keep fixed tool IDs and fixed command grammar
3. keep exact approval semantics
4. keep static session scope
5. preserve verification/repair ceilings unless separately reviewed
6. never make tests writable in a repair session
7. preserve candidate-before-original mutation ordering
8. preserve exact passing-byte sealing/promotion
9. run AppArmor/native launcher tests for host-isolation changes
10. verify on Thor before declaring host behavior complete

Protected files include:

- `testbrain.py`
- `audio_pipeline_tester.py`
- `audio_pipeline_tester_jarvis.py`
- `audio_pipeline_tester_jarvis_v2.py`

Do not install Pillow as part of Jarvis development.

## Canonical Bounded Python Session Request

The Brain bridge intentionally recognizes a strict compact grammar. The explicit
workspace form is:

```text
Run a bounded developer session on /absolute/workspace. Source file: source.py Test file: test_source.py Verification: pytest -q test_source.py Only source.py may be modified. test_source.py must remain read-only. Ask for approval before making any change. Do not use Git.
```

The developer bridge also has a request-length ceiling. Long prose descriptions
should not be used as a substitute for this canonical form.

Jarvis should respond with `confirmation_required`. Only a separate exact:

```text
approve
```

authorizes that one pending action.

Current hard maxima:

- 2 repairs
- 3 verification runs total
- 2 proposal requests

## Host Isolation Validation

After AppArmor/native-launcher changes, the live Thor verification is:

```bash
/usr/libexec/jarvis-api-entry --verify-candidate-isolation
```

The 2026-10-19 verified baseline is:

```text
10 passed
```

Check fresh kernel denials after policy changes rather than guessing:

```bash
sudo journalctl -k --since "5 minutes ago" --no-pager |   grep -Ei 'apparmor|DENIED|jarvis-api-entry|candidate_userns|candidate_runtime|bwrap|unshare|mount|pivot|umount|userns'
```

Keep `kernel.apparmor_restrict_unprivileged_userns=1`. Do not globally disable
the host restriction to make development easier.

## Repair Benchmark

The existing-project Python repair benchmark lives outside the repository at:

```text
/home/mnahtygal/projects/jarvis-repair-challenge
```

On 2026-10-19 Jarvis completed it successfully:

- initial verification failed
- one repair proposal accepted
- one isolated candidate passed
- exact passing bytes promoted to `stock.py`
- final independent verification: 6 passed
- `test_stock.py` unchanged
- no Git operation

Do not silently rewrite the benchmark when testing repair behavior.

## Documentation

Current canonical documentation starts at `docs/README.md`. Dated checkpoint
files are historical records and should not be rewritten merely because current
behavior changed.

## General Engineering Rule

Read first, change the smallest necessary surface, validate the behavior that
matters, inspect the diff, and only then checkpoint.
