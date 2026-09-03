"""Unit tests for the device-API native modules.

Off-device (neither Android nor iOS) every module falls back to a safe
default path: in-memory buffers, ``"unknown"`` states, and no-op
feedback. These tests exercise those desktop fallbacks plus the
listener/dispatch machinery and the ``use_app_state`` / ``use_net_info``
hooks, none of which need a real device.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Generator, List

import pytest

from pythonnative import (
    AppState,
    Battery,
    Biometrics,
    Clipboard,
    Haptics,
    Linking,
    NetInfo,
    Permissions,
    SecureStore,
    Share,
    Vibration,
    use_app_state,
    use_net_info,
)
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.native_modules import app_state, battery, linking, net_info
from pythonnative.native_modules import registry as module_registry
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend as MockBackend


@pytest.fixture(autouse=True)
def _reset_module_state() -> Generator[None, None, None]:
    """Reset process-global module state so tests don't leak into each other."""
    app_state._current = "active"
    app_state._listeners.clear()
    net_info._listeners.clear()
    net_info._last_state = {"is_connected": True, "type": "unknown", "is_internet_reachable": True}
    battery._listeners.clear()
    module_registry.native_module("SecureStore").impl.clear()  # type: ignore[attr-defined]
    linking.set_initial_url(None)
    Clipboard.set_string("")
    yield
    app_state._listeners.clear()
    net_info._listeners.clear()
    battery._listeners.clear()


# ======================================================================
# Clipboard
# ======================================================================


def test_clipboard_roundtrip_desktop() -> None:
    Clipboard.set_string("hello world")
    assert Clipboard.get_string() == "hello world"
    assert Clipboard.has_string() is True


def test_clipboard_empty_has_string_false() -> None:
    Clipboard.set_string("")
    assert Clipboard.has_string() is False


# ======================================================================
# AppState + use_app_state
# ======================================================================


def test_app_state_default_active() -> None:
    assert AppState.current_state() == "active"


def test_app_state_listener_notified_on_dispatch() -> None:
    seen: List[str] = []
    unsubscribe = AppState.add_listener(seen.append)
    app_state.dispatch_app_state("background")
    assert seen == ["background"]
    assert AppState.current_state() == "background"
    unsubscribe()
    app_state.dispatch_app_state("active")
    assert seen == ["background"]  # unsubscribed, no new event


def test_app_state_ignores_invalid_and_duplicate() -> None:
    seen: List[str] = []
    AppState.add_listener(seen.append)
    app_state.dispatch_app_state("active")  # same as current -> ignored
    app_state.dispatch_app_state("bogus")  # invalid -> ignored
    assert seen == []


def test_use_app_state_returns_current_and_rerenders() -> None:
    rendered: List[str] = []

    @component
    def comp() -> Element:
        rendered.append(use_app_state())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: rec.reconcile(comp())
    rec.mount(comp())
    before = len(rendered)
    assert rendered[0] == "active"

    app_state.dispatch_app_state("background")
    assert len(rendered) > before
    assert rendered[-1] == "background"


# ======================================================================
# NetInfo + use_net_info
# ======================================================================


def test_net_info_fetch_desktop_default() -> None:
    state = NetInfo.fetch()
    assert state["is_connected"] is True
    assert state["type"] == "unknown"


def test_net_info_listener_notified() -> None:
    seen: List[Dict[str, object]] = []
    NetInfo.add_listener(seen.append)
    net_info.dispatch_net_info({"is_connected": False, "type": "none", "is_internet_reachable": False})
    assert seen[0]["is_connected"] is False
    assert NetInfo.fetch()["type"] == "none"


