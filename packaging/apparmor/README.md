# Jarvis candidate-isolation launchers

These artifacts package the narrow AppArmor attachment point needed on Thor while
leaving `kernel.apparmor_restrict_unprivileged_userns=1` enabled.

## Boundary and accepted inputs

`jarvis-api-entry` is a native executable with exactly two modes:

- no arguments: execute the fixed Jarvis virtual-environment Python and fixed
  `/home/mnahtygal/jarvis/api.py`;
- `--verify-candidate-isolation`: execute the fixed candidate-isolation test
  module.

It clears the inherited environment and supplies a small fixed environment. The
only Python import path is the compile-time fixed `/home/mnahtygal/jarvis` value;
safe-path and no-user-site protections remain enabled. It does not accept an
executable, command, Python text, environment block, mount, namespace option, or
any other argument.

`jarvis-candidate-sandbox` is a native executable accepting only:

```text
--candidate-fd FD [APPROVED_PYTEST_ARGUMENT ...]
```

`FD` must already refer to a mode-0700 directory owned by the caller, its stable
device/inode must resolve to one direct `/tmp/jarvis-candidate-*` directory, and
each selected pytest path must exist beneath that FD without a symlink traversal.
The remaining grammar is the same finite pytest flag/value/path subset validated
by the Developer Agent before this launcher is reached. The launcher validates it
again as boundary hardening. It does not perform user approval or Developer Agent
authorization.

The namespace flags, executables, environment, mount destinations, runtime roots,
and individual shared-library binds are compiled into the executable. The runtime
manifest is generated from Thor's active Jarvis venv at build time and must be
rebuilt immediately before installation. No caller-provided mount list is
accepted.

## AppArmor design

The only global attachment is the exact installed
`/usr/libexec/jarvis-api-entry`. Its `default_allow` profile explicitly denies
user-namespace creation. Executing the exact candidate launcher through the
profile's `Cx` rule enters a local child profile that alone has `userns create`.
That permission is inherited by the fixed `/usr/bin/unshare` execution. Executing
the exact `/usr/bin/bwrap` then enters a second local child profile that again
denies user-namespace creation.

`flags=(default_allow)` is used instead of the originally proposed
`flags=(unconfined)`. Thor's AppArmor 4 parser supports default-allow profiles,
which retain explicit deny rules and controlled domain transitions. That makes it
possible to deny `userns create` in the API and post-unshare runtime domains while
granting it only in the short launcher/unshare domain.

Neither `default_allow` nor AppArmor provides the candidate filesystem sandbox.
Default-allow is intentionally used to avoid creating a large, fragile host file
policy for the existing API, Python venv, hardware, database sockets, and
Bubblewrap mount setup. Bubblewrap remains the filesystem, PID, IPC, UTS,
capability, and disconnected-network sandbox. The profile is only a selective
user-namespace gate plus exact executable transitions.

An enforced default-deny profile could express the same `userns` gate, but it
would also require a comprehensive and machine-sensitive policy for every Jarvis
API and dynamic Python access. That is a separate confinement project and is not
a safe prerequisite for restoring this one fixed sandbox primitive.

## Build and syntax check

From the repository root:

```bash
make -C packaging/apparmor clean all
apparmor_parser --skip-kernel-load --skip-read-cache \
  packaging/apparmor/usr.libexec.jarvis-api-entry
```

`--skip-kernel-load` performs parser/compile validation without loading or
replacing a kernel profile. No sudo is required.

## Proposed installation (not performed by repository validation)

After review, rebuild and atomically install the two root-owned executables and
profile, then load only that profile:

```bash
make -C /home/mnahtygal/jarvis/packaging/apparmor clean all
sudo install -o root -g root -m 0755 \
  /home/mnahtygal/jarvis/packaging/apparmor/jarvis-api-entry \
  /usr/libexec/jarvis-api-entry
sudo install -o root -g root -m 0755 \
  /home/mnahtygal/jarvis/packaging/apparmor/jarvis-candidate-sandbox \
  /usr/libexec/jarvis-candidate-sandbox
sudo install -o root -g root -m 0644 \
  /home/mnahtygal/jarvis/packaging/apparmor/usr.libexec.jarvis-api-entry \
  /etc/apparmor.d/usr.libexec.jarvis-api-entry
sudo apparmor_parser -r /etc/apparmor.d/usr.libexec.jarvis-api-entry
/usr/libexec/jarvis-api-entry --verify-candidate-isolation
if /usr/bin/unshare --user --map-root-user -- true; then
  echo "ERROR: ordinary shell unexpectedly gained userns" >&2
  exit 1
fi
jarvis restart
```

The repository start script automatically selects the installed
`/usr/libexec/jarvis-api-entry`; before installation it retains the existing
direct-Python fallback. Do not grant `userns` to Python, the shell, VS Code,
`/usr/bin/unshare`, or an unconfined wildcard profile.

Rollback:

```bash
jarvis stop
sudo apparmor_parser -R /etc/apparmor.d/usr.libexec.jarvis-api-entry
sudo rm /etc/apparmor.d/usr.libexec.jarvis-api-entry
sudo rm /usr/libexec/jarvis-candidate-sandbox
sudo rm /usr/libexec/jarvis-api-entry
jarvis restart
```

The repository start script then returns to its direct-Python fallback. The
sysctl is not changed during installation or rollback.
