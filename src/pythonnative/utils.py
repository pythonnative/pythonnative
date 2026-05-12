"""Platform detection and shared helpers.

This module is imported early by most other modules, so it avoids
importing platform-specific packages at module level. The detection
results are cached the first time
[`IS_ANDROID`][pythonnative.utils.IS_ANDROID] and
[`IS_IOS`][pythonnative.utils.IS_IOS] are read.

The Android variants also expose a small global registry for the
current `Activity` / `Context` and the screen's fragment container view;
both are populated by the bundled Android template before any
PythonNative code runs.

Attributes:
    IS_ANDROID: `True` when running inside an Android process (either
        because `ANDROID_*` env vars are present or because Chaquopy's
        `java` module imports successfully).
    IS_IOS: `True` when running inside an iOS app bundle (signaled by
        `PN_PLATFORM=ios`, `sys.platform == "ios"`, or a Simulator
        `HOME` path). Importing `rubicon-objc` alone is intentionally
        not enough to trigger this flag.
"""

import os
import sys
from typing import Any, Optional

# ======================================================================
# Platform detection
# ======================================================================

_is_android: Optional[bool] = None
_is_ios: Optional[bool] = None


def _detect_android() -> bool:
    """Return whether we're running inside an Android process."""
    env = os.environ
    if "ANDROID_BOOTLOGO" in env or "ANDROID_ROOT" in env or "ANDROID_DATA" in env or "ANDROID_ARGUMENT" in env:
        return True
    try:
        from java import jclass  # noqa: F401

        return True
    except Exception:
        pass
    return False


def _detect_ios() -> bool:
    """Detect whether we're running inside an iOS app bundle.

    Signals, in priority order:

    - Explicit `PN_PLATFORM=ios` env var (set by the iOS template's
      `ViewController.swift` before Python starts). This is the
      canonical signal and survives even on hosts where `sys.platform`
      is generic `darwin`.
    - `sys.platform == "ios"` (CPython 3.13+ native iOS builds).
    - `/CoreSimulator/Devices/` in `$HOME` (iOS Simulator fallback if
      the template signal is missing for some reason).

    Crucially, having `rubicon-objc` importable is *not* enough:
    developers frequently install it on macOS via the `[ios]` extra,
    and treating that as iOS would cause subtle side effects
    (e.g., stdout redirection) on desktop machines.
    """
    if os.environ.get("PN_PLATFORM") == "ios":
        return True
    if sys.platform == "ios":
        return True
    home = os.environ.get("HOME", "")
    if "/CoreSimulator/Devices/" in home:
        return True
    return False


def _ensure_platform_detection() -> None:
    """Populate `_is_android` / `_is_ios` once, then reuse."""
    global _is_android, _is_ios
    if _is_android is None:
        _is_android = _detect_android()
    if _is_ios is None:
        _is_ios = (not _is_android) and _detect_ios()


def _get_is_android() -> bool:
    """Return the cached Android-detection result."""
    _ensure_platform_detection()
    assert _is_android is not None
    return _is_android


def _get_is_ios() -> bool:
    """Return the cached iOS-detection result."""
    _ensure_platform_detection()
    assert _is_ios is not None
    return _is_ios


IS_ANDROID: bool = _get_is_android()
"""``True`` when running inside an Android process.

The flag is computed once at import time, by checking for `ANDROID_*`
environment variables and trying to import Chaquopy's `java` module.
"""

IS_IOS: bool = _get_is_ios()
"""``True`` when running inside an iOS app bundle.

The flag is computed once at import time, by checking
`PN_PLATFORM=ios`, `sys.platform == "ios"`, and the iOS Simulator
`HOME` path.
"""

# ======================================================================
# Android context management
# ======================================================================

_android_context: Any = None
_android_fragment_container: Any = None


def set_android_context(context: Any) -> None:
    """Record the current Android `Activity`/`Context`.

    Called by the bundled Android template before any view is created;
    most app code should not call this directly.

    Args:
        context: A Java `android.content.Context` (typically the
            current `Activity`).
    """
    global _android_context
    _android_context = context


def set_android_fragment_container(container_view: Any) -> None:
    """Record the current `Fragment` root container `ViewGroup`.

    Args:
        container_view: A Java `android.view.ViewGroup` that holds the
            screen's view tree.
    """
    global _android_fragment_container
    _android_fragment_container = container_view


def get_android_context() -> Any:
    """Return the current Android `Activity`/`Context`.

    Returns:
        The most recently recorded Android context.

    Raises:
        RuntimeError: If called on a non-Android platform, or before
            the template has registered a context.
    """
    if not IS_ANDROID:
        raise RuntimeError("get_android_context() called on non-Android platform")
    if _android_context is None:
        raise RuntimeError(
            "Android context not set. Ensure the screen host is initialized from an Activity before constructing views."
        )
    return _android_context


def get_android_fragment_container() -> Any:
    """Return the current `Fragment` container `ViewGroup`.

    Returns:
        The most recently recorded fragment container view.

    Raises:
        RuntimeError: If called on a non-Android platform, or before
            `ScreenFragment` has registered its container.
    """
    if not IS_ANDROID:
        raise RuntimeError("get_android_fragment_container() called on non-Android platform")
    if _android_fragment_container is None:
        raise RuntimeError(
            "Android fragment container not set. Ensure ScreenFragment has been created before set_root_view."
        )
    return _android_fragment_container
