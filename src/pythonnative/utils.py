"""Platform detection and shared helpers.

This module is imported early by most other modules, so it avoids
importing platform-specific packages at module level. The detection
results are cached the first time
[`IS_ANDROID`][pythonnative.utils.IS_ANDROID] and
[`IS_IOS`][pythonnative.utils.IS_IOS] are read.

Attributes:
    IS_ANDROID: `True` when running inside an Android process
        (`sys.platform == "android"` on the embedded CPython 3.13+, or
        Chaquopy's `java` module imports successfully).
    IS_IOS: `True` when running inside an iOS app bundle
        (`sys.platform == "ios"` on the embedded CPython 3.13+, or the
        explicit `PN_PLATFORM=ios` override).
    IS_DESKTOP: `True` when running the desktop preview backend
        (signaled by `PN_PLATFORM=desktop`, set by ``pn preview``).
        This drives the Tkinter native-view registry so a PythonNative
        app can render in a real OS window for fast local iteration.
"""

import os
import sys
from typing import Optional

# ======================================================================
# Platform detection
# ======================================================================

_is_android: Optional[bool] = None
_is_ios: Optional[bool] = None
_is_desktop: Optional[bool] = None


def _detect_android() -> bool:
    """Return whether we're running inside an Android process.

    CPython 3.13+ reports ``sys.platform == "android"`` (PEP 738); the
    Chaquopy ``java`` module import is kept as a secondary signal.
    """
    if sys.platform == "android":
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

    - `sys.platform == "ios"`: CPython 3.13+ reports this on both
      devices and the Simulator (PEP 730), so it is the canonical
      signal for the embedded runtime.
    - Explicit `PN_PLATFORM=ios` env var: set by the iOS template before
      Python starts as a belt-and-braces override, and by tests.

    Running on macOS is never enough on its own: the desktop preview
    and unit tests run there and must not be mistaken for iOS.
    """
    if sys.platform == "ios":
        return True
    return os.environ.get("PN_PLATFORM") == "ios"


def _detect_desktop() -> bool:
    """Detect whether we're running the desktop (Tkinter) preview backend.

    The only signal is the explicit ``PN_PLATFORM=desktop`` env var,
    set by ``pn preview`` before importing PythonNative. Desktop is a
    *development* target: it renders the app in a native OS window via
    the pure-Python Tkinter registry so the inner dev loop doesn't
    require a device build. Off-device unit tests deliberately leave
    this flag ``False`` so they keep using an injected mock registry
    and ``Platform.OS == "test"``.
    """
    return os.environ.get("PN_PLATFORM") == "desktop"


def _ensure_platform_detection() -> None:
    """Populate `_is_android` / `_is_ios` / `_is_desktop` once, then reuse."""
    global _is_android, _is_ios, _is_desktop
    if _is_android is None:
        _is_android = _detect_android()
    if _is_ios is None:
        _is_ios = (not _is_android) and _detect_ios()
    if _is_desktop is None:
        _is_desktop = (not _is_android) and (not _is_ios) and _detect_desktop()


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


def _get_is_desktop() -> bool:
    """Return the cached desktop-detection result."""
    _ensure_platform_detection()
    assert _is_desktop is not None
    return _is_desktop


IS_ANDROID: bool = _get_is_android()
"""``True`` when running inside an Android process.

The flag is computed once at import time, from ``sys.platform ==
"android"`` or a successful import of Chaquopy's `java` module.
"""

IS_IOS: bool = _get_is_ios()
"""``True`` when running inside an iOS app bundle.

The flag is computed once at import time, from ``sys.platform ==
"ios"`` or the explicit `PN_PLATFORM=ios` override.
"""

IS_DESKTOP: bool = _get_is_desktop()
"""``True`` when running the desktop (Tkinter) preview backend.

Set by ``pn preview`` via ``PN_PLATFORM=desktop``. Mutually exclusive
with `IS_ANDROID` / `IS_IOS`. Off-device unit tests leave this
``False`` and inject a mock registry instead.
"""
