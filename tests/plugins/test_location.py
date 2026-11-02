"""Tests for the ``location`` capability's facade, fallback, and manifest."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import pythonnative
from pythonnative.location import Location, Position
from pythonnative.native_modules import registry
from pythonnative.project.plugins import load_plugin
from pythonnative.sdk.schema import MODULES


def test_manifest_loads_and_requires_its_permission() -> None:
    plugin = load_plugin(Path(pythonnative.__file__).parent / "location" / "native")
    assert plugin.name == "location"
    assert plugin.requires_permissions == ("location_when_in_use",)
    assert plugin.web_entry == "web/index.js"


def test_contract_declares_the_stream() -> None:
    contract = MODULES["Location"]
    assert {"get_current", "start_watching", "stop_watching"} <= set(contract.methods)
    assert "position" in contract.events


def test_fallback_has_no_fix() -> None:
    assert asyncio.run(Location.get_current()) is None


class _Fix:
    def get_current(self, *, accuracy: str = "balanced", timeout: float = 10.0) -> dict[str, float]:
        return {"latitude": 1.5, "longitude": 2.5, "accuracy": 3.0}


def test_a_fix_becomes_a_position() -> None:
    registry._reset_for_tests()
    registry.register_python_module("Location", _Fix())
    try:
        position = asyncio.run(Location.get_current(accuracy="high"))
    finally:
        registry.unregister_python_module("Location")
        registry._reset_for_tests()
    assert position == Position(latitude=1.5, longitude=2.5, accuracy=3.0)


class _Broken:
    def get_current(self, *, accuracy: str = "balanced", timeout: float = 10.0) -> dict[str, float]:
        return {"accuracy": 3.0}


def test_a_fix_without_coordinates_raises() -> None:
    registry._reset_for_tests()
    registry.register_python_module("Location", _Broken())
    try:
        with pytest.raises(registry.NativeModuleError, match="missing coordinates"):
            asyncio.run(Location.get_current())
    finally:
        registry.unregister_python_module("Location")
        registry._reset_for_tests()


async def test_watch_yields_positions_and_stops_when_the_iteration_ends() -> None:
    stopped: list[int] = []

    class Watcher:
        def start_watching(self, *, accuracy: str = "balanced", distance: float = 0.0) -> int:
            return 7

        def stop_watching(self, id: int) -> None:
            stopped.append(id)

    registry._reset_for_tests()
    registry.register_python_module("Location", Watcher())
    try:
        stream = Location.watch(distance=10)
        pending = asyncio.ensure_future(stream.__anext__())
        await asyncio.sleep(0.01)
        # Another stream's fix isn't this one's.
        registry.emit("Location", "position", {"id": 99, "value": {"latitude": 0.0, "longitude": 0.0}})
        registry.emit("Location", "position", {"id": 7, "value": {"latitude": 4.0, "longitude": 5.0}})
        assert await asyncio.wait_for(pending, 1) == Position(latitude=4.0, longitude=5.0)
        await stream.aclose()
        assert stopped == [7]
    finally:
        registry.unregister_python_module("Location")
        registry._reset_for_tests()


async def test_watch_stops_when_its_task_is_cancelled() -> None:
    stopped: list[int] = []

    class Watcher:
        def start_watching(self, *, accuracy: str = "balanced", distance: float = 0.0) -> int:
            return 3

        def stop_watching(self, id: int) -> None:
            stopped.append(id)

    registry._reset_for_tests()
    registry.register_python_module("Location", Watcher())

    async def consume() -> None:
        async for _ in Location.watch():
            pass

    try:
        task = asyncio.ensure_future(consume())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped == [3]
    finally:
        registry.unregister_python_module("Location")
        registry._reset_for_tests()
