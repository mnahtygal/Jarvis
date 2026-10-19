# Jarvis Developer Agent

Last updated: 2026-10-19

## Purpose

The Developer Agent is Jarvis's controlled software-development boundary. It is
designed to perform useful local engineering work without turning Jarvis into an
unrestricted shell or autonomous administrator.

The current milestone supports explicit, bounded Python repair sessions and a
small set of controlled developer tools.

## Core Principles

- deterministic capability recognition
- fixed tool registry and fixed argument schemas
- no generic shell
- explicit approval for sensitive actions
- static workspace/source/test/verification scope
- protected and sensitive paths fail closed
- strict repair-model output
- candidate verification before original mutation
- exact passing-byte promotion
- bounded retries and verification budget
- no automatic Git stage, commit, push, reset, or history rewrite

## Brain v2 Bridge

Developer requests enter through `core/developer_bridge.py`.

Read-only tools may execute after deterministic validation. Sensitive single
actions and bounded sessions return `confirmation_required` and execute nothing
until a separate exact approval arrives.

Accepted approval:

```text
approve
```

Approval is single-use, argument-bound, process-local, and expires. An unrelated
request invalidates the pending action.

## Canonical Explicit-Workspace Python Session

Use the compact canonical grammar:

```text
Run a bounded developer session on /absolute/workspace. Source file: source.py Test file: test_source.py Verification: pytest -q test_source.py Only source.py may be modified. test_source.py must remain read-only. Ask for approval before making any change. Do not use Git.
```

The recognizer is intentionally strict and request length is bounded. Long
free-form developer plans are not equivalent to this grammar.

Current hard ceilings:

- maximum 2 repairs
- maximum 3 verification runs total
- maximum 2 repair-proposal requests

## Python Session Flow

```text
confirmation
  -> exact approve
  -> capture original workspace/source/test baseline
  -> disposable baseline verification
  -> if failing: bounded local-model proposal
  -> apply proposal only to fresh disposable candidate
  -> isolated pytest
  -> reject candidate if verification fails
  -> if verification passes:
       seal exact candidate bytes + SHA-256
       destroy candidate tree
       revalidate original workspace and file identities
       atomically promote the exact sealed passing bytes
  -> stop
```

A failed candidate never becomes a change to the original source.

## Candidate Isolation on Thor

The API normally runs through:

```text
/usr/libexec/jarvis-api-entry
```

The fixed candidate launcher is:

```text
/usr/libexec/jarvis-candidate-sandbox
```

AppArmor transition chain:

```text
jarvis-api-entry
  -> jarvis-api-entry//candidate_userns
  -> jarvis-api-entry//candidate_userns//candidate_runtime
```

### User namespace gate

The parent API profile denies `userns create`.

Only executing the exact candidate launcher enters `candidate_userns`, where
user namespace creation is allowed for the fixed `/usr/bin/unshare` path.

Bubblewrap then transitions to `candidate_runtime`, which again denies:

- user namespace creation
- profile changes

### Bubblewrap boundary

The root-owned native launcher constructs the namespace and mount plan internally.
The caller cannot choose an executable, environment, namespace flag, mount list,
or arbitrary pytest option.

The candidate sandbox provides:

- disconnected network namespace
- private process/runtime namespace setup
- capability drop
- read-only candidate tree
- private tmpfs-backed temporary locations
- isolated `/proc`
- minimal `/dev`
- only the fixed Python runtime/site-package/library manifest

The original project, broader home directory, Git/SSH credentials, model files,
and unrelated host files are not part of the candidate filesystem.

AppArmor supplies the selective user-namespace/profile/mount gate. Bubblewrap
supplies the candidate filesystem/process/network sandbox.

## Promotion Safety

When an isolated candidate passes:

1. Jarvis reads and seals the exact candidate source bytes.
2. The candidate size and SHA-256 are recorded in memory.
3. The disposable candidate is removed.
4. Jarvis rechecks the original workspace inode.
5. Jarvis rechecks the approved source/test snapshots and digests.
6. Proposal preconditions are revalidated.
7. Only the exact sealed passing bytes are atomically promoted.

Concurrent changes, cleanup failure, stale preconditions, seal mismatch, or
promotion failure stop safely.

## Repair Model Boundary

The repair model receives bounded failure/context data and must return one strict
structured proposal. It cannot select commands or expand the candidate set.

Important controls include:

- strict JSON/grammar output
- fixed proposal types
- bounded source/failure context
- bounded payload sizes
- minimum confidence threshold 0.70
- exact one-match patch validation
- no test mutation
- no model-selected verification command
- no package/network/Git authority

Model confidence is a heuristic, not a calibrated probability.

## Other Developer Capabilities

The repository also contains controlled tools for:

- list/read/git status
- write/patch
- constrained pytest/compile verification
- fixed offline Gradle unit verification
- explicit local Git stage
- verification-gated local commit

These tools keep their own argument validation and confirmation gates. The generic
command tool is not a shell and does not accept package installers, arbitrary
executables, destructive filesystem utilities, service controls, or Git push.

## Protected Files

The safety policy protects, among other sensitive paths:

- `testbrain.py`
- `audio_pipeline_tester.py`
- `audio_pipeline_tester_jarvis.py`
- `audio_pipeline_tester_jarvis_v2.py`
- Git metadata
- `.env*`
- keys/certificates/credential/secret paths

## 2026-10-19 Thor Validation

### Isolation suite

```text
/usr/libexec/jarvis-api-entry --verify-candidate-isolation
.......... [100%]
10 passed
```

### Existing-project repair benchmark

Workspace:

```text
/home/mnahtygal/projects/jarvis-repair-challenge
```

Result:

- initial verification: failed
- proposals generated: 1
- candidate repairs attempted: 1
- candidate repairs rejected: 0
- repairs promoted: 1
- verification runs: 2
- final stop reason: `verification_passed`
- modified path: `stock.py`
- test file remained read-only
- Git stage/commit/push: no

Independent final verification:

```text
6 passed
```

This proves the current bounded repair path works on Thor. It does **not** imply
permission for broader autonomous mutation or shell access.

## Current Next Step

Improve ergonomics and add another small benchmark while preserving the exact
authority boundary. In particular, users should not have to memorize the
canonical grammar forever; a dedicated UI/CLI form can make the same frozen scope
easier to create without widening it.
