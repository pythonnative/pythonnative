"""Environment diagnostics for ``pn doctor``.

Inspects the local toolchain and the project's ``pythonnative.toml`` and
reports what's ready and what's missing for building on each platform,
analogous to ``flutter doctor`` / ``npx react-native doctor``. The checks
are deliberately read-only and fast; they shell out only to ask tools for
their versions.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import icons
from .config import SUPPORTED_PYTHON_VERSIONS, AppConfig, ConfigError
from .runtime_assets import PINNED_ASSETS

OK = "ok"
WARN = "warn"
ERROR = "error"
INFO = "info"

_SYMBOLS = {OK: "[ok]", WARN: "[!]", ERROR: "[x]", INFO: "[i]"}


@dataclass
class CheckResult:
    """The outcome of a single diagnostic check.

    Attributes:
        name: Short label for the thing checked.
        level: One of ``"ok"``, ``"warn"``, ``"error"``, ``"info"``.
        detail: Human-readable detail / remediation hint.
    """

    name: str
    level: str
    detail: str = ""

    def format(self) -> str:
        """Return a single aligned line for terminal output."""
        symbol = _SYMBOLS.get(self.level, "[?]")
        suffix = f": {self.detail}" if self.detail else ""
        return f"  {symbol} {self.name}{suffix}"

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable view of this check for ``--json``."""
        return {"name": self.name, "level": self.level, "message": self.detail}


def _which_version(tool: str, version_args: List[str]) -> Optional[str]:
    path = shutil.which(tool)
    if not path:
        return None
    try:
        out = subprocess.run([tool, *version_args], capture_output=True, text=True, timeout=20)
    except Exception:
        return path
    text = (out.stdout or out.stderr or "").strip().splitlines()
    return text[0] if text else path


def build_python_for(python_version: str) -> Optional[str]:
    """Locate an interpreter matching ``python_version`` (e.g. ``python3.13``) on ``PATH``.

    Args:
        python_version: CPython ``major.minor``.

    Returns:
        The interpreter path, or ``None`` when none is installed.
    """
    host = f"{sys.version_info.major}.{sys.version_info.minor}"
    if host == python_version:
        return sys.executable
    return shutil.which(f"python{python_version}")


def check_common(config: Optional[AppConfig] = None) -> List[CheckResult]:
    """Run platform-agnostic checks (interpreters, requirements, optional dependencies).

    Args:
        config: The loaded app config, or ``None`` if unavailable.

    Returns:
        Check results for the host and build Pythons, the declared
        requirements, and optional dependencies.
    """
    results: List[CheckResult] = []
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if py_version in SUPPORTED_PYTHON_VERSIONS:
        results.append(CheckResult("Host Python", OK, f"{sys.version.split()[0]}"))
    else:
        results.append(
            CheckResult(
                "Host Python",
                WARN,
                f"{py_version} (PythonNative targets {', '.join(SUPPORTED_PYTHON_VERSIONS)})",
            )
        )

    if config is not None:
        # pip cross-resolves iOS wheels from any interpreter, but Chaquopy
        # needs a matching python3.X on the build machine whenever there
        # are requirements, and release bytecode is version-specific.
        build_python = build_python_for(config.python_version)
        label = f"Build Python {config.python_version} (matches app.python_version)"
        if build_python:
            results.append(CheckResult(label, OK, build_python))
        else:
            level = WARN if config.requirements else INFO
            results.append(
                CheckResult(
                    label,
                    level,
                    f"python{config.python_version} not found on PATH; Android builds with [requirements] and "
                    "release bytecode compilation need it (e.g. uv python install "
                    f"{config.python_version})",
                )
            )
        from . import lockfile
        from .artifacts import ArtifactError, privacy_manifest
        from .deps import DependencyError

        if config.ios.privacy_manifest:
            try:
                privacy_manifest(config.resolve_path(config.ios.privacy_manifest))
                results.append(CheckResult("iOS app privacy manifest", OK, config.ios.privacy_manifest))
            except ArtifactError as exc:
                results.append(CheckResult("iOS app privacy manifest", ERROR, str(exc)))
        if config.requirements:
            try:
                frozen = lockfile.read(config)
                results.append(
                    CheckResult(
                        "Frozen release dependencies",
                        OK if frozen else WARN,
                        "pn.lock found" if frozen else "Run 'pn deps --lock' before release builds.",
                    )
                )
            except (DependencyError, ValueError) as exc:
                results.append(CheckResult("Frozen release dependencies", ERROR, str(exc)))
            count = len(config.requirements)
            results.append(
                CheckResult(
                    "Requirements",
                    INFO,
                    f"{count} package(s) declared; run 'pn deps' to check device wheel availability",
                )
            )

    if icons.pillow_available():
        results.append(CheckResult("Pillow (icon/splash generation)", OK))
    else:
        results.append(
            CheckResult(
                "Pillow (icon/splash generation)",
                WARN,
                "not installed; run: pip install 'pythonnative[build]'",
            )
        )
    return results


