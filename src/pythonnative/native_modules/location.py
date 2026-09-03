"""Cross-platform location / GPS access.

[`Location.get_current`][pythonnative.native_modules.location.Location.get_current]
is a coroutine that resolves to a ``(latitude, longitude)`` tuple, or
``None`` if no recent fix is available or the user denies permission.
The native ``Location`` module owns the ``CLLocationManager`` /
``LocationManager`` session and resolves the call with
``{"latitude", "longitude", "accuracy", "altitude", "timestamp"}``.

Permission prompts are triggered the first time a location-using API
is called; ensure the appropriate manifest entries
(``android.permission.ACCESS_FINE_LOCATION``) and Info.plist keys
(``NSLocationWhenInUseUsageDescription``) are present.

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

from typing import Any, Dict, Optional, Tuple

from .registry import native_module

Coords = Tuple[float, float]


class Location:
    """GPS / location-services interface."""

    @staticmethod
    async def get_current(**options: Any) -> Optional[Coords]:
        """Request the device's current location.

        Args:
            **options: Forwarded to the native module (``accuracy``,
                ``timeout``). Unknown keys are ignored.

        Returns:
            ``(latitude, longitude)`` if a fix was obtained, otherwise
            ``None``.
        """
        fix = await Location.get_current_fix(**options)
        if fix is None:
            return None
        return (fix["latitude"], fix["longitude"])

    @staticmethod
    async def get_current_fix(**options: Any) -> Optional[Dict[str, float]]:
        """Like ``get_current`` but returns the full fix dict.

        Keys: ``latitude``, ``longitude``, and when the platform reports
        them ``accuracy`` (meters), ``altitude`` (meters), ``speed``
        (m/s), ``heading`` (degrees), ``timestamp`` (Unix seconds).
        """
        try:
            result = await native_module("Location").call_async("get_current", **options)
        except Exception:
            return None
        if not isinstance(result, dict):
            return None
        try:
            fix: Dict[str, float] = {k: float(v) for k, v in result.items() if v is not None}
            fix["latitude"]
            fix["longitude"]
        except (KeyError, TypeError, ValueError):
            return None
        return fix
