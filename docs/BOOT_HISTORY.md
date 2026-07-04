# Jarvis Boot History

Last updated: 2026-07-04

Jarvis startup has evolved as the project moved from a manually started local assistant to a repeatable Thor AI workstation environment.

## Boot V1

### Purpose

Get Jarvis running manually during early development.

### Major Improvements

- Proved the basic local workflow.
- Allowed manual startup of API, model server, and UI.
- Kept development simple while architecture was still changing.

### Lessons Learned

- Manual terminals are easy to understand but hard to reproduce.
- Startup state was scattered across shells and notes.
- Health checks were not visible enough.

### Current Status

Retired as the primary workflow. Useful only as historical context or emergency manual recovery.

## Boot V2

### Purpose

Reduce manual startup work and begin collecting service startup into scripts.

### Major Improvements

- Introduced more scripted startup.
- Began separating status/restart/smoke-test helpers.
- Reduced the number of manually opened terminals.

### Lessons Learned

- Startup scripts need clear ownership.
- Browser launching from scripts can fight desktop session restore.
- Logs and service checks need to be predictable.
- Startup should check readiness, not just launch processes.

### Current Status

Superseded by Boot V3.

## Boot V3

### Purpose

Turn Thor into a repeatable AI workstation boot environment.

### Major Improvements

- Thor AI Workstation banner.
- Starts Jarvis services through `scripts/start-jarvis.sh`.
- Waits for the React UI.
- Checks UI, text LLM, and vision LLM endpoints.
- Reports running llama-server processes.
- Reports uptime, memory, and disk.
- Opens VS Code to the repo.
- Logs to `logs/boot-v3.log`.
- Intentionally skips Firefox launch.

### Lessons Learned

- Boot should focus on services, checks, and workspace readiness.
- Firefox should own Firefox session restore.
- Visibility is more useful than hidden automation.
- Startup behavior should be documented and stable.

### Current Status

Current stable startup system. Do not change Boot V3 behavior casually. In particular, do not reintroduce Firefox launch unless there is an explicit new design decision.

## July 3-4 Phase 2 Sprint Note

The July 3-4 development sprint changed frontend architecture, Mission Control, Vision Lab, camera diagnostics, calibration, and measurement foundations. It did not change Boot V3 behavior.

Boot V3 remains responsible for:

- starting Jarvis services through `scripts/start-jarvis.sh`
- checking UI/model readiness
- reporting local workstation status
- opening VS Code
- writing `logs/boot-v3.log`
- intentionally not launching Firefox

Future Phase 3 architecture work should continue to treat Boot V3 as stable infrastructure unless a dedicated startup design pass explicitly changes it.
