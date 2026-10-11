"""Dedicated offline Android JVM unit-test verification."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from core.developer_agent.command_policy import SAFE_SYSTEM_PATH, CommandPolicyError
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.tools.run_command import _bounded_number, _execute_fixed_argv
from core.developer_agent.workspace import Workspace


TOOL_ID = "developer.gradle_test"
COMMAND_FAMILY = "gradle_test"
FIXED_TASK = ":app:testDebugUnitTest"
FIXED_ARGUMENTS = (
    "--offline",
    "--no-daemon",
    "--console=plain",
    FIXED_TASK,
)
DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 300
DEFAULT_MAX_OUTPUT_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_PROPERTIES_BYTES = 16 * 1024
MAX_WRAPPER_SCRIPT_BYTES = 64 * 1024
MAX_WRAPPER_JAR_BYTES = 256 * 1024

_TRUSTED_ANDROID_SDK_ROOT = Path("/home/mnahtygal/Android/Sdk")
_TRUSTED_AAPT2_ROOT = Path("/home/mnahtygal/Android/qemu-x86-aapt2")
_TRUSTED_GRADLE_HOME = Path.home() / ".gradle"
_SAFE_PROJECT_GRADLE_PROPERTIES = frozenset({
    "org.gradle.caching",
    "org.gradle.configureondemand",
    "org.gradle.console",
    "org.gradle.daemon",
    "org.gradle.offline",
    "org.gradle.parallel",
    "org.gradle.warning.mode",
    "org.gradle.workers.max",
})
_DANGEROUS_GRADLE_PROPERTY_PREFIXES = (
    "systemProp.",
    "org.gradle.java.",
    "org.gradle.jvmargs",
    "org.gradle.project.",
)


@dataclass(frozen=True)
class _WrapperPolicy:
    version: str
    distribution_url_property: str
    distribution_url: str
    distribution_sha256: str
    wrapper_jar_sha256: str
    wrapper_script_sha256: str
    distribution_cache_key: str


_GRADLE_9_5_POLICY = _WrapperPolicy(
    version="9.5.0",
    distribution_url_property=(
        "https\\://services.gradle.org/distributions/gradle-9.5.0-bin.zip"
    ),
    distribution_url=(
        "https://services.gradle.org/distributions/gradle-9.5.0-bin.zip"
    ),
    distribution_sha256=(
        "553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746"
    ),
    wrapper_jar_sha256=(
        "497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7"
    ),
    wrapper_script_sha256=(
        "ab5c0cad16305af2e619c159c1f58dd68d07fab9c11e36701e109c0277407f7a"
    ),
    distribution_cache_key="bvnork1r7n8i6kp5cnkibsc9q",
)
SUPPORTED_WRAPPER_VERSIONS: Mapping[str, _WrapperPolicy] = MappingProxyType({
    _GRADLE_9_5_POLICY.version: _GRADLE_9_5_POLICY,
})

_EXPECTED_PROPERTIES = MappingProxyType({
    "distributionBase": "GRADLE_USER_HOME",
    "distributionPath": "wrapper/dists",
    "distributionSha256Sum": _GRADLE_9_5_POLICY.distribution_sha256,
    "distributionUrl": _GRADLE_9_5_POLICY.distribution_url_property,
    "networkTimeout": "10000",
    "retries": "0",
    "retryBackOffMs": "500",
    "validateDistributionUrl": "true",
    "zipStoreBase": "GRADLE_USER_HOME",
    "zipStorePath": "wrapper/dists",
})


class _GradlePolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message


def _failure(code: str, message: str) -> ToolResult:
    return ToolResult(
        False,
        TOOL_ID,
        message,
        error_code=code,
        metadata={
            "command_family": COMMAND_FAMILY,
            "exit_code": None,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "output_truncated": False,
        },
    )


def _regular_file(path: Path, *, code: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise _GradlePolicyError(code, "Required Gradle wrapper component is unavailable")


def _sha256(path: Path, *, maximum_bytes: int, code: str) -> str:
    try:
        size = path.stat().st_size
        if size <= 0 or size > maximum_bytes:
            raise _GradlePolicyError(code, "Gradle wrapper component size is invalid")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except _GradlePolicyError:
        raise
    except (OSError, ValueError):
        raise _GradlePolicyError(code, "Gradle wrapper component could not be read") from None


def _canonical_project_root(project_path: object, workspace: Workspace) -> Path:
    if not isinstance(project_path, str) or not project_path or "\x00" in project_path:
        raise _GradlePolicyError("invalid_project_path", "Project path is invalid")
    requested = Path(project_path)
    if ".." in requested.parts or "~" in requested.parts:
        raise _GradlePolicyError("project_path_not_allowed", "Project path is not allowed")

    expected = requested if requested.is_absolute() else workspace.root / requested
    expected = Path(os.path.abspath(expected))
    if not expected.is_relative_to(workspace.root):
        raise _GradlePolicyError("project_path_not_allowed", "Project path is not allowed")

    current = workspace.root
    for part in expected.relative_to(workspace.root).parts:
        current /= part
        if current.is_symlink():
            raise _GradlePolicyError("unsafe_project_symlink", "Project path uses a symlink")
    try:
        resolved = expected.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise _GradlePolicyError("project_not_found", "Project root does not exist") from None
    if resolved != expected:
        raise _GradlePolicyError("unsafe_project_symlink", "Project path uses a symlink")
    if not resolved.is_dir():
        raise _GradlePolicyError("project_not_directory", "Project root is not a directory")
    return resolved


def _parse_properties(path: Path) -> dict[str, str]:
    try:
        raw = path.read_bytes()
    except OSError:
        raise _GradlePolicyError(
            "wrapper_properties_unreadable",
            "Gradle wrapper properties could not be read",
        ) from None
    if not raw or len(raw) > MAX_PROPERTIES_BYTES or b"\x00" in raw:
        raise _GradlePolicyError(
            "wrapper_properties_invalid",
            "Gradle wrapper properties are invalid",
        )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise _GradlePolicyError(
            "wrapper_properties_invalid",
            "Gradle wrapper properties are invalid",
        ) from None

    properties: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")):
            continue
        if "=" not in stripped:
            raise _GradlePolicyError(
                "wrapper_properties_invalid",
                "Gradle wrapper properties are invalid",
            )
        key, value = (part.strip() for part in stripped.split("=", 1))
        if not key or key in properties:
            raise _GradlePolicyError(
                "wrapper_properties_invalid",
                "Gradle wrapper properties are invalid",
            )
        properties[key] = value
    return properties


def _validate_project_gradle_properties(project_root: Path) -> None:
    path = project_root / "gradle.properties"
    if not path.exists():
        return
    _regular_file(path, code="unsafe_gradle_properties")
    properties = _parse_properties(path)
    for key in properties:
        if key.startswith(_DANGEROUS_GRADLE_PROPERTY_PREFIXES):
            raise _GradlePolicyError(
                "unsafe_gradle_properties",
                "Project Gradle properties contain an unsafe execution setting",
            )
        if key.startswith("org.gradle.") and key not in _SAFE_PROJECT_GRADLE_PROPERTIES:
            raise _GradlePolicyError(
                "unsafe_gradle_properties",
                "Project Gradle properties contain an unsupported execution setting",
            )


def _validate_wrapper(project_root: Path) -> _WrapperPolicy:
    wrapper = project_root / "gradlew"
    wrapper_jar = project_root / "gradle" / "wrapper" / "gradle-wrapper.jar"
    properties_path = project_root / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not wrapper.exists():
        raise _GradlePolicyError("missing_gradlew", "Gradle wrapper script is missing")
    if not wrapper_jar.exists():
        raise _GradlePolicyError("missing_wrapper_jar", "Gradle wrapper JAR is missing")
    if not properties_path.exists():
        raise _GradlePolicyError(
            "missing_wrapper_properties",
            "Gradle wrapper properties are missing",
        )
    _regular_file(wrapper, code="unsafe_gradlew")
    _regular_file(wrapper_jar, code="unsafe_wrapper_jar")
    _regular_file(properties_path, code="unsafe_wrapper_properties")
    if not os.access(wrapper, os.X_OK):
        raise _GradlePolicyError("gradlew_not_executable", "Gradle wrapper is not executable")

    properties = _parse_properties(properties_path)
    distribution_hash = properties.get("distributionSha256Sum", "")
    if len(distribution_hash) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in distribution_hash
    ):
        raise _GradlePolicyError(
            "invalid_distribution_sha256",
            "Gradle distribution SHA-256 is missing or invalid",
        )
    raw_url = properties.get("distributionUrl", "")
    policy = next(
        (
            item
            for item in SUPPORTED_WRAPPER_VERSIONS.values()
            if item.distribution_url_property == raw_url
        ),
        None,
    )
    if policy is None:
        if not raw_url.startswith("https\\://"):
            raise _GradlePolicyError(
                "unsafe_wrapper_url",
                "Gradle wrapper distribution URL is not trusted",
            )
        raise _GradlePolicyError(
            "unsupported_gradle_version",
            "Gradle wrapper version is not supported",
        )
    if dict(properties) != dict(_EXPECTED_PROPERTIES):
        if distribution_hash.lower() != policy.distribution_sha256:
            raise _GradlePolicyError(
                "distribution_sha256_mismatch",
                "Gradle distribution SHA-256 is not allowlisted",
            )
        raise _GradlePolicyError(
            "wrapper_properties_not_allowed",
            "Gradle wrapper configuration is not allowlisted",
        )
    if _sha256(
        wrapper,
        maximum_bytes=MAX_WRAPPER_SCRIPT_BYTES,
        code="unsafe_gradlew",
    ) != policy.wrapper_script_sha256:
        raise _GradlePolicyError("untrusted_gradlew", "Gradle wrapper script is not trusted")
    if _sha256(
        wrapper_jar,
        maximum_bytes=MAX_WRAPPER_JAR_BYTES,
        code="unsafe_wrapper_jar",
    ) != policy.wrapper_jar_sha256:
        raise _GradlePolicyError("untrusted_wrapper_jar", "Gradle wrapper JAR is not trusted")

    for local_init in (
        project_root / "init.gradle",
        project_root / "init.gradle.kts",
        project_root / "init.d",
    ):
        if local_init.exists() or local_init.is_symlink():
            raise _GradlePolicyError(
                "project_init_script_not_allowed",
                "Project-local Gradle init scripts are not allowed",
            )
    _validate_project_gradle_properties(project_root)
    return policy


def _validate_android_sdk() -> Path:
    expected = Path(os.path.abspath(_TRUSTED_ANDROID_SDK_ROOT))
    try:
        resolved = expected.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise _GradlePolicyError(
            "android_sdk_unavailable",
            "Trusted Android SDK is unavailable",
        ) from None
    if resolved != expected or resolved.is_symlink() or not resolved.is_dir():
        raise _GradlePolicyError("android_sdk_unavailable", "Trusted Android SDK is unavailable")
    platform_jars = (
        resolved / "platforms" / "android-37" / "android.jar",
        resolved / "platforms" / "android-37.0" / "android.jar",
    )
    if not any(path.is_file() and not path.is_symlink() for path in platform_jars):
        raise _GradlePolicyError(
            "android_sdk_incomplete",
            "Trusted Android SDK platform 37 is unavailable",
        )
    return resolved


def _validate_aapt2_override() -> Path:
    expected_root = Path(os.path.abspath(_TRUSTED_AAPT2_ROOT))
    try:
        root = expected_root.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise _GradlePolicyError(
            "aapt2_unavailable",
            "Trusted AAPT2 override is unavailable",
        ) from None
    if root != expected_root or root.is_symlink() or not root.is_dir():
        raise _GradlePolicyError("aapt2_unavailable", "Trusted AAPT2 override is unavailable")
    expected_files = (
        (
            root / "bin" / "aapt2",
            64 * 1024,
            "936b1a503b433bb3b7293a66c40634935da71baa71a990b524aa9c27aaa55fb7",
        ),
        (
            root / "usr" / "bin" / "qemu-x86_64-static",
            8 * 1024 * 1024,
            "de72ec1143909f0f495a53c36d9215cb86e2952517aad87044c741a1088dc60f",
        ),
        (
            root / "x86" / "aapt2-real",
            8 * 1024 * 1024,
            "baf6784be1b4284da49c78ea2f6961b0c525d56ecf57f1f1d879ca264dc96197",
        ),
    )
    for path, maximum_bytes, expected_hash in expected_files:
        if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
            raise _GradlePolicyError(
                "aapt2_unavailable",
                "Trusted AAPT2 override is unavailable",
            )
        if _sha256(
            path,
            maximum_bytes=maximum_bytes,
            code="aapt2_unavailable",
        ) != expected_hash:
            raise _GradlePolicyError(
                "untrusted_aapt2",
                "AAPT2 override does not match the trusted configuration",
            )
    guest_root = root / "guest"
    if guest_root.is_symlink() or not guest_root.is_dir():
        raise _GradlePolicyError("aapt2_unavailable", "Trusted AAPT2 override is unavailable")
    return root / "bin" / "aapt2"


def _validate_distribution_cache(policy: _WrapperPolicy) -> Path:
    distribution_root = (
        _TRUSTED_GRADLE_HOME
        / "wrapper"
        / "dists"
        / f"gradle-{policy.version}-bin"
        / policy.distribution_cache_key
    )
    extracted = distribution_root / f"gradle-{policy.version}"
    marker = distribution_root / f"gradle-{policy.version}-bin.zip.ok"
    launcher = extracted / "bin" / "gradle"
    if (
        distribution_root.is_symlink()
        or extracted.is_symlink()
        or not extracted.is_dir()
        or marker.is_symlink()
        or not marker.is_file()
        or launcher.is_symlink()
        or not launcher.is_file()
        or not os.access(launcher, os.X_OK)
    ):
        raise _GradlePolicyError(
            "gradle_distribution_not_cached",
            "Supported Gradle distribution is not available in the trusted cache",
        )
    init_directory = extracted / "init.d"
    if init_directory.is_symlink() or not init_directory.is_dir():
        raise _GradlePolicyError(
            "unsafe_gradle_distribution",
            "Cached Gradle distribution is not trusted",
        )
    init_entries = tuple(sorted(path.name for path in init_directory.iterdir()))
    readme = init_directory / "readme.txt"
    if init_entries != ("readme.txt",) or _sha256(
        readme,
        maximum_bytes=1024,
        code="unsafe_gradle_distribution",
    ) != "16cf9450804c97d225bac3e2512583b628a139179fe9c6151d1a23166b66cd23":
        raise _GradlePolicyError(
            "unsafe_gradle_distribution",
            "Cached Gradle distribution contains an untrusted init script",
        )
    return distribution_root


def _prepare_controlled_gradle_home(destination: Path) -> None:
    for name in ("caches", "jdks", "wrapper"):
        source = _TRUSTED_GRADLE_HOME / name
        if source.is_symlink() or not source.is_dir():
            raise _GradlePolicyError(
                "gradle_cache_unavailable",
                "Trusted Gradle cache is unavailable",
            )
        (destination / name).symlink_to(source, target_is_directory=True)
    (destination / "gradle.properties").write_text(
        f"android.aapt2FromMavenOverride={_TRUSTED_AAPT2_ROOT / 'bin' / 'aapt2'}\n"
        "org.gradle.java.installations.auto-download=false\n"
        "org.gradle.daemon=false\n",
        encoding="utf-8",
    )


def _safe_environment(gradle_home: Path, android_sdk: Path) -> dict[str, str]:
    return {
        "ANDROID_HOME": str(android_sdk),
        "ANDROID_SDK_ROOT": str(android_sdk),
        "CI": "true",
        "GRADLE_USER_HOME": str(gradle_home),
        "HOME": str(gradle_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": SAFE_SYSTEM_PATH,
        "TERM": "dumb",
    }


def validate_gradle_project(
    project_path: object,
    *,
    workspace: Workspace,
) -> tuple[Path, _WrapperPolicy, Path]:
    """Validate a project and its fixed wrapper without executing it."""

    project_root = _canonical_project_root(project_path, workspace)
    policy = _validate_wrapper(project_root)
    android_sdk = _validate_android_sdk()
    _validate_aapt2_override()
    _validate_distribution_cache(policy)
    return project_root, policy, android_sdk


def gradle_test(
    project_path: object,
    approved: object = False,
    timeout_seconds: object = DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: object = DEFAULT_MAX_OUTPUT_BYTES,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    """Run one fixed Android JVM unit-test task through an allowlisted wrapper."""

    if not isinstance(approved, bool):
        return _failure("invalid_arguments", "Approval must be a boolean")
    if not approved:
        return _failure("approval_required", "Explicit approval is required")
    try:
        timeout = _bounded_number(
            timeout_seconds,
            default=DEFAULT_TIMEOUT_SECONDS,
            maximum=MAX_TIMEOUT_SECONDS,
            name="timeout_seconds",
        )
        output_limit = _bounded_number(
            max_output_bytes,
            default=DEFAULT_MAX_OUTPUT_BYTES,
            maximum=MAX_OUTPUT_BYTES,
            name="max_output_bytes",
        )
        if not isinstance(output_limit, int):
            raise CommandPolicyError("invalid_arguments", "max_output_bytes must be an integer")
        active_workspace = workspace or Workspace()
        project_root, policy, android_sdk = validate_gradle_project(
            project_path,
            workspace=active_workspace,
        )
    except CommandPolicyError as exc:
        return _failure(exc.code, exc.message)
    except _GradlePolicyError as exc:
        return _failure(exc.code, exc.message)
    except Exception:
        return _failure("validation_failed", "Gradle project validation failed safely")

    try:
        with tempfile.TemporaryDirectory(prefix="jarvis-gradle-") as temporary:
            controlled_home = Path(temporary)
            _prepare_controlled_gradle_home(controlled_home)
            result = _execute_fixed_argv(
                (str(project_root / "gradlew"), *FIXED_ARGUMENTS),
                cwd=project_root,
                environment=_safe_environment(controlled_home, android_sdk),
                timeout=timeout,
                output_limit=output_limit,
                tool_id=TOOL_ID,
                command_family=COMMAND_FAMILY,
            )
    except _GradlePolicyError as exc:
        return _failure(exc.code, exc.message)
    except Exception:
        return _failure("execution_failed", "Gradle verification failed safely")

    metadata = dict(result.metadata)
    metadata.update({
        "gradle_version": policy.version,
        "project_path": str(project_root),
        "task": FIXED_TASK,
    })
    error_code = result.error_code
    if (
        not result.success
        and result.error_code == "command_failed"
        and "No cached version available for offline mode" in result.output
    ):
        error_code = "offline_cache_miss"
    return ToolResult(
        result.success,
        TOOL_ID,
        result.output,
        error_code=error_code,
        metadata=metadata,
    )
