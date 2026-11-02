"""Device location: one fix, or a stream of them.

Enable it in ``pythonnative.toml``:

```toml
[plugins]
use = ["location"]

[permissions]
location_when_in_use = "Show nearby stores."
```

Example:
    ```python
    from pythonnative.location import Location

    async def show_position() -> None:
        position = await Location.get_current()
        if position is not None:
            print(position.latitude, position.longitude)

    async def follow() -> None:
        async for position in Location.watch(distance=10):
            move_marker(position)
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Literal, Mapping, Optional, Protocol

from ..native_modules.registry import NativeModuleError, event_stream, native_module
from ..sdk.plugin import plugin_module

__all__ = ["Accuracy", "Location", "Position"]

Accuracy = Literal["balanced", "high"]
"""Balanced accuracy saves power; high asks for the best the device can do."""


@dataclass(frozen=True)
class Position:
    """One location fix.

    Attributes:
        latitude: Degrees north.
        longitude: Degrees east.
        accuracy: Horizontal accuracy in meters, when reported.
        altitude: Meters above sea level, when reported.
        speed: Meters per second, when reported.
        heading: Degrees clockwise from north, when reported.
        timestamp: Unix seconds, when reported.
    """

    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    timestamp: Optional[float] = None


class _LocationService(Protocol):
    async def get_current(
        self, *, accuracy: Accuracy = "balanced", timeout: float = 10.0
    ) -> Optional[Dict[str, float]]: ...

    async def start_watching(self, *, accuracy: Accuracy = "balanced", distance: float = 0.0) -> int: ...

    def stop_watching(self, id: int) -> None: ...


class _Fallback:
    """No hardware off device: nothing to report, and tests can ``emit`` positions."""

    def __init__(self) -> None:
        self._next = 0

    def get_current(self, *, accuracy: str = "balanced", timeout: float = 10.0) -> Optional[Dict[str, float]]:
        return None

    def start_watching(self, *, accuracy: str = "balanced", distance: float = 0.0) -> int:
        self._next += 1
        return self._next

    def stop_watching(self, id: int) -> None:
        del id


plugin_module(
    "Location",
    _LocationService,
    plugin="location",
    events={"position": Dict[str, Any]},
    fallback=_Fallback,
    browser=True,
)


def _position(fix: Mapping[str, Any], *, method: str) -> Position:
    if "latitude" not in fix or "longitude" not in fix:
        raise NativeModuleError("Location", method, f"fix is missing coordinates: {sorted(fix)}")
    known = ("latitude", "longitude", "accuracy", "altitude", "speed", "heading", "timestamp")
    return Position(**{key: float(fix[key]) for key in known if fix.get(key) is not None})


class Location:
    """Location services.

    Raises:
        NativeModuleError: If the native module fails, or with the code
            ``plugin_not_enabled`` when ``location`` isn't in the build.
    """

    @staticmethod
    async def get_current(*, accuracy: Accuracy = "balanced", timeout: float = 10.0) -> Optional[Position]:
        """Request the device's current location, prompting for permission if needed.

        Args:
            accuracy: How hard to try for a precise fix.
            timeout: Maximum seconds to wait.

        Returns:
            The position, or ``None`` when permission was denied, location
            services are off, or the request timed out.
        """
        result = await native_module("Location").call_async("get_current", accuracy=accuracy, timeout=timeout)
        return _position(result, method="get_current") if isinstance(result, dict) else None

    @staticmethod
    async def watch(*, accuracy: Accuracy = "balanced", distance: float = 0.0) -> AsyncIterator[Position]:
        """Yield positions as the device moves, until the iteration ends.

        Prompts for permission when needed. Leaving the ``async for`` (or
        canceling its task) stops the updates, so this is safe to run from
        ``use_effect``. The iterator ends only when the caller stops it.

        Args:
            accuracy: How hard to try for a precise fix.
            distance: Meters the device must move between updates.

        Raises:
            NativeModuleError: With the code ``permission_denied`` when the
                user refuses.
        """
        stream = event_stream(
            native_module("Location"),
            "position",
            start="start_watching",
            stop="stop_watching",
            accuracy=accuracy,
            distance=distance,
        )
        async for fix in stream:
            yield _position(fix, method="watch")
