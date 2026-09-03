"""Battery level and charging state.

[`Battery`][pythonnative.Battery] reports the current charge fraction
(``0.0``–``1.0``, or ``-1.0`` when unknown) and charging state, and
lets you subscribe to changes. The native ``Battery`` module pushes a
``change`` event with ``{"level", "state"}``; off device, tests drive
the same path through
[`dispatch_battery`][pythonnative.native_modules.battery.dispatch_battery].
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from .. import diagnostics
from .registry import native_module, on_event

BatteryState = str  # "unknown" | "unplugged" | "charging" | "full"

_listeners: List[Callable[[Dict[str, object]], None]] = []


class Battery:
    """Battery interface (synchronous getters + change listener)."""

    @staticmethod
    def get_level() -> float:
        """Return the charge fraction in ``[0, 1]`` (``-1.0`` if unknown)."""
        try:
            level = float(native_module("Battery").call("get_level"))
        except Exception:
            return -1.0
        return level if 0.0 <= level <= 1.0 else -1.0

    @staticmethod
    def get_state() -> BatteryState:
        """Return ``"charging"`` / ``"full"`` / ``"unplugged"`` / ``"unknown"``."""
        try:
            state = str(native_module("Battery").call("get_state") or "unknown")
        except Exception:
            return "unknown"
        return state if state in ("unknown", "unplugged", "charging", "full") else "unknown"

    @staticmethod
    def add_listener(callback: Callable[[Dict[str, object]], None]) -> Callable[[], None]:
        """Subscribe to battery changes; returns an unsubscribe fn.

        Each callback receives ``{"level": float, "state": str}``.
        """
        _listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                _listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


def dispatch_battery(level: float, state: BatteryState) -> None:
    """Notify listeners of a battery change."""
    payload: Dict[str, object] = {"level": level, "state": state}
    for listener in list(_listeners):
        try:
            listener(dict(payload))
        except Exception:
            diagnostics.swallowed("battery.dispatch_battery")


def _on_native_change(payload: Any) -> None:
    if isinstance(payload, dict):
        dispatch_battery(float(payload.get("level", -1.0)), str(payload.get("state", "unknown")))


on_event("Battery", "change", _on_native_change)
