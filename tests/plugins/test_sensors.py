"""``pythonnative.sensors``: the off-device fallback, the streams, and the plugin manifest."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import pytest

import pythonnative.sensors as sensors
from pythonnative.native_modules.registry import (
    NativeModuleError,
    emit,
    native_module,
    register_python_module,
)
from pythonnative.project.plugins import load_plugin
from pythonnative.sdk import schema
from pythonnative.sensors import Accelerometer, Barometer, Gyroscope, Magnetometer, Pressure, Vector

NATIVE = Path(sensors.__file__).parent / "native"


@pytest.fixture(autouse=True)
def _restore_fallback() -> Any:
    yield
    register_python_module("Sensors", sensors._Fallback)


class _Recording:
    """A scripted module that records its calls, standing in for native."""

    def __init__(self, *, available: bool = True, failure: Optional[Exception] = None) -> None:
        self.available = available
        self.failure = failure
        self.started: List[Dict[str, Any]] = []
        self.stopped: List[int] = []

    def is_available(self, sensor: str) -> bool:
        del sensor
        return self.available

    def start(self, sensor: str, *, hz: float = 30.0) -> int:
        if self.failure is not None:
            raise self.failure
        self.started.append({"sensor": sensor, "hz": hz})
        return len(self.started)

    def stop(self, id: int) -> None:
        self.stopped.append(id)


async def _take(stream: AsyncIterator[Any], payloads: List[Dict[str, Any]], *, wrong_id: bool = False) -> List[Any]:
    """Emit ``payloads`` once ``stream`` has started, and collect one reading per payload."""
    collected: List[Any] = []

    async def feed() -> None:
        await asyncio.sleep(0.01)
        if wrong_id:
            emit("Sensors", "reading", {"id": 99, "value": payloads[0]})
        for payload in payloads:
            emit("Sensors", "reading", {"id": 1, "value": payload})

    task = asyncio.ensure_future(feed())
    async for reading in stream:
        collected.append(reading)
        if len(collected) == len(payloads):
            break
    await task
    await stream.aclose()  # type: ignore[attr-defined]
    return collected


@pytest.mark.parametrize("sensor", [Accelerometer, Gyroscope, Magnetometer, Barometer])
def test_nothing_is_available_off_device(sensor: Any) -> None:
    assert sensor.is_available() is False


def test_available_asks_the_module_for_that_sensor() -> None:
    asked: List[str] = []

    class Module(_Recording):
        def is_available(self, sensor: str) -> bool:
            asked.append(sensor)
            return True

    register_python_module("Sensors", Module())
    assert Accelerometer.is_available() and Gyroscope.is_available()
    assert Magnetometer.is_available() and Barometer.is_available()
    assert asked == ["accelerometer", "gyroscope", "magnetometer", "barometer"]


def test_vector_stream_yields_frozen_records_and_stops_the_sensor() -> None:
    module = _Recording()
    register_python_module("Sensors", module)
    payload = {"x": 1, "y": 2.5, "z": 9.81, "timestamp": 100.0}

    readings = asyncio.run(_take(Accelerometer.readings(hz=10), [payload]))

    assert readings == [Vector(1.0, 2.5, 9.81, 100.0)]
    assert module.started == [{"sensor": "accelerometer", "hz": 10.0}]
    assert module.stopped == [1]
    with pytest.raises(AttributeError):
        readings[0].x = 0.0  # type: ignore[misc]


def test_each_sensor_starts_its_own_hardware() -> None:
    for sensor, name in ((Gyroscope, "gyroscope"), (Magnetometer, "magnetometer")):
        module = _Recording()
        register_python_module("Sensors", module)
        readings = asyncio.run(_take(sensor.readings(), [{"x": 0, "y": 0, "z": 1, "timestamp": 2}]))
        assert isinstance(readings[0], Vector)
        assert module.started == [{"sensor": name, "hz": 30.0}]


def test_barometer_yields_pressure() -> None:
    module = _Recording()
    register_python_module("Sensors", module)
    readings = asyncio.run(_take(Barometer.readings(), [{"hpa": 1013.25, "timestamp": 5}]))
    assert readings == [Pressure(1013.25, 5.0)]
    assert module.started[0]["sensor"] == "barometer"
    assert module.stopped == [1]


def test_stream_ignores_other_subscriptions() -> None:
    register_python_module("Sensors", _Recording())
    payload = {"x": 1, "y": 2, "z": 3, "timestamp": 4}
    readings = asyncio.run(_take(Accelerometer.readings(), [payload], wrong_id=True))
    assert readings == [Vector(1.0, 2.0, 3.0, 4.0)]


def test_cancelling_the_task_stops_the_sensor() -> None:
    module = _Recording()
    register_python_module("Sensors", module)

    async def consume() -> None:
        async for _ in Accelerometer.readings():
            pass

    async def run() -> None:
        task = asyncio.ensure_future(consume())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert module.stopped == [1]


def test_breaking_out_of_the_loop_stops_the_sensor() -> None:
    module = _Recording()
    register_python_module("Sensors", module)

    async def run() -> None:
        async def feed() -> None:
            await asyncio.sleep(0.01)
            emit("Sensors", "reading", {"id": 1, "value": {"x": 0, "y": 0, "z": 0, "timestamp": 0}})

        task = asyncio.ensure_future(feed())
        async for _ in Accelerometer.readings():
            break
        await task
        await asyncio.sleep(0.01)

    asyncio.run(run())
    assert module.stopped == [1]


def test_unavailable_raises_with_its_code() -> None:
    failure = NativeModuleError("Sensors", "start", "This device has no accelerometer", "unavailable")
    module = _Recording(available=False, failure=failure)
    register_python_module("Sensors", module)

    async def run() -> None:
        async for _ in Accelerometer.readings():
            pass

    with pytest.raises(NativeModuleError) as raised:
        asyncio.run(run())
    assert raised.value.code == "unavailable"
    assert module.stopped == []


@pytest.mark.parametrize("hz", [0, -1, 101])
def test_rate_out_of_range_is_rejected(hz: float) -> None:
    async def run() -> None:
        async for _ in Accelerometer.readings(hz=hz):
            pass

    with pytest.raises(ValueError, match="hz"):
        asyncio.run(run())


def test_malformed_reading_raises() -> None:
    register_python_module("Sensors", _Recording())
    with pytest.raises(NativeModuleError, match="missing"):
        asyncio.run(_take(Accelerometer.readings(), [{"x": 1, "timestamp": 2}]))


def test_fallback_stream_runs_and_can_be_driven_by_emit() -> None:
    payload = {"hpa": 990.0, "timestamp": 1.0}
    assert asyncio.run(_take(Barometer.readings(), [payload])) == [Pressure(990.0, 1.0)]


def test_contract() -> None:
    contract = schema.MODULES["Sensors"]
    assert contract.methods["start"]["async"] is True
    assert contract.methods["is_available"]["async"] is False
    assert contract.methods["start"]["arguments"]["sensor"]["enum"] == [
        "accelerometer",
        "gyroscope",
        "magnetometer",
        "barometer",
    ]
    assert "reading" in contract.events
    assert native_module("Sensors") is not None


def test_manifest_loads_and_requires_the_motion_usage_string() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "sensors"
    assert plugin.requires_permissions == ("motion",)
    assert plugin.has_ios and plugin.has_android
