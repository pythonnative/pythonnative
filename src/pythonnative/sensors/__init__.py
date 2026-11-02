"""Motion and pressure sensors, as async iterators.

Enable it in ``pythonnative.toml``:

```toml
[plugins]
use = ["sensors"]

[permissions]
motion = "Measure air pressure for your altitude."
```

iOS's ``CMAltimeter``, behind [`Barometer`][pythonnative.sensors.Barometer],
needs ``NSMotionUsageDescription``: without it the app is terminated at the
call. The plugin compiles that API in, so the build requires the ``motion``
line even if you only use the accelerometer, which never prompts.

Every platform reports the same units and axes:

| Sensor | Unit | At rest, flat on a table, screen up |
| --- | --- | --- |
| ``Accelerometer`` | m/s^2, including gravity | ``z`` is about +9.81 |
| ``Gyroscope`` | rad/s, counterclockwise positive | all about 0 |
| ``Magnetometer`` | microtesla | depends on where you are |
| ``Barometer`` | hPa | about 1013 at sea level |

Axes are the device's: ``x`` to the right of the screen, ``y`` to its top, and
``z`` out of its face.

Example:
    ```python
    from pythonnative.sensors import Accelerometer

    async def watch_motion() -> None:
        if not Accelerometer.is_available():
            return
        async for reading in Accelerometer.readings(hz=30):
            print(reading.x, reading.y, reading.z)
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncGenerator, AsyncIterator, Dict, Literal, Mapping, Protocol

from ..native_modules.registry import NativeModuleError, event_stream, native_module
from ..sdk.plugin import plugin_module

__all__ = ["Accelerometer", "Barometer", "Gyroscope", "Magnetometer", "Pressure", "Vector"]

_SensorName = Literal["accelerometer", "gyroscope", "magnetometer", "barometer"]

_MAX_HZ = 100.0
"""CoreMotion's documented ceiling. Android 12 also rejects rates above 200 Hz without a permission."""


@dataclass(frozen=True)
class Vector:
    """One three-axis reading.

    Attributes:
        x: Along the device's right edge.
        y: Along the device's top edge.
        z: Out of the device's face.
        timestamp: Unix seconds when the sensor took the reading.
    """

    x: float
    y: float
    z: float
    timestamp: float


@dataclass(frozen=True)
class Pressure:
    """One barometer reading.

    Attributes:
        hpa: Air pressure in hectopascals.
        timestamp: Unix seconds when the sensor took the reading.
    """

    hpa: float
    timestamp: float


class _SensorsService(Protocol):
    def is_available(self, sensor: _SensorName) -> bool: ...

    async def start(self, sensor: _SensorName, *, hz: float = 30.0) -> int: ...

    def stop(self, id: int) -> None: ...


class _Fallback:
    """No sensors off device: nothing is available, and tests can ``emit`` readings."""

    def __init__(self) -> None:
        self._next = 0

    def is_available(self, sensor: str) -> bool:
        del sensor
        return False

    def start(self, sensor: str, *, hz: float = 30.0) -> int:
        del sensor, hz
        self._next += 1
        return self._next

    def stop(self, id: int) -> None:
        del id


plugin_module(
    "Sensors",
    _SensorsService,
    plugin="sensors",
    events={"reading": Dict[str, Any]},
    fallback=_Fallback,
    browser=True,
)


def _vector(payload: Mapping[str, Any]) -> Vector:
    try:
        return Vector(float(payload["x"]), float(payload["y"]), float(payload["z"]), float(payload["timestamp"]))
    except KeyError as missing:
        raise NativeModuleError("Sensors", "start", f"reading is missing {missing}: {sorted(payload)}") from None


def _pressure(payload: Mapping[str, Any]) -> Pressure:
    try:
        return Pressure(float(payload["hpa"]), float(payload["timestamp"]))
    except KeyError as missing:
        raise NativeModuleError("Sensors", "start", f"reading is missing {missing}: {sorted(payload)}") from None


