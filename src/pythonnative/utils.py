"""Platform detection and shared helpers.

This module is imported early by most other modules, so it avoids
importing platform-specific packages at module level. The detection
results are cached the first time
[`IS_ANDROID`][pythonnative.utils.IS_ANDROID],
[`IS_IOS`][pythonnative.utils.IS_IOS], and
[`IS_WEB`][pythonnative.utils.IS_WEB] are read.

Attributes:
    IS_ANDROID: `True` when running inside an Android process
        (`sys.platform == "android"` on the embedded CPython 3.13+, or
        Chaquopy's `java` module imports successfully).
    IS_IOS: `True` when running inside an iOS app bundle
        (`sys.platform == "ios"` on the embedded CPython 3.13+, or the
        explicit `PN_PLATFORM=ios` override).
    IS_WEB: `True` when running the browser preview (signaled by
        `PN_PLATFORM=web`, set by ``pn preview`` / ``pn start``). The
        reconciler then commits through the bridge to a browser page
        instead of to Swift or Kotlin.
"""

import os
import sys
from typing import Optional

# ======================================================================
# Platform detection
# ======================================================================

_is_android: Optional[bool] = None
_is_ios: Optional[bool] = None
_is_web: Optional[bool] = None


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

    Running on macOS is never enough on its own: the browser preview
    and unit tests run there and must not be mistaken for iOS.
    """
    if sys.platform == "ios":
        return True
    return os.environ.get("PN_PLATFORM") == "ios"


def _detect_web() -> bool:
    """Detect whether we're running the browser preview.

    The only signal is the explicit ``PN_PLATFORM=web`` env var, set by
    ``pn preview`` / ``pn start`` before importing PythonNative. Web is
    a *development* target: the app renders in a browser tab through
    the bridge protocol so the inner dev loop doesn't require a device
    build. Off-device unit tests deliberately leave this flag ``False``
    so they keep using an injected fake backend and
    ``Platform.OS == "test"``.
    """
    return os.environ.get("PN_PLATFORM") == "web"


def _ensure_platform_detection() -> None:
    """Populate `_is_android` / `_is_ios` / `_is_web` once, then reuse."""
    global _is_android, _is_ios, _is_web
    if _is_android is None:
        _is_android = _detect_android()
    if _is_ios is None:
        _is_ios = (not _is_android) and _detect_ios()
    if _is_web is None:
        _is_web = (not _is_android) and (not _is_ios) and _detect_web()


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


def _get_is_web() -> bool:
    """Return the cached web-detection result."""
    _ensure_platform_detection()
    assert _is_web is not None
    return _is_web


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

IS_WEB: bool = _get_is_web()
"""``True`` when running the browser preview.

Set by ``pn preview`` / ``pn start`` via ``PN_PLATFORM=web``. Mutually
exclusive with `IS_ANDROID` / `IS_IOS`. Off-device unit tests leave
this ``False`` and inject a fake backend instead.
"""

IS_NATIVE: bool = IS_ANDROID or IS_IOS or IS_WEB
"""``True`` whenever the reconciler commits through the bridge.

All three of iOS, Android, and the browser preview render through a
bridge transport; only headless tests have no native side at all.
"""
