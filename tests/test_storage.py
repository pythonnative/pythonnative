"""Unit tests for pn.AsyncStorage and pn.use_persisted_state."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Generator

import pytest

from pythonnative.element import Element
from pythonnative.hooks import component
from pythonnative.reconciler import Reconciler
from pythonnative.storage import AsyncStorage, _desktop_store, use_persisted_state


@pytest.fixture(autouse=True)
def _reset_desktop_store(tmp_path: Path) -> Generator[None, None, None]:
    """Isolate the desktop backend per test by pointing it at a temp dir."""
    _desktop_store.clear()
    # Reload flag is module-private; force reload-on-read.
    import pythonnative.storage as storage_mod

    storage_mod._desktop_loaded = False
    os.environ["PN_STORAGE_DIR"] = str(tmp_path)
    yield
    _desktop_store.clear()
    storage_mod._desktop_loaded = False
    os.environ.pop("PN_STORAGE_DIR", None)


def test_set_and_get_round_trip() -> None:
    async def run() -> str | None:
        await AsyncStorage.set("name", "Alice")
        return await AsyncStorage.get("name")

    assert asyncio.run(run()) == "Alice"


def test_get_missing_key_returns_none() -> None:
    async def run() -> str | None:
        return await AsyncStorage.get("never-set")

    assert asyncio.run(run()) is None


def test_set_rejects_non_string_values() -> None:
    async def run() -> None:
        with pytest.raises(TypeError):
            await AsyncStorage.set("k", 42)  # type: ignore[arg-type]

    asyncio.run(run())


def test_set_json_and_get_json_round_trip_complex_value() -> None:
    payload = {"name": "Alice", "tags": [1, 2, 3], "active": True}

    async def run() -> object:
        await AsyncStorage.set_json("user", payload)
        return await AsyncStorage.get_json("user")

    assert asyncio.run(run()) == payload


def test_get_json_returns_none_for_invalid_json() -> None:
    async def run() -> object:
        # Bypass set_json to write a non-JSON value.
        await AsyncStorage.set("user", "not json {")
        return await AsyncStorage.get_json("user")

    assert asyncio.run(run()) is None


def test_delete_removes_value() -> None:
    async def run() -> str | None:
        await AsyncStorage.set("temp", "v")
        await AsyncStorage.delete("temp")
        return await AsyncStorage.get("temp")

    assert asyncio.run(run()) is None


def test_all_keys_returns_persisted_keys() -> None:
    async def run() -> set:
        await AsyncStorage.set("a", "1")
        await AsyncStorage.set("b", "2")
        keys = await AsyncStorage.all_keys()
        return set(keys)

    assert asyncio.run(run()) == {"a", "b"}


def test_clear_removes_everything() -> None:
    async def run() -> list:
        await AsyncStorage.set("a", "1")
        await AsyncStorage.set("b", "2")
        await AsyncStorage.clear()
        return await AsyncStorage.all_keys()

    assert asyncio.run(run()) == []


def test_desktop_backend_persists_to_disk(tmp_path: Path) -> None:
    async def write() -> None:
        await AsyncStorage.set("name", "Alice")

    asyncio.run(write())
    # File should now exist with the value serialised.
    on_disk = json.loads((tmp_path / "pn_async_storage.json").read_text())
    assert on_disk == {"name": "Alice"}


# ======================================================================
# use_persisted_state
# ======================================================================


class _Stub:
    def __init__(self, type_name: str, props: dict) -> None:
        self.type_name = type_name
        self.props = props
        self.children: list = []


class _StubBackend:
    def create_view(self, type_name: str, props: dict) -> _Stub:
        return _Stub(type_name, props)

    def update_view(self, view: _Stub, type_name: str, changed: dict) -> None:
        view.props.update(changed)

    def add_child(self, parent: _Stub, child: _Stub, parent_type: str) -> None:
        parent.children.append(child)

    def remove_child(self, parent: _Stub, child: _Stub, parent_type: str) -> None:
        parent.children = [c for c in parent.children if c is not child]

    def insert_child(self, parent: _Stub, child: _Stub, parent_type: str, index: int) -> None:
        parent.children.insert(index, child)


def test_use_persisted_state_starts_with_initial() -> None:
    captured: list = []

    @component
    def screen() -> Element:
        value, _set = use_persisted_state("theme", "light")
        captured.append(value)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())
    assert captured[0] == "light"


def test_use_persisted_state_loads_existing_value() -> None:
    async def seed() -> None:
        await AsyncStorage.set_json("theme", "dark")

    asyncio.run(seed())

    captured: list = []

    @component
    def screen() -> Element:
        value, _set = use_persisted_state("theme", "light")
        captured.append(value)
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())

    # The first render returns the initial; the async load triggers a
    # state update on a separate task. Allow the runtime loop to
    # deliver the update, then re-render.
    deadline = asyncio.get_event_loop_policy().new_event_loop().time() + 1.5
    import time as _time

    while _time.monotonic() < deadline and (not captured or captured[-1] != "dark"):
        _time.sleep(0.02)
        rec.reconcile(screen())

    assert captured[-1] == "dark"


def test_use_persisted_state_setter_persists_writes() -> None:
    setters: list = []

    @component
    def screen() -> Element:
        value, set_value = use_persisted_state("theme", "light")
        setters.append((value, set_value))
        return Element("View", {}, [])

    rec = Reconciler(_StubBackend())
    rec.mount(screen())

    # Wait for the load to mark loaded=True so the setter actually writes.
    import time as _time

    _time.sleep(0.2)
    rec.reconcile(screen())

    _, set_value = setters[-1]
    set_value("dark")
    rec.reconcile(screen())

    deadline = _time.monotonic() + 1.0
    while _time.monotonic() < deadline:
        if asyncio.run(AsyncStorage.get_json("theme")) == "dark":
            break
        _time.sleep(0.02)
    assert asyncio.run(AsyncStorage.get_json("theme")) == "dark"
