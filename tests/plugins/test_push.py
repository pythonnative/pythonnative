"""``pythonnative.push``: the off-device fallback, the facade, and the plugin manifest."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, List

import pytest

import pythonnative.push as push
from pythonnative.native_modules.registry import emit, register_python_module
from pythonnative.project.config import AppConfig
from pythonnative.project.plugin_config import check_requirements, resolve_plugin
from pythonnative.project.plugins import PluginError, load_plugin
from pythonnative.push import Push, PushMessage
from pythonnative.sdk import schema

NATIVE = Path(push.__file__).parent / "native"
NOTIFICATIONS_NATIVE = NATIVE.parent.parent / "notifications" / "native"


class _Recording:
    def __init__(self) -> None:
        self.listening: List[tuple[str, bool]] = []

    def get_device_token(self) -> str:
        return "abc123"

    def set_listening(self, event: str, listening: bool) -> None:
        self.listening.append((event, listening))


@pytest.fixture(autouse=True)
def _fresh_fallback() -> Any:
    register_python_module("Push", push._Fallback)
    yield
    register_python_module("Push", push._Fallback)


def _config(tmp_path: Path, **plugin_options: Any) -> AppConfig:
    config = AppConfig(app_id="com.example.app", name="app", display_name="App", project_root=tmp_path)
    config.plugin_use = ["notifications", "push"]
    config.permissions = {"notifications": True, "remote_notifications": True}
    config.plugin_options = {"push": plugin_options} if plugin_options else {}
    return config


def test_fallback_has_no_token() -> None:
    assert asyncio.run(Push.get_device_token()) is None


def test_get_device_token_returns_the_token() -> None:
    register_python_module("Push", _Recording())
    assert asyncio.run(Push.get_device_token()) == "abc123"


def test_on_token_delivers_strings_and_unsubscribes() -> None:
    device = _Recording()
    register_python_module("Push", device)
    seen: List[str] = []
    unsubscribe = Push.on_token(seen.append)
    emit("Push", "token", "first")
    unsubscribe()
    emit("Push", "token", "second")
    assert seen == ["first"]
    assert device.listening == [("token", True), ("token", False)]


def test_on_message_decodes() -> None:
    device = _Recording()
    register_python_module("Push", device)
    seen: List[PushMessage] = []
    unsubscribe = Push.on_message(seen.append)
    emit("Push", "message", {"title": "T", "body": "B", "data": {"k": "v"}})
    emit("Push", "message", {"data": {"silent": "yes"}})
    unsubscribe()
    assert seen == [PushMessage("T", "B", {"k": "v"}), PushMessage(None, None, {"silent": "yes"})]
    assert device.listening == [("message", True), ("message", False)]


def test_contract() -> None:
    contract = schema.MODULES["Push"]
    assert contract.methods["get_device_token"]["async"] is True
    assert set(contract.events) == {"token", "message"}


def test_manifest_loads() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "push"
    assert plugin.ios_entry == "PushPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.push.PushPlugin"
    assert plugin.requires_plugins == ("notifications",)
    assert plugin.requires_permissions == ("remote_notifications",)
    assert any(item.startswith("com.google.firebase:firebase-messaging:") for item in plugin.maven_dependencies)
    fragment = (NATIVE / plugin.manifest["android"]["manifest"]["application"]).read_text()
    assert "com.google.firebase.MESSAGING_EVENT" in fragment


def test_build_requires_the_notifications_plugin(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(PluginError, match="notifications"):
        check_requirements([load_plugin(NATIVE)], config)
    check_requirements([load_plugin(NATIVE), load_plugin(NOTIFICATIONS_NATIVE)], config)


def test_build_without_a_google_file_leaves_gradle_alone(tmp_path: Path) -> None:
    resolved = resolve_plugin(load_plugin(NATIVE), _config(tmp_path), environ={})
    assert "gradle_plugins" not in resolved.android
    assert "files" not in resolved.android
    assert resolved.android["dependencies"]


def test_google_file_adds_the_gradle_plugin_and_copies_itself(tmp_path: Path) -> None:
    source = tmp_path / "google-services.json"
    source.write_text("{}")
    config = _config(tmp_path, google_services_file="google-services.json")
    resolved = resolve_plugin(load_plugin(NATIVE), config, environ={})
    assert [entry["id"] for entry in resolved.android["gradle_plugins"]] == ["com.google.gms.google-services"]
    assert resolved.android["files"] == [{"from": str(source), "to": "app/google-services.json"}]


def test_schema_file_is_current() -> None:
    written = json.loads((NATIVE / "schema.json").read_text())
    assert set(written["modules"]) == {"Push"}
    assert set(written["modules"]["Push"]["methods"]) == set(schema.MODULES["Push"].methods)
