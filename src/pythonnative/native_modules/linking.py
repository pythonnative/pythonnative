"""Open URLs, deep links, and the system settings page.

[`Linking`][pythonnative.Linking] wraps ``UIApplication.openURL`` /
``Intent(ACTION_VIEW)`` so a Python app can hand a URL (``https:``,
``mailto:``, ``tel:``, a custom scheme, …) to the OS.

Outbound methods are synchronous and return a ``bool`` describing
whether the platform accepted the request. On desktop they return
``False``.

Inbound deep links flow the other way: declare your schemes in
``pythonnative.toml`` (``app.url_schemes``) and the native host calls
[`dispatch_url`][pythonnative.native_modules.linking.dispatch_url] for
every URL that opens the app. The URL that cold-started the app is kept
and returned by ``get_initial_url``; later URLs reach subscribers added
with ``add_listener``.

Example:
    ```python
    import pythonnative as pn

    if url := pn.Linking.get_initial_url():
        navigate_to(url)

    unsubscribe = pn.Linking.add_listener(navigate_to)
    ```
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from ..utils import IS_ANDROID, IS_IOS

# Populated by the native host when the app is launched from a deep
# link; ``get_initial_url`` returns it.
_initial_url: Optional[str] = None
_url_listeners: List[Callable[[str], None]] = []


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

    @staticmethod
    def add_listener(callback: Callable[[str], None]) -> Callable[[], None]:
        """Subscribe to deep links that arrive while the app is running.

        Args:
            callback: Called with the full URL string for every inbound
                deep link (including the initial one, which is
                dispatched right after startup).

        Returns:
            A zero-arg function that unsubscribes when called.
        """
        _url_listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                _url_listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


def set_initial_url(url: Optional[str]) -> None:
    """Record the launch URL (called by the native host on cold start)."""
    global _initial_url
    _initial_url = url


def dispatch_url(url: str) -> None:
    """Deliver an inbound deep link from the native host.

    The first URL ever dispatched is also recorded as the initial URL
    (a cold start from a deep link reaches Python only after the
    interpreter boots, so the host can't call ``set_initial_url``
    earlier than this).

    Args:
        url: The full URL string that opened the app.
    """
    global _initial_url
    if _initial_url is None:
        _initial_url = url
    for listener in list(_url_listeners):
        try:
            listener(url)
        except Exception as exc:
            from .. import diagnostics

            diagnostics.warn(f"Linking listener raised while handling {url!r}: {exc!r}")


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
