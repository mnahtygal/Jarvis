"""Generate the fixed Thor Python runtime manifest for the native launcher."""

from __future__ import annotations

from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))

from core.developer_agent.candidate_verification import (  # noqa: E402
    _runtime_site_packages,
    _runtime_venv,
    _system_library_bindings,
    _system_runtime_roots,
)


def _c_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    runtime = _runtime_venv()
    site_packages = _runtime_site_packages(runtime)
    shared_libraries, standard_library, loader_name = _system_runtime_roots()
    base_python = Path(sys.executable).resolve(strict=True)
    bindings = _system_library_bindings(
        runtime,
        shared_libraries,
        standard_library,
        base_python,
    )
    print("/* Generated for the local Thor runtime; rebuild before installation. */")
    print("#ifndef JARVIS_RUNTIME_MANIFEST_H")
    print("#define JARVIS_RUNTIME_MANIFEST_H")
    print(f"#define JARVIS_BASE_PYTHON {_c_string(str(base_python))}")
    print(f"#define JARVIS_STDLIB {_c_string(str(standard_library))}")
    print(f"#define JARVIS_SITE_PACKAGES {_c_string(str(site_packages))}")
    print(f"#define JARVIS_SHARED_LIBRARIES {_c_string(str(shared_libraries))}")
    print(f"#define JARVIS_LOADER_NAME {_c_string(loader_name)}")
    print("static const struct runtime_bind JARVIS_RUNTIME_BINDS[] = {")
    for source, destination in bindings:
        print(f"    {{{_c_string(str(source))}, {_c_string(str(destination))}}},")
    print("};")
    print(
        "#define JARVIS_RUNTIME_BIND_COUNT "
        "(sizeof(JARVIS_RUNTIME_BINDS) / sizeof(JARVIS_RUNTIME_BINDS[0]))"
    )
    print("#endif")


if __name__ == "__main__":
    main()
