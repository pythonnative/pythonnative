"""Cross-platform location / GPS access.

[`Location.get_current`][pythonnative.native_modules.location.Location.get_current]
is a coroutine that resolves to a ``(latitude, longitude)`` tuple, or
``None`` if no recent fix is available or the user denies permission.

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

import asyncio
from typing import Any, Callable, Dict, Optional, Tuple

from .. import diagnostics
from ..runtime import resolve_future
from ..utils import IS_ANDROID, IS_IOS

# Retain pool keyed by ``id(delegate)`` so iOS / Android listeners
# aren't garbage-collected before the platform calls back.
_pending_delegates: Dict[int, Any] = {}

Coords = Tuple[float, float]


class Location:
    """GPS / location-services interface."""

    @staticmethod
    async def get_current(**options: Any) -> Optional[Coords]:
        """Request the device's current location.

        Args:
            **options: Reserved for platform-specific tuning (e.g.,
                ``accuracy``, ``timeout``).

        Returns:
            ``(latitude, longitude)`` if a fix was obtained, otherwise
            ``None``.
        """
        del options
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Optional[Coords]] = loop.create_future()

        def _on_result(coords: Optional[Coords]) -> None:
            resolve_future(future, coords)

        if IS_ANDROID:
            _android_get(_on_result)
        elif IS_IOS:
            _ios_get(_on_result)
        else:
            resolve_future(future, None)

        return await future


# ======================================================================
# iOS implementation: CLLocationManagerDelegate
# ======================================================================


def _ios_get(on_result: Callable[[Optional[Coords]], None]) -> None:
    try:
        from rubicon.objc import ObjCClass, objc_method

        CLLocationManager = ObjCClass("CLLocationManager")
        NSObject = ObjCClass("NSObject")

        class _PNLocationDelegate(NSObject):  # type: ignore[misc,valid-type]
            _callback: Optional[Callable[[Optional[Coords]], None]] = None
            _manager: Any = None
            _delivered: bool = False

            def _finish(self, coords: Optional[Coords]) -> None:
                if self._delivered:
                    return
                self._delivered = True
                try:
                    if self._manager is not None:
                        self._manager.stopUpdatingLocation()
                except Exception:
                    diagnostics.swallowed("location._ios_get._PNLocationDelegate._finish")
                cb = self._callback
                self._callback = None
                _pending_delegates.pop(id(self), None)
                if cb is not None:
                    try:
                        cb(coords)
                    except Exception:
                        diagnostics.swallowed("location._ios_get._PNLocationDelegate._finish")

            @objc_method
            def locationManager_didUpdateLocations_(self, manager: Any, locations: Any) -> None:
                del manager
                try:
                    last = locations.lastObject
                    if last is None:
                        return
                    coord = last.coordinate
                    self._finish((float(coord.latitude), float(coord.longitude)))
                except Exception:
                    self._finish(None)

            @objc_method
            def locationManager_didFailWithError_(self, manager: Any, error: Any) -> None:
                del manager, error
                self._finish(None)

            @objc_method
            def locationManagerDidChangeAuthorization_(self, manager: Any) -> None:
                try:
                    status = int(manager.authorizationStatus)
                except Exception:
                    status = 0
                if status in (3, 4):  # AuthorizedAlways, AuthorizedWhenInUse
                    try:
                        manager.startUpdatingLocation()
                    except Exception:
                        diagnostics.swallowed(
                            "location._ios_get._PNLocationDelegate.locationManagerDidChangeAuthorization_"
                        )

        delegate = _PNLocationDelegate.new()
        delegate._callback = on_result
        _pending_delegates[id(delegate)] = delegate

        manager = CLLocationManager.alloc().init()
        manager.setDelegate_(delegate)
        delegate._manager = manager
        try:
            manager.requestWhenInUseAuthorization()
        except Exception:
            diagnostics.swallowed("location._ios_get")
        try:
            manager.startUpdatingLocation()
        except Exception:
            diagnostics.swallowed("location._ios_get")
    except Exception:
        on_result(None)


# ======================================================================
# Android implementation: LocationListener
# ======================================================================


def _android_get(on_result: Callable[[Optional[Coords]], None]) -> None:
    try:
        from java import dynamic_proxy, jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        Context = jclass("android.content.Context")
        lm = ctx.getSystemService(Context.LOCATION_SERVICE)

        # Try the most recent known fix first; it's instant and avoids
        # the GPS warm-up delay.
        try:
            for provider in ("gps", "network", "passive"):
                loc = lm.getLastKnownLocation(provider)
                if loc is not None:
                    on_result((float(loc.getLatitude()), float(loc.getLongitude())))
                    return
        except Exception:
            diagnostics.swallowed("location._android_get")

        LocationListener = jclass("android.location.LocationListener")
        delivered = [False]

        def _finish(coords: Optional[Coords], listener: Any) -> None:
            if delivered[0]:
                return
            delivered[0] = True
            try:
                lm.removeUpdates(listener)
            except Exception:
                diagnostics.swallowed("location._android_get._finish")
            _pending_delegates.pop(id(listener), None)
            try:
                on_result(coords)
            except Exception:
                diagnostics.swallowed("location._android_get._finish")

        class _PNLocationListener(dynamic_proxy(LocationListener)):  # type: ignore[misc]
            def onLocationChanged(self, loc: Any) -> None:
                try:
                    coords = (float(loc.getLatitude()), float(loc.getLongitude()))
                except Exception:
                    coords = None
                _finish(coords, self)

            def onStatusChanged(self, provider: Any, status: int, extras: Any) -> None:
                del provider, status, extras

            def onProviderEnabled(self, provider: Any) -> None:
                del provider

            def onProviderDisabled(self, provider: Any) -> None:
                del provider
                _finish(None, self)

        listener = _PNLocationListener()
        _pending_delegates[id(listener)] = listener
        try:
            lm.requestSingleUpdate("gps", listener, None)
        except Exception:
            try:
                lm.requestLocationUpdates("network", 1000, 0.0, listener)
            except Exception:
                _finish(None, listener)
    except Exception:
        on_result(None)
