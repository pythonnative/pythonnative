"""Network connectivity state.

[`NetInfo`][pythonnative.NetInfo] reports whether the device is online
and over what kind of connection. ``fetch`` returns a snapshot dict;
``add_listener`` (and the [`use_net_info`][pythonnative.use_net_info]
hook) deliver live updates: while at least one listener is subscribed,
a lightweight background watcher polls the platform's connectivity
state and dispatches a fresh snapshot whenever it changes. Native
hosts may also push changes directly through
[`dispatch_net_info`][pythonnative.native_modules.net_info.dispatch_net_info].

A snapshot looks like::

    {"is_connected": True, "type": "wifi", "is_internet_reachable": True}

``type`` is one of ``"wifi"``, ``"cellular"``, ``"ethernet"``,
``"none"``, or ``"unknown"``.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional

from .. import diagnostics
from ..hooks import use_effect, use_state
from ..utils import IS_ANDROID, IS_IOS

NetInfoState = Dict[str, object]

_listeners: List[Callable[[NetInfoState], None]] = []
_last_state: NetInfoState = {
    "is_connected": True,
    "type": "unknown",
    "is_internet_reachable": True,
}

# Background watcher driving live updates while listeners exist.
_WATCH_INTERVAL_S = 2.0
_watcher_lock = threading.Lock()
_watcher_stop: Optional[threading.Event] = None


class NetInfo:
    """Network connectivity interface."""

    @staticmethod
    def fetch() -> NetInfoState:
        """Return a fresh snapshot of connectivity state."""
        global _last_state
        if IS_ANDROID:
            _last_state = _android_state()
        elif IS_IOS:
            _last_state = _ios_state()
        return dict(_last_state)

    @staticmethod
    def add_listener(callback: Callable[[NetInfoState], None]) -> Callable[[], None]:
        """Subscribe to connectivity changes; returns an unsubscribe fn.

        The first subscription starts a background watcher that polls
        the platform connectivity state every couple of seconds and
        dispatches a snapshot on change; the watcher stops when the
        last listener unsubscribes.
        """
        _listeners.append(callback)
        _ensure_watcher()

        def _unsubscribe() -> None:
            try:
                _listeners.remove(callback)
            except ValueError:
                pass
            if not _listeners:
                _stop_watcher()

        return _unsubscribe


def _ensure_watcher() -> None:
    """Start the connectivity watcher if a platform backend exists."""
    global _watcher_stop
    if not (IS_ANDROID or IS_IOS):
        return
    with _watcher_lock:
        if _watcher_stop is not None:
            return
        stop = threading.Event()
        _watcher_stop = stop

    def _watch() -> None:
        previous = dict(_last_state)
        while not stop.wait(_WATCH_INTERVAL_S):
            try:
                current = _android_state() if IS_ANDROID else _ios_state()
            except Exception:
                continue
            if current != previous:
                previous = dict(current)
                dispatch_net_info(current)

    threading.Thread(target=_watch, daemon=True, name="pn-netinfo").start()


def _stop_watcher() -> None:
    global _watcher_stop
    with _watcher_lock:
        if _watcher_stop is not None:
            _watcher_stop.set()
            _watcher_stop = None


def dispatch_net_info(state: NetInfoState) -> None:
    """Push a new connectivity snapshot and notify listeners."""
    global _last_state
    _last_state = dict(state)
    for listener in list(_listeners):
        try:
            listener(dict(state))
        except Exception:
            diagnostics.swallowed("net_info.dispatch_net_info")


def dispatch_android_change() -> None:
    """Re-read Android connectivity and notify listeners on change.

    Called by the template's ``MainActivity`` from the
    ``ConnectivityManager.NetworkCallback`` it registers via
    ``registerDefaultNetworkCallback`` whenever the default network
    appears, drops, or changes capabilities. The callback lives in
    Kotlin because Chaquopy's ``dynamic_proxy`` implements interfaces
    only and ``NetworkCallback`` is a class. Re-reading the snapshot
    here keeps the transport-type mapping in one place, and identical
    consecutive snapshots are dropped so paired ``onAvailable`` /
    ``onCapabilitiesChanged`` callbacks don't double-notify.
    """
    state = _android_state()
    if state == _last_state:
        return
    dispatch_net_info(state)


def use_net_info() -> NetInfoState:
    """Subscribe a component to [`NetInfo`][pythonnative.NetInfo].

    Returns:
        The latest connectivity snapshot dict; the component
        re-renders whenever connectivity changes.
    """
    state, set_state = use_state(NetInfo.fetch)

    def _subscribe() -> Callable[[], None]:
        set_state(NetInfo.fetch())
        return NetInfo.add_listener(set_state)

    use_effect(_subscribe, [])
    return state


# ======================================================================
# iOS: SCNetworkReachability
# ======================================================================


def _ios_state() -> NetInfoState:
    try:
        from ctypes import CDLL, byref, c_uint32, c_void_p, util

        sc = CDLL(util.find_library("SystemConfiguration"))
        sc.SCNetworkReachabilityCreateWithName.restype = c_void_p
        ref = sc.SCNetworkReachabilityCreateWithName(None, b"8.8.8.8")
        if not ref:
            return dict(_last_state)
        flags = c_uint32(0)
        ok = sc.SCNetworkReachabilityGetFlags(c_void_p(ref), byref(flags))
        if not ok:
            return {"is_connected": False, "type": "none", "is_internet_reachable": False}
        reachable = bool(flags.value & 0x2)  # kSCNetworkReachabilityFlagsReachable
        is_wwan = bool(flags.value & (1 << 18))  # kSCNetworkReachabilityFlagsIsWWAN
        return {
            "is_connected": reachable,
            "type": ("cellular" if is_wwan else "wifi") if reachable else "none",
            "is_internet_reachable": reachable,
        }
    except Exception:
        return dict(_last_state)


# ======================================================================
# Android: ConnectivityManager
# ======================================================================


def _android_state() -> NetInfoState:
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        Context = jclass("android.content.Context")
        manager = ctx.getSystemService(Context.CONNECTIVITY_SERVICE)
        network = manager.getActiveNetwork()
        if network is None:
            return {"is_connected": False, "type": "none", "is_internet_reachable": False}
        caps = manager.getNetworkCapabilities(network)
        if caps is None:
            return {"is_connected": False, "type": "none", "is_internet_reachable": False}
        NetworkCapabilities = jclass("android.net.NetworkCapabilities")
        if caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI):
            kind = "wifi"
        elif caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR):
            kind = "cellular"
        elif caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET):
            kind = "ethernet"
        else:
            kind = "unknown"
        reachable = bool(caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))
        return {"is_connected": True, "type": kind, "is_internet_reachable": reachable}
    except Exception:
        return dict(_last_state)
