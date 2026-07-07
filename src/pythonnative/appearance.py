"""System color-scheme (light / dark mode) tracking.

The platform screen host publishes the operating system's current
appearance here (Android: ``Configuration.uiMode``; iOS:
``UITraitCollection.userInterfaceStyle``), and components read it back
through [`use_color_scheme`][pythonnative.use_color_scheme] or
[`use_theme`][pythonnative.use_theme], both of which re-render when
the scheme changes.

Apps can also *override* the scheme (e.g. an in-app appearance
setting) with [`set_color_scheme`][pythonnative.appearance.set_color_scheme];
the override wins over the system value until cleared with ``None``.

Example:
    >>> from pythonnative import appearance
    >>> appearance.get_color_scheme()
    'light'
    >>> appearance.set_color_scheme("dark")   # app-level override
    >>> appearance.get_color_scheme()
    'dark'
    >>> appearance.set_color_scheme(None)     # follow the system again
"""

from __future__ import annotations

import threading
from typing import Callable, List, Literal, Optional

ColorScheme = Literal["light", "dark"]
"""The two supported appearance values."""

_system_scheme: str = "light"
_override_scheme: Optional[str] = None

_subscribers: List[Callable[[], None]] = []
_subscribers_lock = threading.Lock()


def _notify_subscribers() -> None:
    """Invoke every registered subscriber, swallowing exceptions."""
    with _subscribers_lock:
        callbacks = list(_subscribers)
    for cb in callbacks:
        try:
            cb()
        except Exception:
            pass


def subscribe(callback: Callable[[], None]) -> Callable[[], None]:
    """Register ``callback`` to fire whenever the effective scheme changes.

    Returns an unsubscribe function. Threadsafe.
    """
    with _subscribers_lock:
        _subscribers.append(callback)

    def _unsub() -> None:
        with _subscribers_lock:
            try:
                _subscribers.remove(callback)
            except ValueError:
                pass

    return _unsub


def _coerce(scheme: object) -> Optional[str]:
    if scheme in ("light", "dark"):
        return str(scheme)
    return None


def set_system_color_scheme(scheme: str) -> None:
    """Publish the operating system's current scheme.

    Called by the platform screen host on create/resume and whenever
    the system reports an appearance change. Invalid values are
    ignored. Subscribers are only notified when the *effective* scheme
    (after any app override) actually changes.
    """
    global _system_scheme
    coerced = _coerce(scheme)
    if coerced is None or coerced == _system_scheme:
        return
    effective_before = get_color_scheme()
    _system_scheme = coerced
    if get_color_scheme() != effective_before:
        _notify_subscribers()


def set_color_scheme(scheme: Optional[str]) -> None:
    """Set (or clear) the app-level scheme override.

    Args:
        scheme: ``"light"`` or ``"dark"`` to force that appearance
            regardless of the system setting, or ``None`` to follow
            the system again.
    """
    global _override_scheme
    coerced = _coerce(scheme) if scheme is not None else None
    if scheme is not None and coerced is None:
        return
    effective_before = get_color_scheme()
    _override_scheme = coerced
    if get_color_scheme() != effective_before:
        _notify_subscribers()


def get_color_scheme() -> str:
    """Return the effective scheme: the app override if set, else the system value."""
    return _override_scheme if _override_scheme is not None else _system_scheme


def get_system_color_scheme() -> str:
    """Return the system-reported scheme, ignoring any app override."""
    return _system_scheme


def reset_color_scheme() -> None:
    """Reset to system ``"light"`` with no override. Intended for tests."""
    global _system_scheme, _override_scheme
    _system_scheme = "light"
    _override_scheme = None
