"""Where entries were written: getting a fix, and framing a map around them."""

from __future__ import annotations

import math
from typing import Optional, Sequence

from pythonnative.location import Location, Position
from pythonnative.maps import Coordinate, Region
from pythonnative.native_modules import NativeModuleError

from .models import Place

WORLD = Region(Coordinate(20.0, 0.0), latitude_delta=120.0, longitude_delta=180.0)
"""What the map shows before there's anything to show."""

_MINIMUM_SPAN = 0.02
"""About two kilometers, so a single marker doesn't zoom in to one roof."""


async def locate() -> Optional[Position]:
    """Get one position fix, for a new entry.

    A balanced fix usually comes first and costs little. Out of range of the cell
    towers and Wi-Fi it relies on, which is where a field journal gets used, it
    comes back empty, so GPS gets a turn before giving up.

    Returns:
        The position, or ``None`` when the permission was refused, location
        services are off, or no fix came in time. A journal entry doesn't depend on
        any of those, so none is an error here.
    """
    try:
        position = await Location.get_current(accuracy="balanced", timeout=5)
        return position or await Location.get_current(accuracy="high", timeout=10)
    except NativeModuleError:
        return None


def place_from(position: Position, *, name: str = "") -> Place:
    """Turn a position fix into the place an entry records."""
    return Place(position.latitude, position.longitude, position.accuracy, name)


def fit_region(places: Sequence[Place], *, padding: float = 1.4) -> Region:
    """Return the region that frames every place.

    Args:
        places: The markers to frame.
        padding: How much larger than the markers' extent to make it, so that a
            pin at the edge isn't cut off.

    Returns:
        The region, or the whole world when there are no places.
    """
    if not places:
        return WORLD
    latitudes = [place.latitude for place in places]
    longitudes = [place.longitude for place in places]
    north, south = max(latitudes), min(latitudes)
    center_longitude, longitude_span = _longitude_extent(longitudes)
    return Region(
        Coordinate((north + south) / 2, center_longitude),
        latitude_delta=min(170.0, max(_MINIMUM_SPAN, (north - south) * padding)),
        longitude_delta=min(350.0, max(_MINIMUM_SPAN, longitude_span * padding)),
    )


def _longitude_extent(longitudes: Sequence[float]) -> tuple[float, float]:
    """Return the center and span of some longitudes, the short way around the globe."""
    ordered = sorted(longitudes)
    gaps = [(ordered[(index + 1) % len(ordered)] - value) % 360.0 for index, value in enumerate(ordered)]
    widest = max(range(len(gaps)), key=gaps.__getitem__) if len(ordered) > 1 else 0
    span = 360.0 - gaps[widest] if len(ordered) > 1 else 0.0
    start = ordered[(widest + 1) % len(ordered)]
    center = start + span / 2
    return (center + 180.0) % 360.0 - 180.0, span


def tilt_degrees(x: float, y: float) -> Optional[float]:
    """Return how far a device held upright is rotated from level, for the capture screen.

    Args:
        x: Acceleration along the device's right edge.
        y: Acceleration along its top edge.

    Returns:
        Degrees, positive when it's rolled clockwise, or ``None`` when the device
        is lying nearly flat and the reading means nothing.
    """
    if math.hypot(x, y) < 2.0:
        return None
    return math.degrees(math.atan2(x, y))
