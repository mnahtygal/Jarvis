# Jarvis Secure API Deployment

Date: 2026-11-23
Host: NVIDIA Thor
Branch: feature/api-apparmor-service
Commit: f27a389

## Purpose

Move the production Flask API from direct Python startup into
the reviewed native AppArmor entrypoint while preserving
handheld authentication.

## Production Configuration

Service: jarvis-api.service

Entrypoint:
`/usr/libexec/jarvis-api-entry`

Systemd drop-ins:
- `/etc/systemd/system/jarvis-api.service.d/10-handheld-env.conf`
- `/etc/systemd/system/jarvis-api.service.d/20-secure-launcher.conf`

Required security profile:
`jarvis-api-entry (enforce)`

Installed launcher SHA-256:
`95ec8cdea2bb385810e5fb068a9c93cd9eb5428665a2fbaddbabcdc10d0c615a`

## Validation

- Native launcher compiled successfully.
- Security and handheld regression tests: 57 passed.
- Candidate isolation verification: 10 passed.
- Flask `/health`: HTTP success.
- Text model port 8080: healthy.
- Vision model port 8081: healthy.
- Handheld token: present in process environment.
- Invalid handheld credential: HTTP 401.
- Production API: active.
- AppArmor profile: enforced.

## Pending Functional Checks

- Valid authenticated handheld request through Flask.
- Real image-analysis request through Flask.
- Developer Agent candidate execution through production API.

## Rollback Backup

`/home/mnahtygal/jarvis-backups/api-apparmor-20261123-051712`

Contains:
- Original native launcher
- Original systemd service
- Original AppArmor policy

No handheld token or environment file is included.

## Rollback Procedure

To restore the original direct-Python API startup:

```bash
sudo rm -f \
  /etc/systemd/system/jarvis-api.service.d/20-secure-launcher.conf

sudo systemctl daemon-reload
sudo systemctl restart jarvis-api.service

systemctl is-active jarvis-api.service
curl --max-time 5 -fsS http://127.0.0.1:5000/health
```

This rollback restores the original service execution path.

If the installed launcher itself must be restored, use the
backed-up binary after verifying the backup location and
permissions. Do not disable AppArmor globally.

## Security Notes

- The API runs under an enforced AppArmor profile.
- Candidate isolation uses its dedicated namespace transitions.
- The native launcher clears inherited environment variables.
- Only the approved handheld token is preserved for API mode.
- Isolation verification mode excludes that credential.
- Flask remains bound to 127.0.0.1:5000.
- Authentication secrets must never be written to logs or Git.
