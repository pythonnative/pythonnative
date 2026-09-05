"""Platform-aware constants and selectors.

A small, RN-style helper for branching app code on the host platform.
The public surface is the [`Platform`][pythonnative.Platform] class
exposing ``OS``, ``Version``, ``is_ios``, ``is_android``, ``is_web``,
and ``select`` so user code can write ``Platform.select({"ios": ..., ...})``
without importing the ``IS_*`` flags directly.

Example:
    ```python
    import pythonnative as pn

    title_size = pn.Platform.select({"ios": 17, "android": 16, "default": 16})

    @pn.component
    def App():
        return pn.Text(
            f"Running on {pn.Platform.OS} {pn.Platform.Version}",
            style={"font_size": title_size},
        )
    ```
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

from .utils import IS_ANDROID, IS_IOS, IS_WEB


def _detect_os() -> str:
    if IS_ANDROID:
        return "android"
    if IS_IOS:
        return "ios"
    if IS_WEB:
        return "web"
    return "test"


def _detect_version() -> str:
    """Return a human-readable platform version string.

    On device this asks the native ``Device`` module (``UIDevice
    .systemVersion`` / ``Build.VERSION.RELEASE``); the browser preview
    answers with the browser's user agent family. Off-device (the test
    environment), returns the host Python's version so user code can
    still introspect *something*.
    """
    if IS_IOS or IS_ANDROID or IS_WEB:
        try:
            from .native_modules.registry import native_module

            info = native_module("Device").call("info")
            if isinstance(info, dict) and info.get("os_version"):
                return str(info["os_version"])
        except Exception:
            pass
        sim_version = os.environ.get("SIMULATOR_RUNTIME_VERSION")
        if sim_version:
            return sim_version
    return f"python-{sys.version_info.major}.{sys.version_info.minor}"


class _LazyVersion:
    """Resolve ``Platform.Version`` on first access (it needs the bridge on device)."""

    _value: Optional[str] = None

    def __get__(self, obj: object, owner: Optional[type] = None) -> str:
        if _LazyVersion._value is None:
            _LazyVersion._value = _detect_version()
        return _LazyVersion._value


class Platform:
    """Platform-aware constants and the ``select`` dispatcher.

    All attributes are read at import time. ``OS`` is one of
    ``"ios"``, ``"android"``, ``"web"`` (the browser preview), or
    ``"test"`` (when running off-device, e.g., in unit tests).
    """

    OS: str = _detect_os()
    """``"ios"``, ``"android"``, ``"web"``, or ``"test"``."""

    Version: str = _LazyVersion()  # type: ignore[assignment]
    """Best-effort OS version string (``"17.4"``, ``"14"``, ``"python-3.11"``)."""

    is_ios: bool = IS_IOS
    """``True`` when running inside an iOS app bundle."""

    is_android: bool = IS_ANDROID
    """``True`` when running inside an Android process."""

    is_web: bool = IS_WEB
    """``True`` when running the browser preview (``pn preview``)."""

    is_test: bool = OS == "test"
    """``True`` when running off-device (no native runtime)."""

    @staticmethod
    def select(spec: Dict[str, Any], default: Any = None) -> Any:
        """Pick the value matching the current platform.

        Looks up ``spec[Platform.OS]``, then falls back to
        ``spec["native"]`` (matches iOS and Android, *not* the browser
        preview, which is a development surface), then to
        ``spec["default"]``, then to the explicit ``default`` argument.

        Args:
            spec: Mapping from platform name to value. Recognized keys:
                ``"ios"``, ``"android"``, ``"web"``, ``"test"``,
                ``"native"``, ``"default"``.
            default: Value returned when ``spec`` has no matching key
                and no ``"default"`` entry.

        Returns:
            The matching value, or ``default`` when nothing matches.

        Example:
            ```python
            font = pn.Platform.select(
                {"ios": "Helvetica", "android": "Roboto", "default": None}
            )
            ```
        """
        if Platform.OS in spec:
            return spec[Platform.OS]
        if (Platform.is_ios or Platform.is_android) and "native" in spec:
            return spec["native"]
        if "default" in spec:
            return spec["default"]
        return default


def get_platform() -> str:
    """Return the active platform name.

    Equivalent to reading ``Platform.OS``, exposed as a function for
    introspection from non-component code.
    """
    return Platform.OS


def _set_platform_for_test(name: Optional[str]) -> None:
    """Override ``Platform.OS`` for unit tests.

    Production code should not call this. Tests can pass ``"ios"``,
    ``"android"``, ``"web"``, ``"test"``, or ``None`` (to reset to
    autodetect).
    """
    if name is None:
        Platform.OS = _detect_os()
        Platform.is_ios = IS_IOS
        Platform.is_android = IS_ANDROID
        Platform.is_web = IS_WEB
        Platform.is_test = Platform.OS == "test"
        return
    Platform.OS = name
    Platform.is_ios = name == "ios"
    Platform.is_android = name == "android"
    Platform.is_web = name == "web"
    Platform.is_test = name == "test"
