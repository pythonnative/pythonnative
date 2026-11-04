"""Maps: a native map view with markers and polylines.

Enable it in ``pythonnative.toml``:

```toml
[plugins]
use = ["maps"]

# Android only. Or leave this out and set GOOGLE_MAPS_API_KEY when building.
[plugins.maps]
android_api_key = "..."
```

iOS uses MapKit and needs no key. Android uses the Google Maps SDK, which needs
an API key and Google Play services on the device. Without either, the view
shows a message saying so and calls ``on_error``; the app keeps running.

Example:
    ```python
    import pythonnative as pn
    from pythonnative.maps import Coordinate, MapView, Marker, Region

    OSLO = Coordinate(59.9139, 10.7522)

    @pn.component
    def Stores() -> pn.Node:
        chosen, set_chosen = pn.use_state(None)
        return pn.Column(
            MapView(
                initial_region=Region(OSLO, 0.05, 0.05),
                markers=[Marker("oslo", OSLO, title="Oslo")],
                on_marker_press=set_chosen,
                style=pn.style(flex=1),
            ),
            pn.Text(chosen or "Pick a store"),
        )
    ```
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Literal, Optional, Sequence

from ..element import Element
from ..handles import HANDLE_TYPES, ViewHandle
from ..hooks import Ref
from ..sdk import Props
from ..sdk.plugin import plugin_component
from ..sdk.schema import COMPONENTS, NativeField, register_schema
from ..sdk.types import encode_value, type_schema
from ..style import StyleProp

__all__ = ["Coordinate", "MapHandle", "MapType", "MapView", "Marker", "Polyline", "Region"]

MapType = Literal["standard", "satellite", "hybrid"]
"""The base map: streets, imagery, or imagery with streets and labels."""


@dataclass(frozen=True)
class Coordinate:
    """A point on Earth.

    Attributes:
        latitude: Degrees north, from -90 to 90.
        longitude: Degrees east, from -180 to 180.
    """

    latitude: float
    longitude: float


@dataclass(frozen=True)
class Region:
    """The rectangle a map shows.

    A map adjusts the region it's given to fit its own shape and zoom levels,
    so the region ``on_region_change`` reports is close to, but rarely equal
    to, the one requested.

    Attributes:
        center: The middle of the rectangle.
        latitude_delta: Its height in degrees of latitude.
        longitude_delta: Its width in degrees of longitude.
    """

    center: Coordinate
    latitude_delta: float
    longitude_delta: float


@dataclass(frozen=True)
class Marker:
    """A pin on the map.

    Attributes:
        id: Identifies the marker across renders and in ``on_marker_press``.
        coordinate: Where it sits.
        title: The callout's title.
        description: The callout's second line.
        color: A hex color string for the pin. Google Maps pins take their
            hue from it, so Android keeps the hue and drops the saturation
            and brightness.
    """

    id: str
    coordinate: Coordinate
    title: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


@dataclass(frozen=True)
class Polyline:
    """A line through a list of coordinates.

    Attributes:
        id: Identifies the line across renders.
        coordinates: The points it passes through, in order.
        color: A hex color string. Defaults to the platform's blue.
        width: Stroke width in logical pixels.
    """

    id: str
    coordinates: Sequence[Coordinate]
    color: Optional[str] = None
    width: float = 2


@dataclass(frozen=True)
class MapViewProps(Props):
    """The wire contract of [`MapView`][pythonnative.maps.MapView]."""

    region: Optional[Region] = None
    initial_region: Optional[Region] = None
    markers: Sequence[Marker] = ()
    polylines: Sequence[Polyline] = ()
    shows_user_location: bool = False
    map_type: MapType = "standard"
    zoom_enabled: bool = True
    scroll_enabled: bool = True
    # Spelled as the View contract spells them: a field that differs from View's
    # drops out of the generated PNViewProps every component shares.
    accessibility_label: Annotated[Optional[str], NativeField()] = None
    test_id: Annotated[Optional[str], NativeField()] = None
    on_region_change: Optional[Callable[[Region], Any]] = None
    on_marker_press: Optional[Callable[[str], Any]] = None
    on_press: Optional[Callable[[Coordinate], Any]] = None
    on_ready: Optional[Callable[[], Any]] = None
    on_error: Optional[Callable[[str], Any]] = None


_map_view = plugin_component("MapView", MapViewProps, plugin="maps", measurement="container")

register_schema(
    dataclasses.replace(
        COMPONENTS["MapView"],
        commands={
            "animate_to": {
                "arguments": {"region": type_schema(Region)},
                "required": ["region"],
                "result": {"type": "null"},
                "defaults": {},
            }
        },
    )
)


class MapHandle(ViewHandle):
    """Handle a ``ref`` on [`MapView`][pythonnative.maps.MapView] receives.

    Example:
        ```python
        import pythonnative as pn
        from pythonnative.maps import Coordinate, MapView, Region

        @pn.component
        def Home() -> pn.Node:
            map_ref = pn.use_ref()
            home = Region(Coordinate(59.91, 10.75), 0.02, 0.02)
            return pn.Column(
                MapView(ref=map_ref, initial_region=home, style=pn.style(height=240)),
                pn.Button("Home", on_press=lambda: map_ref.current.animate_to(home)),
            )
        ```
    """

    __slots__ = ()

    def animate_to(self, region: Region) -> None:
        """Move the map to ``region`` with the platform's animation.

        Args:
            region: Where to go. ``on_region_change`` fires when it arrives.
        """
        self.command("animate_to", region=encode_value(region))


HANDLE_TYPES["MapView"] = MapHandle


def MapView(
    *,
    region: Optional[Region] = None,
    initial_region: Optional[Region] = None,
    markers: Sequence[Marker] = (),
    polylines: Sequence[Polyline] = (),
    shows_user_location: bool = False,
    map_type: MapType = "standard",
    zoom_enabled: bool = True,
    scroll_enabled: bool = True,
    on_region_change: Optional[Callable[[Region], Any]] = None,
    on_marker_press: Optional[Callable[[str], Any]] = None,
    on_press: Optional[Callable[[Coordinate], Any]] = None,
    on_ready: Optional[Callable[[], Any]] = None,
    on_error: Optional[Callable[[str], Any]] = None,
    accessibility_label: Optional[str] = None,
    test_id: Optional[str] = None,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Show a native map: MapKit on iOS, Google Maps on Android.

    A map has no intrinsic size, so give it one with ``style``, such as
    ``pn.style(flex=1)`` or ``pn.style(height=240)``. Passing a ``ref``
    publishes a [`MapHandle`][pythonnative.maps.MapHandle] on ``ref.current``.

    Args:
        region: The region to show, controlled. Each change moves the map
            without animating. To follow the user's panning, store what
            ``on_region_change`` reports and pass it back. A region within a
            rounding error of the current one is ignored, so this can't loop.
        initial_region: The region to start on, uncontrolled. Later changes
            are ignored. ``region`` wins when both are set.
        markers: The pins, as data rather than child elements.
        polylines: The lines, as data rather than child elements.
        shows_user_location: Draw the user's position. The app must already
            have location permission, which this doesn't ask for: enable the
            ``location`` capability and call
            ``Permissions.request("location_when_in_use")`` first. Without the
            permission, Android calls ``on_error`` and tries again the next
            time the app resumes, and iOS draws nothing.
        map_type: The base map.
        zoom_enabled: Whether the user can zoom.
        scroll_enabled: Whether the user can pan.
        on_region_change: Called with the new [`Region`][pythonnative.maps.Region]
            when the map stops moving, however it was moved.
        on_marker_press: Called with a marker's ``id``. On iOS, pressing a
            marker that's already selected doesn't fire it again.
        on_press: Called with the [`Coordinate`][pythonnative.maps.Coordinate]
            pressed on the map itself, not on a marker.
        on_ready: Called once, when the map can be controlled.
        on_error: Called with a message when the map can't work: on Android,
            no API key, no Google Play services, or no location permission for
            ``shows_user_location``; on iOS, map data that failed to load. A
            wrong Android API key isn't reported: the SDK only logs it and
            draws an empty map.
        accessibility_label: Screen reader label for the map.
        test_id: Identifier for UI tests.
        style: Layout and visual style.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity among siblings.

    Returns:
        The map element.

    Raises:
        PluginNotEnabledError: On a device whose build doesn't include ``maps``.
    """
    element = _map_view(
        region=region,
        initial_region=initial_region,
        markers=markers,
        polylines=polylines,
        shows_user_location=shows_user_location,
        map_type=map_type,
        zoom_enabled=zoom_enabled,
        scroll_enabled=scroll_enabled,
        on_region_change=on_region_change,
        on_marker_press=on_marker_press,
        on_press=on_press,
        on_ready=on_ready,
        on_error=on_error,
        accessibility_label=accessibility_label,
        test_id=test_id,
        style=style,
        key=key,
    )
    if ref is None:
        return element
    return Element(element.type, {**element.props, "ref": ref}, list(element.children), key=key)