def check_android(config: Optional[AppConfig]) -> List[CheckResult]:
    """Run Android toolchain and signing checks.

    Args:
        config: The loaded app config, or ``None`` if unavailable.

    Returns:
        Android-specific check results.
    """
    results: List[CheckResult] = []
    adb = _which_version("adb", ["--version"])
    results.append(CheckResult("adb (Android platform-tools)", OK if adb else WARN, adb or "not found on PATH"))

    import os

    java = _which_version("java", ["-version"])
    match = re.search(r'version "(\d+)', java or "")
    major = int(match.group(1)) if match else None
    results.append(
        CheckResult(
            "Java (JDK 17-23)",
            OK if major is not None and 17 <= major <= 23 else ERROR,
            java if major is not None and 17 <= major <= 23 else "Install JDK 17 or 21 and select it with JAVA_HOME.",
        )
    )
    sdk = Path(
        os.environ.get("ANDROID_HOME")
        or os.environ.get("ANDROID_SDK_ROOT")
        or (Path.home() / "Library/Android/sdk" if sys.platform == "darwin" else Path.home() / "Android/Sdk")
    )
    required = config.android.compile_sdk if config is not None else 36
    for name, path, package in (
        (
            f"Android SDK {required}",
            sdk / "platforms" / f"android-{required}" / "android.jar",
            f"platforms;android-{required}",
        ),
        ("Android NDK 28.2", sdk / "ndk/28.2.13676358/source.properties", "ndk;28.2.13676358"),
    ):
        results.append(
            CheckResult(
                name,
                OK if path.is_file() else ERROR,
                str(path) if path.is_file() else f'Install with sdkmanager "{package}". SDK: {sdk}',
            )
        )
    if config is not None and config.android.target_sdk < 36:
        results.append(CheckResult("Android release target", WARN, "Release builds require target_sdk >= 36."))

    if config is not None:
        signing = config.android.signing
        if signing.is_configured:
            keystore = config.resolve_path(signing.keystore) if signing.keystore else None
            if keystore and keystore.is_file():
                results.append(CheckResult("Android release keystore", OK, str(keystore)))
            else:
                results.append(CheckResult("Android release keystore", ERROR, f"not found: {keystore}"))
            missing = [env for env in (signing.store_password_env, signing.key_password_env) if not os.environ.get(env)]
            if missing:
                results.append(CheckResult("Android signing passwords", WARN, f"unset env: {', '.join(missing)}"))
        else:
            results.append(
                CheckResult(
                    "Android release signing",
                    INFO,
                    "not configured; release builds will be unsigned (set [android.signing])",
                )
            )
    return results


def check_ios(config: Optional[AppConfig]) -> List[CheckResult]:
    """Run iOS toolchain and signing checks.

    Args:
        config: The loaded app config, or ``None`` if unavailable.

    Returns:
        iOS-specific check results.
    """
    results: List[CheckResult] = []
    if sys.platform != "darwin":
        results.append(CheckResult("macOS (required for iOS)", ERROR, f"this is {sys.platform}; iOS builds need macOS"))
        return results

    xcodebuild = _which_version("xcodebuild", ["-version"])
    version = re.search(r"Xcode (\d+)", xcodebuild or "")
    modern = version is not None and int(version.group(1)) >= 26
    results.append(
        CheckResult(
            "Xcode 26 or later",
            OK if modern else ERROR,
            xcodebuild if modern else "Install Xcode 26 or later and select it with xcode-select.",
        )
    )
    simctl = shutil.which("xcrun")
    results.append(CheckResult("xcrun simctl (Simulators)", OK if simctl else WARN, simctl or "not found on PATH"))

    if config is not None:
        if config.python_version not in PINNED_ASSETS:
            supported = ", ".join(sorted(PINNED_ASSETS))
            results.append(
                CheckResult(
                    "iOS embedded Python",
                    WARN,
                    f"app.python_version={config.python_version}; pinned iOS builds exist for {supported}",
                )
            )
        if config.ios.development_team:
            results.append(CheckResult("iOS development team", OK, config.ios.development_team))
        else:
            results.append(
                CheckResult(
                    "iOS development team",
                    INFO,
                    "not set; required for device builds (set [ios].development_team)",
                )
            )
    return results


def check_config(project_root: Path) -> tuple[Optional[AppConfig], List[CheckResult]]:
    """Load and validate the project config, returning it with a result.

    Args:
        project_root: Directory expected to contain ``pythonnative.toml``.

    Returns:
        A tuple of the loaded config (or ``None``) and the check results.
    """
    results: List[CheckResult] = []
    try:
        config = AppConfig.load(project_root)
    except ConfigError as exc:
        results.append(CheckResult("pythonnative.toml", ERROR, str(exc).splitlines()[0]))
        return None, results
    results.append(CheckResult("pythonnative.toml", OK, f"{config.app_id} (v{config.version})"))
    return config, results


def run_doctor(project_root: Path, *, platform: Optional[str] = None) -> List[CheckResult]:
    """Run all diagnostics for ``project_root``.

    Args:
        project_root: The project directory.
        platform: Restrict checks to ``"android"`` or ``"ios"``; ``None``
            checks both.

    Returns:
        All check results in display order.
    """
    config, results = check_config(project_root)
    results.extend(check_common(config))
    if platform in (None, "android"):
        results.extend(check_android(config))
    if platform in (None, "ios"):
        results.extend(check_ios(config))
    return results


def worst_level(results: List[CheckResult]) -> str:
    """Return the most severe level among ``results``.

    Args:
        results: The diagnostic results.

    Returns:
        ``"error"`` if any error, else ``"warn"`` if any warning, else
        ``"ok"``.
    """
    levels = {result.level for result in results}
    if ERROR in levels:
        return ERROR
    if WARN in levels:
        return WARN
    return OK
