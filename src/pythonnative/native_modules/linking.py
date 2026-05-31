"""Open URLs, deep links, and the system settings page.

[`Linking`][pythonnative.Linking] wraps ``UIApplication.openURL`` /
``Intent(ACTION_VIEW)`` so a Python app can hand a URL (``https:``,
``mailto:``, ``tel:``, a custom scheme, …) to the OS.

All methods are synchronous and return a ``bool`` describing whether
the platform accepted the request. On desktop they return ``False``.

Example:
    ```python
    import pythonnative as pn

    if pn.Linking.can_open_url("tel:+15551234567"):
        pn.Linking.open_url("tel:+15551234567")
    ```
"""

from __future__ import annotations

from typing import Any, Optional

from ..utils import IS_ANDROID, IS_IOS

# Populated by the native host when the app is launched from a deep
# link; ``get_initial_url`` returns it once.
_initial_url: Optional[str] = None


class Linking:
    """System URL / deep-link interface (synchronous)."""

    @staticmethod
    def open_url(url: str) -> bool:
        """Hand ``url`` to the OS. Returns ``True`` if it was accepted."""
        if IS_IOS:
            return _ios_open(url)
        if IS_ANDROID:
            return _android_open(url)
        return False

    @staticmethod
    def can_open_url(url: str) -> bool:
        """Return ``True`` when some installed app can handle ``url``."""
        if IS_IOS:
            return _ios_can_open(url)
        if IS_ANDROID:
            return _android_can_open(url)
        return False

    @staticmethod
    def open_settings() -> bool:
        """Open this app's entry in the system Settings app."""
        if IS_IOS:
            return _ios_open_settings()
        if IS_ANDROID:
            return _android_open_settings()
        return False

    @staticmethod
    def get_initial_url() -> Optional[str]:
        """Return the URL that launched the app, if any."""
        return _initial_url


def set_initial_url(url: Optional[str]) -> None:
    """Record the launch URL (called by the native host on cold start)."""
    global _initial_url
    _initial_url = url


# ======================================================================
# iOS
# ======================================================================


def _ios_url(url: str) -> Optional[Any]:
    try:
        from rubicon.objc import ObjCClass

        return ObjCClass("NSURL").URLWithString_(url)
    except Exception:
        return None


def _ios_open(url: str) -> bool:
    nsurl = _ios_url(url)
    if nsurl is None:
        return False
    try:
        from rubicon.objc import ObjCClass

        app = ObjCClass("UIApplication").sharedApplication
        if app.canOpenURL_(nsurl):
            app.openURL_options_completionHandler_(nsurl, None, None)
            return True
        return False
    except Exception:
        return False


def _ios_can_open(url: str) -> bool:
    nsurl = _ios_url(url)
    if nsurl is None:
        return False
    try:
        from rubicon.objc import ObjCClass

        return bool(ObjCClass("UIApplication").sharedApplication.canOpenURL_(nsurl))
    except Exception:
        return False


def _ios_open_settings() -> bool:
    try:
        from rubicon.objc import ObjCClass

        settings = ObjCClass("UIApplicationOpenSettingsURLString")
        return _ios_open(str(settings))
    except Exception:
        try:
            return _ios_open("app-settings:")
        except Exception:
            return False


# ======================================================================
# Android
# ======================================================================


def _android_open(url: str) -> bool:
    try:
        from java import jclass

        from ..utils import get_android_context

        Intent = jclass("android.content.Intent")
        Uri = jclass("android.net.Uri")
        intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        get_android_context().startActivity(intent)
        return True
    except Exception:
        return False


def _android_can_open(url: str) -> bool:
    try:
        from java import jclass

        from ..utils import get_android_context

        Intent = jclass("android.content.Intent")
        Uri = jclass("android.net.Uri")
        intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        pm = get_android_context().getPackageManager()
        return intent.resolveActivity(pm) is not None
    except Exception:
        return False


def _android_open_settings() -> bool:
    try:
        from java import jclass

        from ..utils import get_android_context

        Intent = jclass("android.content.Intent")
        Settings = jclass("android.provider.Settings")
        Uri = jclass("android.net.Uri")
        ctx = get_android_context()
        intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
        intent.setData(Uri.fromParts("package", ctx.getPackageName(), None))
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(intent)
        return True
    except Exception:
        return False
