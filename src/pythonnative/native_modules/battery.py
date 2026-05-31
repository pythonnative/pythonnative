"""Battery level and charging state.

[`Battery`][pythonnative.Battery] reports the current charge fraction
(``0.0``–``1.0``, or ``-1.0`` when unknown) and charging state, and
lets you subscribe to changes that the native host forwards via
[`dispatch_battery`][pythonnative.native_modules.battery.dispatch_battery].
"""

from __future__ import annotations

from typing import Callable, Dict, List

from ..utils import IS_ANDROID, IS_IOS

BatteryState = str  # "unknown" | "unplugged" | "charging" | "full"

_listeners: List[Callable[[Dict[str, object]], None]] = []


class Battery:
    """Battery interface (synchronous getters + change listener)."""

    @staticmethod
    def get_level() -> float:
        """Return the charge fraction in ``[0, 1]`` (``-1.0`` if unknown)."""
        if IS_IOS:
            return _ios_level()
        if IS_ANDROID:
            return _android_level()
        return -1.0

    @staticmethod
    def get_state() -> BatteryState:
        """Return ``"charging"`` / ``"full"`` / ``"unplugged"`` / ``"unknown"``."""
        if IS_IOS:
            return _ios_state()
        if IS_ANDROID:
            return _android_state()
        return "unknown"

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
    """Notify listeners of a battery change (called by the native host)."""
    payload: Dict[str, object] = {"level": level, "state": state}
    for listener in list(_listeners):
        try:
            listener(dict(payload))
        except Exception:
            pass


# ======================================================================
# iOS: UIDevice
# ======================================================================


def _ios_device() -> object:
    from rubicon.objc import ObjCClass

    device = ObjCClass("UIDevice").currentDevice
    try:
        device.setBatteryMonitoringEnabled_(True)
    except Exception:
        pass
    return device


def _ios_level() -> float:
    try:
        level = float(_ios_device().batteryLevel)
        return level if level >= 0 else -1.0
    except Exception:
        return -1.0


def _ios_state() -> BatteryState:
    try:
        # UIDeviceBatteryState: 0 unknown, 1 unplugged, 2 charging, 3 full
        return {0: "unknown", 1: "unplugged", 2: "charging", 3: "full"}.get(int(_ios_device().batteryState), "unknown")
    except Exception:
        return "unknown"


# ======================================================================
# Android: BatteryManager
# ======================================================================


def _android_level() -> float:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        Context = jclass("android.content.Context")
        bm = ctx.getSystemService(Context.BATTERY_SERVICE)
        BatteryManager = jclass("android.os.BatteryManager")
        pct = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        return (pct / 100.0) if pct is not None and pct >= 0 else -1.0
    except Exception:
        return -1.0


def _android_state() -> BatteryState:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        Context = jclass("android.content.Context")
        bm = ctx.getSystemService(Context.BATTERY_SERVICE)
        BatteryManager = jclass("android.os.BatteryManager")
        status = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS)
        return {
            BatteryManager.BATTERY_STATUS_CHARGING: "charging",
            BatteryManager.BATTERY_STATUS_FULL: "full",
            BatteryManager.BATTERY_STATUS_DISCHARGING: "unplugged",
            BatteryManager.BATTERY_STATUS_NOT_CHARGING: "unplugged",
        }.get(status, "unknown")
    except Exception:
        return "unknown"
