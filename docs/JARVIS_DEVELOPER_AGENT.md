# Jarvis Developer Agent

## Purpose

The Developer Agent is a controlled, local-first tool boundary for future software
development workflows. Phase 1 is deliberately read-only: it lets trusted Jarvis
code inspect the project workspace without exposing arbitrary filesystem or command
access.

Brain v2 advertises these capabilities, but does not invoke them from natural
language or run an autonomous tool loop.

## Architecture

The implementation is intentionally small:

- `core/developer_agent/tool_models.py` defines immutable tool results.
- `core/developer_agent/workspace.py` owns the shared workspace boundary.
- `core/developer_agent/registry.py` contains a fixed tool registry.
- `core/developer_agent/executor.py` validates arguments and uses a fixed dispatch
  table.
- `core/developer_agent/tools/` contains the three read-only implementations.
- `core/capability_registry.py` advertises the matching Brain v2 capabilities.

There is no dynamic registration, dynamic import, `eval`, `exec`, or generic shell
tool.

## Phase 1 tools

### `developer.list_files`

Lists a directory inside the workspace. Results are sorted and bounded. Recursive
listings skip `.git`, `.venv`, `__pycache__`, `node_modules`, `build`, and `dist`
unless one of those directories is explicitly selected as the listing root.
Each visited directory also has a fixed scan ceiling, preventing a single unusually
large directory from consuming unbounded memory before sorting.

### `developer.read_file`

Reads bounded UTF-8 text and returns line-numbered output. It refuses directories,
binary or invalid UTF-8 files, and explicitly sensitive names: `.env`, `.env.*`,
`*.pem`, `*.key`, `credentials*`, and `secrets*`.

### `developer.git_status`

Runs only this fixed argument vector with a timeout and captured output:

```text
git status --short --branch
```

It uses the workspace root as its working directory, never enables a shell, and
sets `GIT_OPTIONAL_LOCKS=0` to prevent optional index refresh writes.

## Workspace and security model

The default approved root is the Jarvis repository containing the implementation.
A caller may construct a `Workspace` with another explicit project root for tests
or controlled embedding.

Every filesystem tool resolves the requested path and all symlinks before checking
containment. Absolute paths and `..` paths are accepted only when their resolved
destination remains inside the configured root. Escapes to a home directory,
`/etc`, `/proc`, or any other external location are rejected. Recursive listing
does not follow symlinks outside the root.

Tool results contain stable error codes and safe messages; raw exceptions are not
returned. File reads, line ranges, directory output, Git output, and subprocess
duration are bounded.

## Read-only limitation

Phase 1 cannot create, modify, delete, stage, commit, or push files. The executor
allows exactly the three registered IDs. It does not provide command execution,
automatic retries, self-correction, planning, or natural-language invocation.

Allowed examples:

```python
execute_tool("developer.list_files", {"path": "core", "recursive": False})
execute_tool("developer.read_file", {"path": "README.md", "start_line": 1, "end_line": 20})
execute_tool("developer.git_status", {})
```

Rejected examples include `../` or symlink escapes, `/etc/passwd`, `.env`, binary
files, unknown tool IDs, unsupported arguments, and any attempted
`developer.run_command` or write/edit tool.

## Roadmap

- Phase 2: controlled `write_file` and `patch_file`
- Phase 3: controlled `run_command`
- Phase 4: build/test/verify loop
- Phase 5: Git commit
- Phase 6: Farkle-2 autonomous benchmark

Each later phase requires a separate security design and validation. None of those
capabilities is available in Phase 1.
