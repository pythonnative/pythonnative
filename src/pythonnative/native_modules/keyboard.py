"""On-screen keyboard state and dismissal.

[`Keyboard`][pythonnative.Keyboard] mirrors React Native's ``Keyboard``
over the native ``Keyboard`` module. ``is_visible`` reads state the OS
already holds and ``dismiss`` resigns the first responder, so both are
synchronous. Native pushes a ``change`` event with ``{"height",
"visible", "duration_ms"}`` on every show, hide, and resize (iOS
``keyboardWillChangeFrame``, Android ``WindowInsetsCompat.Type.ime()``);
the facade forwards the height to
``platform_metrics`` so
[`use_keyboard_height`][pythonnative.use_keyboard_height] and
[`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView] track it on
both platforms. Off device, tests drive the same path through
[`dispatch_keyboard`][pythonnative.native_modules.keyboard.dispatch_keyboard].

Example:
    ```python
    import pythonnative as pn

    pn.Pressable(pn.Text("Done"), on_press=pn.Keyboard.dismiss)
    unsubscribe = pn.Keyboard.add_listener(lambda e: print(e.height, e.visible))
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List

from .. import diagnostics, platform_metrics
from .registry import native_module, on_event


@dataclass(frozen=True)
class KeyboardEvent:
    """One keyboard transition.

    Attributes:
        height: Keyboard height in layout units (``0.0`` when hidden).
        visible: Whether the keyboard is (or is about to be) on screen.
        duration_ms: The platform's show/hide animation duration in
            milliseconds (``0.0`` when it doesn't animate or doesn't say).
    """

    height: float
    visible: bool
    duration_ms: float = 0.0


_listeners: List[Callable[[KeyboardEvent], None]] = []


class Keyboard:
    """Keyboard interface (synchronous).

    Raises:
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def dismiss() -> None:
        """Hide the keyboard by resigning the focused input (a no-op when none is focused)."""
        native_module("Keyboard").call("dismiss")

    @staticmethod
    def is_visible() -> bool:
        """Return ``True`` while the keyboard is on screen."""
        return bool(native_module("Keyboard").call("is_visible"))

    @staticmethod
    def add_listener(callback: Callable[[KeyboardEvent], None]) -> Callable[[], None]:
        """Subscribe to keyboard transitions; returns an unsubscribe function.

        Each callback receives a [`KeyboardEvent`][pythonnative.KeyboardEvent].
        """
        _listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                _listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


def dispatch_keyboard(height: float, visible: bool, duration_ms: float = 0.0) -> None:
    """Publish a keyboard transition to ``platform_metrics`` and every listener."""
    event = KeyboardEvent(max(0.0, float(height)), bool(visible), max(0.0, float(duration_ms)))
    platform_metrics.set_keyboard_height(event.height if event.visible else 0.0)
    for listener in list(_listeners):
        try:
            listener(event)
        except Exception:
            diagnostics.swallowed("keyboard.dispatch_keyboard")


def _on_native_change(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    height = float(payload.get("height") or 0.0)
    visible = bool(payload.get("visible", height > 0))
    dispatch_keyboard(height, visible, float(payload.get("duration_ms") or 0.0))


on_event("Keyboard", "change", _on_native_change)