def test_use_net_info_rerenders_on_change() -> None:
    rendered: List[Dict[str, object]] = []

    @component
    def comp() -> Element:
        rendered.append(use_net_info())
        return Element("Text", {"text": "ok"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: rec.reconcile(comp())
    rec.mount(comp())
    before = len(rendered)

    net_info.dispatch_net_info({"is_connected": False, "type": "cellular", "is_internet_reachable": True})
    assert len(rendered) > before
    assert rendered[-1]["type"] == "cellular"


# ======================================================================
# Battery
# ======================================================================


def test_battery_desktop_defaults() -> None:
    assert Battery.get_level() == -1.0
    assert Battery.get_state() == "unknown"


def test_battery_listener_dispatch() -> None:
    seen: List[Dict[str, object]] = []
    Battery.add_listener(seen.append)
    battery.dispatch_battery(0.5, "charging")
    assert seen[0] == {"level": 0.5, "state": "charging"}


# ======================================================================
# SecureStore
# ======================================================================


def test_secure_store_roundtrip_desktop() -> None:
    assert SecureStore.set_item("token", "abc123") is True
    assert SecureStore.get_item("token") == "abc123"
    assert SecureStore.delete_item("token") is True
    assert SecureStore.get_item("token") is None
    assert SecureStore.delete_item("token") is False


# ======================================================================
# Permissions
# ======================================================================


def test_permissions_check_undetermined_desktop() -> None:
    assert Permissions.check("camera") == "undetermined"


def test_permissions_request_undetermined_desktop() -> None:
    assert asyncio.run(Permissions.request("camera")) == "undetermined"


# ======================================================================
# Linking
# ======================================================================


def test_linking_desktop_false() -> None:
    assert Linking.can_open_url("https://example.com") is False
    assert Linking.open_url("https://example.com") is False
    assert Linking.open_settings() is False


def test_linking_initial_url() -> None:
    assert Linking.get_initial_url() is None
    linking.set_initial_url("myapp://launch")
    assert Linking.get_initial_url() == "myapp://launch"


def test_linking_dispatch_url_notifies_listeners() -> None:
    linking.set_initial_url(None)
    received: list = []
    unsubscribe = Linking.add_listener(received.append)
    try:
        linking.dispatch_url("myapp://one")
        linking.dispatch_url("myapp://two")
    finally:
        unsubscribe()
    linking.dispatch_url("myapp://after-unsubscribe")
    assert received == ["myapp://one", "myapp://two"]
    # The first dispatched URL doubles as the cold-start initial URL.
    assert Linking.get_initial_url() == "myapp://one"
    linking.set_initial_url(None)


def test_linking_listener_errors_do_not_break_dispatch() -> None:
    linking.set_initial_url(None)
    received: list = []

    def _bad(_url: str) -> None:
        raise RuntimeError("boom")

    unsub_bad = Linking.add_listener(_bad)
    unsub_ok = Linking.add_listener(received.append)
    try:
        linking.dispatch_url("myapp://x")
    finally:
        unsub_bad()
        unsub_ok()
    assert received == ["myapp://x"]
    linking.set_initial_url(None)


# ======================================================================
# Notifications: remote push registration
# ======================================================================


def test_get_device_token_none_on_desktop() -> None:
    from pythonnative.native_modules.notifications import Notifications

    assert asyncio.run(Notifications.get_device_token()) is None


def test_get_device_token_surfaces_native_error() -> None:
    from pythonnative.native_modules.notifications import Notifications

    class FailingNotifications:
        def get_device_token(self) -> str:
            raise module_registry.NativeModuleError("Notifications", "get_device_token", "no entitlement")

    module_registry.register_python_module("Notifications", FailingNotifications())
    try:
        with pytest.raises(RuntimeError, match="no entitlement"):
            asyncio.run(Notifications.get_device_token())
    finally:
        module_registry.unregister_python_module("Notifications")


# ======================================================================
# Module events pushed from native
# ======================================================================


def test_native_module_events_reach_facade_listeners() -> None:
    seen_states: List[str] = []
    seen_urls: List[str] = []
    seen_battery: List[Dict[str, object]] = []
    seen_net: List[Dict[str, object]] = []
    AppState.add_listener(seen_states.append)
    Linking.add_listener(seen_urls.append)
    Battery.add_listener(seen_battery.append)
    NetInfo.add_listener(seen_net.append)

    module_registry.dispatch_module_message("AppState", {"event": "change", "payload": "background"})
    module_registry.dispatch_module_message("Linking", {"event": "url", "payload": "myapp://deep"})
    module_registry.dispatch_module_message("Battery", {"event": "change", "payload": {"level": 0.25, "state": "full"}})
    module_registry.dispatch_module_message(
        "NetInfo", {"event": "change", "payload": {"is_connected": False, "type": "none"}}
    )

    assert seen_states == ["background"]
    assert AppState.current_state() == "background"
    assert seen_urls == ["myapp://deep"]
    assert Linking.get_initial_url() == "myapp://deep"
    assert seen_battery == [{"level": 0.25, "state": "full"}]
    assert seen_net == [{"is_connected": False, "type": "none", "is_internet_reachable": False}]
    assert net_info._last_state["type"] == "none"


# ======================================================================
# Share / Biometrics / Haptics (desktop no-ops)
# ======================================================================


def test_share_returns_false_desktop() -> None:
    assert asyncio.run(Share.share(message="hi", url="https://example.com")) is False


def test_biometrics_unavailable_desktop() -> None:
    assert Biometrics.is_available() is False


def test_biometrics_authenticate_false_desktop() -> None:
    assert asyncio.run(Biometrics.authenticate("Unlock")) is False


def test_haptics_and_vibration_are_noops_desktop() -> None:
    # Should not raise on desktop.
    Haptics.impact("light")
    Haptics.notification("success")
    Haptics.selection()
    Vibration.vibrate(100)
    Vibration.cancel()
