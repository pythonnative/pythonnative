"""Open URLs, deep links, and the system settings page.

[`Linking`][pythonnative.Linking] wraps ``UIApplication.openURL`` /
``Intent(ACTION_VIEW)`` (in the native ``Linking`` module) so a Python
app can hand a URL (``https:``, ``mailto:``, ``tel:``, a custom
scheme, ...) to the OS.

Outbound methods are synchronous and return a ``bool`` describing
whether the platform accepted the request. On desktop they return
``False``.

Inbound deep links flow the other way: declare your schemes in
``pythonnative.toml`` (``app.url_schemes``) and the native module
pushes a ``url`` event for every URL that opens the app, which lands in
[`dispatch_url`][pythonnative.native_modules.linking.dispatch_url]. The
URL that cold-started the app is kept and returned by
``get_initial_url``; later URLs reach subscribers added with
``add_listener``.

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

from .registry import native_module, on_event

_initial_url: Optional[str] = None
_url_listeners: List[Callable[[str], None]] = []


def _call_bool(method: str, **args: Any) -> bool:
    try:
        return bool(native_module("Linking").call(method, **args))
    except Exception:
        return False


class Linking:
    """System URL / deep-link interface (synchronous)."""

    @staticmethod
    def open_url(url: str) -> bool:
        """Hand ``url`` to the OS. Returns ``True`` if it was accepted."""
        return _call_bool("open_url", url=url)

    @staticmethod
    def can_open_url(url: str) -> bool:
        """Return ``True`` when some installed app can handle ``url``."""
        return _call_bool("can_open_url", url=url)

    @staticmethod
    def open_settings() -> bool:
        """Open this app's entry in the system Settings app."""
        return _call_bool("open_settings")

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
    """Record the launch URL (or clear it with ``None``)."""
    global _initial_url
    _initial_url = url


def dispatch_url(url: str) -> None:
    """Deliver an inbound deep link.

    The first URL ever dispatched is also recorded as the initial URL
    (a cold start from a deep link reaches Python only after the
    interpreter boots, so native can't report it earlier than this).

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


on_event("Linking", "url", lambda payload: dispatch_url(str(payload)))
