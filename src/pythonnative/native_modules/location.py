"""Cross-platform location / GPS access.

[`Location.get_current`][pythonnative.native_modules.location.Location.get_current]
is a coroutine that resolves to a ``(latitude, longitude)`` tuple, or
``None`` if no fix is available (the user denied permission, location
services are off, or the request timed out).
The native ``Location`` module owns the ``CLLocationManager`` /
``LocationManager`` session and resolves the call with
``{"latitude", "longitude", "accuracy", "altitude", "timestamp"}``.

The first call prompts for when-in-use permission on both platforms
(``requestWhenInUseAuthorization`` on iOS, the
``ACCESS_FINE_LOCATION`` runtime prompt on Android), so there is no
separate ``Permissions.request`` step unless you want to ask earlier.
Declare ``location_when_in_use`` in the ``[permissions]`` table of
``pythonnative.toml`` so the manifest entry and Info.plist usage string
are generated.

Example:
    ```python
    import pythonnative as pn

    async def show_position():
        coords = await pn.Location.get_current()
        if coords is None:
            return
        lat, lon = coords
        print(f"You are at {lat:.5f}, {lon:.5f}")
    ```
"""

from __future__ import annotations

from typing import Dict, Literal, Optional, Tuple

from .registry import NativeModuleError, native_module

Coords = Tuple[float, float]


class Location:
    """GPS / location-services interface."""

    @staticmethod
    async def get_current(
        *, accuracy: Literal["balanced", "high"] = "balanced", timeout: float = 10.0
    ) -> Optional[Coords]:
        """Request the device's current location.

        Args:
            accuracy: Balanced accuracy or the highest available accuracy.
            timeout: Maximum seconds to wait for a fix.

        Returns:
            ``(latitude, longitude)`` if a fix was obtained, otherwise
            ``None`` (permission denied, location services off, or the
            request timed out).

        Raises:
            NativeModuleError: If the native module fails.
        """
        fix = await Location.get_current_fix(accuracy=accuracy, timeout=timeout)
        if fix is None:
            return None
        return (fix["latitude"], fix["longitude"])

    @staticmethod
    async def get_current_fix(
        *, accuracy: Literal["balanced", "high"] = "balanced", timeout: float = 10.0
    ) -> Optional[Dict[str, float]]:
        """Like ``get_current`` but returns the full fix dict.

        Keys: ``latitude``, ``longitude``, and when the platform reports
        them ``accuracy`` (meters), ``altitude`` (meters), ``speed``
        (m/s), ``heading`` (degrees), ``timestamp`` (Unix seconds).
        """
        result = await native_module("Location").call_async("get_current", accuracy=accuracy, timeout=timeout)
        if not isinstance(result, dict):
            return None
        fix: Dict[str, float] = {k: float(v) for k, v in result.items() if v is not None}
        if "latitude" not in fix or "longitude" not in fix:
            raise NativeModuleError("Location", "get_current", f"fix is missing coordinates: {sorted(result)}")
        return fix
