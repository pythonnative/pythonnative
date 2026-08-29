"""Environment diagnostics for ``pn doctor``.

Inspects the local toolchain and the project's ``pythonnative.toml`` and
reports what's ready and what's missing for building on each platform,
analogous to ``flutter doctor`` / ``npx react-native doctor``. The checks
are deliberately read-only and fast; they shell out only to ask tools for
their versions.
"""

from __future__ import annotations

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


def _tkinter_available() -> bool:
    """Return whether the host Python can import Tkinter."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


def check_common() -> List[CheckResult]:
    """Run platform-agnostic checks (interpreter and optional dependencies).

    Returns:
        Check results for the host Python and optional dependencies.
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
    if _tkinter_available():
        results.append(CheckResult("Tkinter (desktop preview)", OK))
    else:
        results.append(
            CheckResult(
                "Tkinter (desktop preview)",
                WARN,
                "not installed; macOS: brew install python-tk; Debian/Ubuntu: sudo apt-get install python3-tk; "
                "Windows: reinstall Python with the 'tcl/tk' option checked",
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

    java_home = shutil.which("java")
    import os

    if os.environ.get("JAVA_HOME") or java_home:
        results.append(CheckResult("Java (JDK 17 recommended)", OK, os.environ.get("JAVA_HOME") or java_home or ""))
    else:
        results.append(CheckResult("Java (JDK 17 recommended)", WARN, "JAVA_HOME not set and 'java' not on PATH"))

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
    results.append(CheckResult("Xcode (xcodebuild)", OK if xcodebuild else ERROR, xcodebuild or "not found on PATH"))
    simctl = shutil.which("xcrun")
    results.append(CheckResult("xcrun simctl (Simulators)", OK if simctl else WARN, simctl or "not found on PATH"))

    if config is not None:
        if config.python_version not in PINNED_ASSETS:
            supported = ", ".join(sorted(PINNED_ASSETS))
            results.append(
                CheckResult(
                    "iOS embedded Python",
                    WARN,
                    f"app.python_version={config.python_version}; pinned iOS builds " f"exist for {supported}",
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
    results.extend(check_common())
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
