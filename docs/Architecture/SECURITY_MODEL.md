# Jarvis Security Model

Last updated: 2026-10-19

Jarvis uses least privilege, explicit approval, bounded execution, and local-first
operation as default policy.

## Core Policy

Require explicit confirmation for sensitive actions such as:

- file mutation
- constrained command execution
- local Git stage/commit
- bounded developer sessions
- other actions that cross a clear trust boundary

There is no generic shell capability and no automatic Git push.

## Developer Agent Boundary

The Developer Agent uses:

- fixed capability registry
- deterministic request recognition
- static workspace and file scope
- protected/sensitive path refusal
- strict argument schemas
- bounded subprocess time/output
- strict repair-model schema
- verification ceilings
- candidate verification before original mutation
- exact passing-byte promotion

Tests are not writable in the current bounded Python repair flow.

## Thor Host Isolation

Normal Thor API startup uses `/usr/libexec/jarvis-api-entry` with an AppArmor
profile.

Expected transition chain:

```text
jarvis-api-entry
  -> candidate_userns
  -> candidate_runtime
```

The parent and runtime profiles deny user namespace creation. Only the narrow
candidate setup child may create the user/network namespace for the fixed
`unshare` call.

Bubblewrap then constructs the reviewed candidate filesystem/process sandbox:

- candidate source/test tree read-only
- private temporary locations
- disconnected network namespace
- minimal runtime/library visibility
- no broad home/project/credential/model visibility

Keep the host-wide unprivileged-userns restriction enabled.

## Promotion Rule

A repair may reach the original project only after an isolated candidate passes.
Jarvis seals the exact passing bytes, destroys the disposable candidate, rechecks
the original workspace/file identities, and atomically promotes those exact bytes.

Any stale state, seal mismatch, cleanup failure, or verification failure stops
safely.

## Git

Developer Agent Git behavior is deliberately separate from repair execution.
Bounded repair sessions do not stage, commit, push, reset, restore, or rewrite
history.

## Secrets and Sensitive Files

Do not expose or commit:

- passwords/tokens
- private keys/certificates
- `.env*`
- credentials/secrets
- Git metadata
- personal data dumps
- model files
- runtime logs/artifacts

## Validation

Host security changes are not complete because parser/unit tests pass in a
development sandbox. They must be verified on Thor.

The 2026-10-19 baseline is:

- live candidate-isolation suite: 10 passed
- existing-project repair benchmark: 6 passed after one isolated promoted repair

That milestone validates the current boundary; it does not authorize broader
execution privileges.
