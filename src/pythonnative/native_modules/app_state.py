"""Foreground / background app lifecycle state.

[`AppState`][pythonnative.AppState] exposes the current lifecycle phase
(``"active"``, ``"inactive"``, or ``"background"``) and lets you
subscribe to transitions. The native host (the iOS app delegate /
Android ``Activity``) forwards lifecycle callbacks by calling
[`dispatch_app_state`][pythonnative.native_modules.app_state.dispatch_app_state],
so the same listener machinery works on every platform and in tests.

Prefer the [`use_app_state`][pythonnative.use_app_state] hook inside
components; use the imperative API for non-UI code.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Banner():
        state = pn.use_app_state()
        return pn.Text(f"App is {state}")
    ```
"""

from __future__ import annotations

from typing import Callable, List

from .. import diagnostics
from ..hooks import use_effect, use_state

AppStateStatus = str  # "active" | "inactive" | "background"

_VALID = ("active", "inactive", "background")
_current: AppStateStatus = "active"
_listeners: List[Callable[[AppStateStatus], None]] = []


class AppState:
    """App lifecycle state interface."""

    @staticmethod
    def current_state() -> AppStateStatus:
        """Return the current lifecycle phase."""
        return _current

    @staticmethod
    def add_listener(callback: Callable[[AppStateStatus], None]) -> Callable[[], None]:
        """Subscribe to lifecycle changes.

        Returns:
            A zero-arg function that unsubscribes when called.
        """
        _listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                _listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


def dispatch_app_state(state: AppStateStatus) -> None:
    """Update the current state and notify every listener.

    Called by the native host on lifecycle transitions. Unknown values
    are ignored so a misbehaving host can't push garbage into the tree.
    """
    global _current
    if state not in _VALID or state == _current:
        return
    _current = state
    for listener in list(_listeners):
        try:
            listener(state)
        except Exception:
            diagnostics.swallowed("app_state.dispatch_app_state")


def use_app_state() -> AppStateStatus:
    """Subscribe a component to [`AppState`][pythonnative.AppState].

    Returns:
        The current lifecycle phase; the component re-renders whenever
        it changes.
    """
    state, set_state = use_state(_current)

    def _subscribe() -> Callable[[], None]:
        set_state(_current)
        return AppState.add_listener(set_state)

    use_effect(_subscribe, [])
    return state
