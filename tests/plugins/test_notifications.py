"""``pythonnative.notifications``: the off-device fallback, the facade, and the plugin manifest."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

import pythonnative.notifications as notifications
from pythonnative.native_modules.registry import NativeModuleError, emit, register_python_module
from pythonnative.notifications import NotificationResponse, Notifications, ReceivedNotification
from pythonnative.project.plugins import load_plugin
from pythonnative.sdk import schema

NATIVE = Path(notifications.__file__).parent / "native"


class _Recording:
    """Answers like a device, recording what the facade sends."""

    def __init__(self) -> None:
        self.scheduled: List[Dict[str, Any]] = []
        self.listening: List[tuple[str, bool]] = []
        self.launch: Optional[Dict[str, Any]] = None
        self.fail_listening = False

    def schedule(self, **kwargs: Any) -> bool:
        self.scheduled.append(kwargs)
        return True

    def last_response(self) -> Optional[Dict[str, Any]]:
        return self.launch

    def set_listening(self, event: str, listening: bool) -> None:
        if self.fail_listening:
            raise NativeModuleError("Notifications", "set_listening", "no plugin", "plugin_not_enabled")
        self.listening.append((event, listening))


@pytest.fixture(autouse=True)
def _fresh_fallback() -> Any:
    register_python_module("Notifications", notifications._Fallback)
    yield
    register_python_module("Notifications", notifications._Fallback)


@pytest.fixture
def device() -> _Recording:
    recording = _Recording()
    register_python_module("Notifications", recording)
    return recording


def test_fallback_reports_nothing_was_shown() -> None:
    async def run() -> None:
        assert await Notifications.request_permission() is False
        assert await Notifications.schedule("Title", "Body", delay_seconds=5, data={"a": 1}) is False
        await Notifications.cancel("x")
        await Notifications.cancel_all()
        await Notifications.set_badge(2)

    asyncio.run(run())
    assert Notifications.last_response() is None


def test_schedule_sends_every_option(device: _Recording) -> None:
    result = asyncio.run(
        Notifications.schedule(
            "Hi", "There", delay_seconds=3, identifier="id", data={"k": [1, None]}, badge=4, sound=False
        )
    )
    assert result is True
    assert device.scheduled == [
        {
            "title": "Hi",
            "body": "There",
            "delay_seconds": 3.0,
            "identifier": "id",
            "data": {"k": [1, None]},
            "badge": 4,
            "sound": False,
        }
    ]


def test_schedule_defaults(device: _Recording) -> None:
    asyncio.run(Notifications.schedule("Hi"))
    sent = device.scheduled[0]
    assert (sent["body"], sent["delay_seconds"], sent["identifier"]) == ("", 0.0, "default")
    assert (sent["data"], sent["badge"], sent["sound"]) == (None, None, True)


@pytest.mark.parametrize("delay", [-1, float("inf"), float("nan")])
def test_schedule_rejects_a_bad_delay(delay: float) -> None:
    with pytest.raises(ValueError, match="delay_seconds"):
        asyncio.run(Notifications.schedule("Hi", delay_seconds=delay))


def test_negative_badges_are_rejected() -> None:
    with pytest.raises(ValueError, match="badge"):
        asyncio.run(Notifications.schedule("Hi", badge=-1))
    with pytest.raises(ValueError, match="count"):
        asyncio.run(Notifications.set_badge(-1))


def test_on_received_decodes_and_unsubscribes(device: _Recording) -> None:
    seen: List[ReceivedNotification] = []
    unsubscribe = Notifications.on_received(seen.append)
    emit("Notifications", "received", {"identifier": "a", "title": "T", "body": "B", "data": {"k": 1}})
    assert seen == [ReceivedNotification("a", "T", "B", {"k": 1})]
    unsubscribe()
    unsubscribe()
    emit("Notifications", "received", {"identifier": "b"})
    assert len(seen) == 1
    assert device.listening == [("received", True), ("received", False)]


def test_on_response_decodes_with_defaults(device: _Recording) -> None:
    seen: List[NotificationResponse] = []
    unsubscribe = Notifications.on_response(seen.append)
    emit("Notifications", "response", {"identifier": "a", "data": {"k": 1}, "action": "default"})
    emit("Notifications", "response", {"identifier": "b"})
    unsubscribe()
    assert seen == [
        NotificationResponse("a", "", "", {"k": 1}, "default"),
        NotificationResponse("b", "", "", {}, "default"),
    ]


def test_native_listens_while_anyone_subscribes(device: _Recording) -> None:
    first = Notifications.on_response(lambda _: None)
    second = Notifications.on_response(lambda _: None)
    assert device.listening == [("response", True)]
    first()
    assert device.listening == [("response", True)]
    second()
    assert device.listening == [("response", True), ("response", False)]


def test_each_event_listens_separately(device: _Recording) -> None:
    received = Notifications.on_received(lambda _: None)
    response = Notifications.on_response(lambda _: None)
    received()
    response()
    assert device.listening == [
        ("received", True),
        ("response", True),
        ("received", False),
        ("response", False),
    ]


def test_events_replayed_during_subscribe_reach_the_callback() -> None:
    """Native drains its buffer from inside ``set_listening``, so the hook must already be on."""
    seen: List[NotificationResponse] = []

    class Replaying(_Recording):
        def set_listening(self, event: str, listening: bool) -> None:
            if listening:
                emit("Notifications", event, {"identifier": "early"})

    register_python_module("Notifications", Replaying())
    unsubscribe = Notifications.on_response(seen.append)
    unsubscribe()
    assert [response.identifier for response in seen] == ["early"]


def test_a_failed_subscribe_leaves_nothing_behind(device: _Recording) -> None:
    device.fail_listening = True
    seen: List[NotificationResponse] = []
    with pytest.raises(NativeModuleError) as error:
        Notifications.on_response(seen.append)
    assert error.value.code == "plugin_not_enabled"
    device.fail_listening = False
    emit("Notifications", "response", {"identifier": "a"})
    assert seen == []
    Notifications.on_response(seen.append)()
    assert device.listening == [("response", True), ("response", False)]


def test_last_response_decodes_the_launching_tap(device: _Recording) -> None:
    device.launch = {"identifier": "a", "title": "T", "body": "B", "data": {"k": 1}, "action": "default"}
    assert Notifications.last_response() == NotificationResponse("a", "T", "B", {"k": 1}, "default")


def test_contract_matches_the_platform_limits() -> None:
    contract = schema.MODULES["Notifications"]
    assert contract.methods["set_badge"]["platforms"] == ["ios"]
    assert contract.methods["schedule"]["async"] is True
    assert contract.methods["last_response"]["async"] is False
    assert set(contract.events) == {"received", "response"}


def test_manifest_loads_and_declares_what_the_platforms_need() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "notifications"
    assert plugin.ios_entry == "NotificationsPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.notifications.NotificationsPlugin"
    assert plugin.requires_permissions == ("notifications",)
    assert plugin.requires_plugins == ()
    fragment = (NATIVE / plugin.manifest["android"]["manifest"]["application"]).read_text()
    assert "plugins.notifications.NotificationReceiver" in fragment
    assert 'android:exported="false"' in fragment
    # POST_NOTIFICATIONS comes from the [permissions] table, so the manifest doesn't repeat it.
    assert "permissions" not in plugin.manifest["android"]
    assert plugin.manifest["options"]["android_icon"]["type"] == "path"


def test_schema_file_is_current() -> None:
    written = json.loads((NATIVE / "schema.json").read_text())
    assert set(written["modules"]) == {"Notifications"}
    assert set(written["modules"]["Notifications"]["methods"]) == set(schema.MODULES["Notifications"].methods)