def _stream(sensor: str, hz: float) -> AsyncGenerator[Any, None]:
    if not 0 < hz <= _MAX_HZ:
        raise ValueError(f"hz must be above 0 and at most {_MAX_HZ:g}, got {hz!r}")
    return event_stream(native_module("Sensors"), "reading", start="start", stop="stop", sensor=sensor, hz=float(hz))


class _VectorSensor:
    _sensor: str = ""

    @classmethod
    def is_available(cls) -> bool:
        """Whether this device has the sensor.

        Returns:
            ``True`` when ``readings`` can start. Always ``False`` on the iOS
            simulator, which has no sensors.
        """
        return bool(native_module("Sensors").call("is_available", sensor=cls._sensor))

    @classmethod
    async def readings(cls, *, hz: float = 30) -> AsyncIterator[Vector]:
        """Yield readings until the iteration ends, which stops the sensor.

        Leaving the ``async for`` or canceling its task stops the hardware, so
        this is safe to run from ``use_effect``. The iterator ends only when
        the caller stops it.

        Args:
            hz: Readings per second to ask for, above 0 and at most 100. The
                hardware may deliver a different rate.

        Yields:
            One [`Vector`][pythonnative.sensors.Vector] per reading.

        Raises:
            ValueError: If ``hz`` is out of range.
            NativeModuleError: With the code ``unavailable`` when the device
                has no such sensor, or ``plugin_not_enabled`` when ``sensors``
                isn't in the build.
        """
        stream = _stream(cls._sensor, hz)
        try:
            async for payload in stream:
                yield _vector(payload)
        finally:
            await stream.aclose()


class Accelerometer(_VectorSensor):
    """Acceleration in m/s^2, including gravity.

    A device at rest, flat on a table with its screen up, reads ``z`` of about
    +9.81: the sensor reports the table pushing up. Android and the W3C
    ``DeviceMotionEvent`` work this way natively. CoreMotion reports g with the
    opposite sign, so iOS multiplies by -9.80665.
    """

    _sensor = "accelerometer"


class Gyroscope(_VectorSensor):
    """Rotation rate in rad/s around each axis, counterclockwise positive.

    CoreMotion and Android already agree on this. The browser reports degrees
    per second, so the preview converts them.
    """

    _sensor = "gyroscope"


class Magnetometer(_VectorSensor):
    """Magnetic field in microtesla.

    iOS reports the raw field, which includes the device's own bias of up to
    hundreds of microtesla. Android reports a calibrated field, around 25 to 65
    microtesla. Don't build a compass on the raw value without calibrating it.
    Browsers have no magnetometer API, so it's unavailable in the preview.
    """

    _sensor = "magnetometer"


class Barometer:
    """Air pressure in hPa.

    iOS reads ``CMAltimeter``, which reports kilopascals (multiplied by 10
    here), delivers about once a second regardless of ``hz``, and may ask the
    user for Motion and Fitness permission on first use. Android delivers at
    the requested rate where the hardware can. Browsers have no barometer API,
    so it's unavailable in the preview.
    """

    @staticmethod
    def is_available() -> bool:
        """Whether this device has a barometer.

        Returns:
            ``True`` when ``readings`` can start. Always ``False`` on the iOS
            simulator, which has no sensors.
        """
        return bool(native_module("Sensors").call("is_available", sensor="barometer"))

    @staticmethod
    async def readings(*, hz: float = 30) -> AsyncIterator[Pressure]:
        """Yield readings until the iteration ends, which stops the sensor.

        Args:
            hz: Readings per second to ask for, above 0 and at most 100. iOS
                ignores it and delivers about once a second.

        Yields:
            One [`Pressure`][pythonnative.sensors.Pressure] per reading.

        Raises:
            ValueError: If ``hz`` is out of range.
            NativeModuleError: With the code ``unavailable`` when the device
                has no barometer, ``permission_denied`` when the user refuses
                on iOS, or ``plugin_not_enabled`` when ``sensors`` isn't in
                the build.
        """
        stream = _stream("barometer", hz)
        try:
            async for payload in stream:
                yield _pressure(payload)
        finally:
            await stream.aclose()
