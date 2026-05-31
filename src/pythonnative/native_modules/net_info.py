"""Network connectivity state.

[`NetInfo`][pythonnative.NetInfo] reports whether the device is online
and over what kind of connection. ``fetch`` returns a snapshot dict;
``add_listener`` (and the [`use_net_info`][pythonnative.use_net_info]
hook) deliver live updates as the native host forwards connectivity
changes through
[`dispatch_net_info`][pythonnative.native_modules.net_info.dispatch_net_info].

A snapshot looks like::

    {"is_connected": True, "type": "wifi", "is_internet_reachable": True}

``type`` is one of ``"wifi"``, ``"cellular"``, ``"ethernet"``,
``"none"``, or ``"unknown"``.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from ..hooks import use_effect, use_state
from ..utils import IS_ANDROID, IS_IOS

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
        if IS_ANDROID:
            _last_state = _android_state()
        elif IS_IOS:
            _last_state = _ios_state()
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


def dispatch_net_info(state: NetInfoState) -> None:
    """Push a new connectivity snapshot and notify listeners."""
    global _last_state
    _last_state = dict(state)
    for listener in list(_listeners):
        try:
            listener(dict(state))
        except Exception:
            pass


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
