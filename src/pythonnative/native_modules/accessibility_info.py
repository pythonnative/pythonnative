"""Screen-reader and reduce-motion state, announcements, and accessibility focus.

[`AccessibilityInfo`][pythonnative.AccessibilityInfo] mirrors React
Native's module of the same name over the native ``AccessibilityInfo``
module (``UIAccessibility`` on iOS, ``AccessibilityManager`` on Android).
The two readers answer from state the OS already holds, so they are
synchronous; ``announce`` and ``set_accessibility_focus`` hand a request
to the OS and return at once. Native pushes a ``change`` event with
``{"screen_reader": bool, "reduce_motion": bool}`` whenever either
setting flips; off device, tests drive the same path through
[`dispatch_accessibility`][pythonnative.native_modules.accessibility_info.dispatch_accessibility].

Prefer the [`use_screen_reader_enabled`][pythonnative.use_screen_reader_enabled]
and [`use_reduce_motion`][pythonnative.use_reduce_motion] hooks inside
components; use the imperative API for non-UI code.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Toast(message: str):
        reduce_motion = pn.use_reduce_motion()
        pn.use_effect(lambda: pn.AccessibilityInfo.announce(message), [message])
        return pn.Text(message, style=pn.style(opacity=1 if reduce_motion else 0.9))
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from .. import diagnostics
from ..hooks import use_subscription
from .registry import native_module, on_event


@dataclass(frozen=True)
class AccessibilityEvent:
    """Snapshot of the two accessibility settings PythonNative tracks.

    Attributes:
        screen_reader: ``True`` while VoiceOver or TalkBack is running.
        reduce_motion: ``True`` while the user asked for reduced motion.
    """

    screen_reader: bool
    reduce_motion: bool


_state: Optional[AccessibilityEvent] = None
_listeners: List[Callable[[AccessibilityEvent], None]] = []


def _resolve_tag(target: Any) -> int:
    """Return the native view tag behind ``target`` (an int, a handle, or a ``Ref``)."""
    if isinstance(target, int) and not isinstance(target, bool):
        return target
    tag = getattr(target, "tag", None)
    if tag is None:
        tag = getattr(getattr(target, "current", None), "tag", None)
    if isinstance(tag, int) and not isinstance(tag, bool):
        return tag
    raise ValueError("set_accessibility_focus needs a Ref attached to a mounted element, a handle, or a view tag")


def _snapshot() -> AccessibilityEvent:
    """Return the cached settings, reading them from native on first use."""
    global _state
    if _state is None:
        module = native_module("AccessibilityInfo")
        _state = AccessibilityEvent(
            screen_reader=bool(module.call("is_screen_reader_enabled")),
            reduce_motion=bool(module.call("is_reduce_motion_enabled")),
        )
    return _state


class AccessibilityInfo:
    """Accessibility settings interface (synchronous readers + change listener).

    Raises:
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def is_screen_reader_enabled() -> bool:
        """Return ``True`` while a screen reader (VoiceOver, TalkBack) is active."""
        return bool(native_module("AccessibilityInfo").call("is_screen_reader_enabled"))

    @staticmethod
    def is_reduce_motion_enabled() -> bool:
        """Return ``True`` while the system Reduce Motion setting is on."""
        return bool(native_module("AccessibilityInfo").call("is_reduce_motion_enabled"))

    @staticmethod
    def announce(message: str) -> None:
        """Ask the screen reader to speak ``message`` (a no-op when none is running)."""
        native_module("AccessibilityInfo").call("announce", message=str(message))

    @staticmethod
    def set_accessibility_focus(ref: Any) -> None:
        """Move screen-reader focus to the element behind ``ref``.

        Args:
            ref: A ``Ref`` passed to a built-in element (its ``current`` is
                the element's handle), a handle with a ``tag``, or a raw
                view tag.

        Raises:
            ValueError: If ``ref`` isn't attached to a mounted element.
        """
        native_module("AccessibilityInfo").call("set_accessibility_focus", tag=_resolve_tag(ref))

    @staticmethod
    def add_listener(callback: Callable[[AccessibilityEvent], None]) -> Callable[[], None]:
        """Subscribe to setting changes; returns an unsubscribe function.

        Each callback receives an
        [`AccessibilityEvent`][pythonnative.AccessibilityEvent].
        """
        _listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                _listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


def dispatch_accessibility(screen_reader: bool, reduce_motion: bool) -> None:
    """Record new settings and notify listeners (tests and native pushes)."""
    global _state
    event = AccessibilityEvent(bool(screen_reader), bool(reduce_motion))
    if event == _state:
        return
    _state = event
    for listener in list(_listeners):
        try:
            listener(event)
        except Exception:
            diagnostics.swallowed("accessibility_info.dispatch_accessibility")


def _on_native_change(payload: Any) -> None:
    if isinstance(payload, dict):
        current = _state
        dispatch_accessibility(
            payload.get("screen_reader", current.screen_reader if current else False),
            payload.get("reduce_motion", current.reduce_motion if current else False),
        )


on_event("AccessibilityInfo", "change", _on_native_change)


def _subscribe(notify: Callable[[], None]) -> Callable[[], None]:
    return AccessibilityInfo.add_listener(lambda _event: notify())


def use_screen_reader_enabled() -> bool:
    """Return whether a screen reader is running and re-render when that changes.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    return use_subscription(_subscribe, lambda: _snapshot().screen_reader)


def use_reduce_motion() -> bool:
    """Return whether Reduce Motion is on and re-render when that changes.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    return use_subscription(_subscribe, lambda: _snapshot().reduce_motion)
