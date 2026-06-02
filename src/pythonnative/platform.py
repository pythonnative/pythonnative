"""Platform-aware constants and selectors.

A small, RN-style helper for branching app code on the host platform.
The public surface is the [`Platform`][pythonnative.Platform] class
exposing ``OS``, ``Version``, ``is_ios``, ``is_android``, and
``select`` so user code can write ``Platform.select({"ios": ..., ...})``
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

from .utils import IS_ANDROID, IS_DESKTOP, IS_IOS


def _detect_os() -> str:
    if IS_ANDROID:
        return "android"
    if IS_IOS:
        return "ios"
    if IS_DESKTOP:
        return "desktop"
    return "test"


def _detect_version() -> str:
    """Return a human-readable platform version string.

    On iOS, reads the Simulator/device's reported OS version. On
    Android, reads ``Build.VERSION.RELEASE``. Off-device (the test
    environment), returns the host Python's version so user code can
    still introspect *something*.
    """
    if IS_IOS:
        try:
            from rubicon.objc import ObjCClass

            UIDevice = ObjCClass("UIDevice")
            return str(UIDevice.currentDevice.systemVersion)
        except Exception:
            pass
        sim_version = os.environ.get("SIMULATOR_RUNTIME_VERSION")
        if sim_version:
            return sim_version
    if IS_ANDROID:
        try:
            from java import jclass

            Build = jclass("android.os.Build$VERSION")
            return str(Build.RELEASE)
        except Exception:
            pass
    return f"python-{sys.version_info.major}.{sys.version_info.minor}"


class Platform:
    """Platform-aware constants and the ``select`` dispatcher.

    All attributes are read at import time. ``OS`` is one of
    ``"ios"``, ``"android"``, ``"desktop"`` (the Tkinter preview
    backend), or ``"test"`` (when running off-device, e.g., in unit
    tests).
    """

    OS: str = _detect_os()
    """``"ios"``, ``"android"``, ``"desktop"``, or ``"test"``."""

    Version: str = _detect_version()
    """Best-effort OS version string (``"17.4"``, ``"14"``, ``"python-3.11"``)."""

    is_ios: bool = IS_IOS
    """``True`` when running inside an iOS app bundle."""

    is_android: bool = IS_ANDROID
    """``True`` when running inside an Android process."""

    is_desktop: bool = IS_DESKTOP
    """``True`` when running the desktop (Tkinter) preview backend."""

    is_test: bool = OS == "test"
    """``True`` when running off-device (no native runtime)."""

    @staticmethod
    def select(spec: Dict[str, Any], default: Any = None) -> Any:
        """Pick the value matching the current platform.

        Looks up ``spec[Platform.OS]``, then falls back to
        ``spec["native"]`` (matches iOS and Android — *not* desktop,
        which is a development surface), then to ``spec["default"]``,
        then to the explicit ``default`` argument.

        Args:
            spec: Mapping from platform name to value. Recognized keys:
                ``"ios"``, ``"android"``, ``"desktop"``, ``"test"``,
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
    ``"android"``, ``"test"``, or ``None`` (to reset to autodetect).
    """
    if name is None:
        Platform.OS = _detect_os()
        Platform.is_ios = IS_IOS
        Platform.is_android = IS_ANDROID
        Platform.is_desktop = IS_DESKTOP
        Platform.is_test = Platform.OS == "test"
        return
    Platform.OS = name
    Platform.is_ios = name == "ios"
    Platform.is_android = name == "android"
    Platform.is_desktop = name == "desktop"
    Platform.is_test = name == "test"
