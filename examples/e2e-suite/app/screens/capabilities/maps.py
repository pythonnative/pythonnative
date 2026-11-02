"""Demo screen for [`MapView`][pythonnative.maps.MapView].

The map draws one marker and one polyline, and the readouts mirror every
event: ``on_ready``, ``on_region_change``, ``on_marker_press``, ``on_press``,
and ``on_error``. "Fly to Bergen" exercises the typed handle, and the map type
buttons change a prop. On an Android build with no API key, the view shows why
and ``on_error`` reports the same thing.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText
from pythonnative.maps import Coordinate, MapView, Marker, Polyline, Region

OSLO = Coordinate(59.9139, 10.7522)
BERGEN = Coordinate(60.3913, 5.3221)
START = Region(OSLO, 0.2, 0.2)


@pn.component
def MapsDemo() -> pn.Node:
    """Render a map, its event readouts, and the controls that drive it."""
    map_ref = pn.use_ref()
    ready, set_ready = pn.use_state(False)
    pressed, set_pressed = pn.use_state("none")
    marker, set_marker = pn.use_state("none")
    regions, set_regions = pn.use_state(0)
    center, set_center = pn.use_state("unknown")
    error, set_error = pn.use_state("none")
    map_type, set_map_type = pn.use_state("standard")

    def on_region_change(region: Region) -> None:
        set_regions(lambda count: count + 1)
        set_center(f"{region.center.latitude:.1f}, {region.center.longitude:.1f}")

    def fly() -> None:
        if map_ref.current is not None:
            map_ref.current.animate_to(Region(BERGEN, 0.2, 0.2))

    return DemoScreen(
        "Maps",
        "MapView with markers, a polyline, a handle, and events.",
        DemoSection(
            "MapView",
            MapView(
                ref=map_ref,
                initial_region=START,
                markers=[
                    Marker("oslo", OSLO, title="Oslo", description="Start here", color="#2563EB"),
                    Marker("bergen", BERGEN, title="Bergen"),
                ],
                polylines=[Polyline("train", [OSLO, BERGEN], color="#DC2626", width=3)],
                map_type=map_type,
                on_ready=lambda: set_ready(True),
                on_region_change=on_region_change,
                on_marker_press=set_marker,
                on_press=lambda point: set_pressed(f"{point.latitude:.1f}, {point.longitude:.1f}"),
                on_error=set_error,
                style=pn.style(height=260),
            ),
            ResultText("Map ready", "yes" if ready else "no"),
            ResultText("Map error", error),
            ResultText("Region changes", "some" if regions else "none"),
            ResultText("Center", center),
            ResultText("Marker pressed", marker),
            ResultText("Map pressed", pressed),
            ResultText("Map type", map_type),
            pn.Button("Fly to Bergen", on_press=fly),
            pn.Button("Use satellite", on_press=lambda: set_map_type("satellite")),
            Hint("Android needs an API key and Google Play services; without them the map says so."),
        ),
    )
