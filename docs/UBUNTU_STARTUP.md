# Ubuntu Startup on Thor

Last updated: 2026-10-19

This document describes the current Thor service lifecycle, including the hardened
API entrypoint required by Developer Agent candidate isolation.

## Normal Service Flow

```text
Ubuntu / manual start
  -> scripts/start-jarvis.sh
       -> text llama.cpp :8080
       -> vision llama.cpp :8081
       -> /usr/libexec/jarvis-api-entry :5000
       -> Vite UI :5173
```

The model servers are preserved when already healthy. `jarvis restart` normally
restarts API/UI source while keeping healthy model servers alive.

## API Entrypoint

On Thor, `scripts/start-jarvis.sh` prefers:

```text
/usr/libexec/jarvis-api-entry
```

That root-owned native launcher:

- clears inherited environment
- sets a fixed safe runtime environment
- launches the fixed Jarvis virtual-environment Python and `api.py`
- provides a fixed `--verify-candidate-isolation` mode
- attaches the API to the reviewed AppArmor profile by executable path

The script retains a direct-Python fallback only for environments where the native
entrypoint is not installed. Thor normal operation should use the native entry.

## AppArmor Profiles

Installed policy:

```text
/etc/apparmor.d/usr.libexec.jarvis-api-entry
```

Expected loaded profiles:

```text
jarvis-api-entry
jarvis-api-entry//candidate_userns
jarvis-api-entry//candidate_userns//candidate_runtime
```

The parent API profile denies user namespace creation. Executing the fixed
candidate launcher transitions into `candidate_userns`, where the fixed
`unshare` call may create the user/network namespace. Executing Bubblewrap then
transitions into `candidate_runtime`, which again denies user namespace creation
and profile changes.

The runtime profile grants only the mount operations Bubblewrap needs to construct
the already-reviewed sandbox, including exact propagation flags observed on Thor.

## Native Artifacts

Installed executables:

```text
/usr/libexec/jarvis-api-entry
/usr/libexec/jarvis-candidate-sandbox
```

Reviewed source/build/policy files live in:

```text
packaging/apparmor/
```

Rebuild/install only after source and profile review.

## Service Addresses

| Port | Service |
| --- | --- |
| 8080 | Qwen text llama.cpp server |
| 8081 | Gemma vision llama.cpp server |
| 5000 | Flask API |
| 5173 | Vite UI |

The API binds loopback at `127.0.0.1:5000`.

## Common Commands

```bash
jarvis start
jarvis stop
jarvis restart
jarvis status
jarvis ui
```

Logs/PIDs remain under `/tmp`, including `/tmp/jarvis-api.log` and
`/tmp/jarvis-api.pid`.

## Health Checks

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:5000/api/cameras
```

## Candidate Isolation Verification

After any launcher/AppArmor change:

```bash
/usr/libexec/jarvis-api-entry --verify-candidate-isolation
```

The 2026-10-19 live Thor baseline is:

```text
10 passed
```

Fresh AppArmor diagnostics:

```bash
sudo journalctl -k --since "5 minutes ago" --no-pager |   grep -Ei 'apparmor|DENIED|jarvis-api-entry|candidate_userns|candidate_runtime|bwrap|unshare|mount|pivot|umount|userns'
```

Unrelated Firefox/Chromium snap denials may appear. Evaluate the profile name
before treating an audit record as a Jarvis failure.

## Important Host Rule

Keep:

```text
kernel.apparmor_restrict_unprivileged_userns = 1
```

Do not globally disable this restriction. Jarvis receives the required user
namespace permission only through its reviewed AppArmor transition.

## Rollback

If the hardened entrypoint/policy must be removed:

```bash
jarvis stop
sudo apparmor_parser -R /etc/apparmor.d/usr.libexec.jarvis-api-entry
sudo rm /etc/apparmor.d/usr.libexec.jarvis-api-entry
sudo rm /usr/libexec/jarvis-candidate-sandbox
sudo rm /usr/libexec/jarvis-api-entry
jarvis start
```

The repository startup script then falls back to direct Python. Developer Agent
isolated candidate repair should be considered unavailable until the hardened path
is restored and verified.
