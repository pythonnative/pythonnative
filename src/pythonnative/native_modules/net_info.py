"""Network connectivity state.

[`NetInfo`][pythonnative.NetInfo] reports whether the device is online
and over what kind of connection. ``fetch`` returns a snapshot dict;
``add_listener`` (and the [`use_net_info`][pythonnative.use_net_info]
hook) deliver live updates pushed by the native ``NetInfo`` module
(``NWPathMonitor`` on iOS, ``ConnectivityManager.NetworkCallback`` on
Android) as ``change`` events. Off device, tests push snapshots through
[`dispatch_net_info`][pythonnative.native_modules.net_info.dispatch_net_info].

A snapshot looks like::

    {"is_connected": True, "type": "wifi", "is_internet_reachable": True}

``type`` is one of ``"wifi"``, ``"cellular"``, ``"ethernet"``,
``"none"``, or ``"unknown"``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from .. import diagnostics
from ..hooks import use_effect, use_state
from .registry import native_module, on_event

NetInfoState = Dict[str, object]

_listeners: List[Callable[[NetInfoState], None]] = []
_last_state: NetInfoState = {
    "is_connected": True,
    "type": "unknown",
    "is_internet_reachable": True,
}


class NetInfo:
    """Network connectivity interface."""

    @staticmethod
    def fetch() -> NetInfoState:
        """Return a fresh snapshot of connectivity state."""
        global _last_state
        snapshot = native_module("NetInfo").call("fetch")
        if isinstance(snapshot, dict):
            _last_state = _normalize(snapshot)
        return dict(_last_state)

    @staticmethod
    def add_listener(callback: Callable[[NetInfoState], None]) -> Callable[[], None]:
        """Subscribe to connectivity changes; returns an unsubscribe fn."""
        _listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                _listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


def _normalize(snapshot: Dict[str, Any]) -> NetInfoState:
    return {
        "is_connected": bool(snapshot.get("is_connected", False)),
        "type": str(snapshot.get("type", "unknown")),
        "is_internet_reachable": bool(snapshot.get("is_internet_reachable", False)),
    }


def dispatch_net_info(state: NetInfoState) -> None:
    """Push a new connectivity snapshot and notify listeners."""
    global _last_state
    _last_state = dict(state)
    for listener in list(_listeners):
        try:
            listener(dict(state))
        except Exception:
            diagnostics.swallowed("net_info.dispatch_net_info")


def _on_native_change(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    state = _normalize(payload)
    if state == _last_state:
        return
    dispatch_net_info(state)


on_event("NetInfo", "change", _on_native_change)


def use_net_info() -> NetInfoState:
    """Subscribe a component to [`NetInfo`][pythonnative.NetInfo].

    Returns:
        The latest connectivity snapshot dict; the component
        re-renders whenever connectivity changes.
    """
    state, set_state = use_state(NetInfo.fetch)

    def _subscribe() -> Callable[[], None]:
        set_state(NetInfo.fetch())

        def on_change(snapshot: NetInfoState) -> None:
            set_state(snapshot)

        return NetInfo.add_listener(on_change)

    use_effect(_subscribe, [])
    return state
