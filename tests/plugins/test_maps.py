"""``pythonnative.maps``: the props contract, the handle, events, and the plugin manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

import pytest

import pythonnative as pn
import pythonnative.maps as maps
from pythonnative.maps import Coordinate, MapHandle, MapView, Marker, Polyline, Region
from pythonnative.project import plugin_config
from pythonnative.project.config import AppConfig
from pythonnative.project.plugins import load_plugin
from pythonnative.sdk import schema
from pythonnative.testing import render

NATIVE = Path(maps.__file__).parent / "native"
OSLO = Coordinate(59.91, 10.75)
BERGEN = Coordinate(60.39, 5.32)
REGION = Region(OSLO, 0.1, 0.2)


def test_marker_and_polyline_are_frozen_records_with_optional_fields() -> None:
    marker = Marker("a", OSLO)
    assert (marker.title, marker.description, marker.color) == (None, None, None)
    assert Polyline("line", [OSLO, BERGEN]).width == 2
    with pytest.raises(AttributeError):
        marker.id = "b"  # type: ignore[misc]


def test_map_view_sends_markers_and_polylines_as_typed_data() -> None:
    result = render(
        MapView(
            region=REGION,
            markers=[Marker("a", OSLO, title="Oslo", color="#FF0000")],
            polylines=[Polyline("line", [OSLO, BERGEN], width=3)],
            map_type="hybrid",
            zoom_enabled=False,
            style=pn.style(height=200),
        )
    )
    view = result.get_by_type("MapView")
    assert view.props["map_type"] == "hybrid"
    assert view.props["zoom_enabled"] is False
    assert view.props["markers"] == [Marker("a", OSLO, title="Oslo", color="#FF0000")]
    assert view.props["polylines"] == [Polyline("line", [OSLO, BERGEN], width=3)]
    assert view.props["region"] == REGION


def test_invalid_map_type_is_rejected() -> None:
    with pytest.raises(Exception, match="map_type"):
        render(MapView(map_type="terrain"))


def test_events_arrive_as_records() -> None:
    regions: List[Region] = []
    pressed: List[Coordinate] = []
    markers: List[str] = []
    result = render(MapView(on_region_change=regions.append, on_press=pressed.append, on_marker_press=markers.append))
    view = result.get_by_type("MapView")
    result.fire(
        view,
        "on_region_change",
        {"center": {"latitude": 1.0, "longitude": 2.0}, "latitude_delta": 3.0, "longitude_delta": 4.0},
    )
    result.fire(view, "on_press", {"latitude": 5.0, "longitude": 6.0})
    result.fire(view, "on_marker_press", "a")
    assert regions == [Region(Coordinate(1.0, 2.0), 3.0, 4.0)]
    assert pressed == [Coordinate(5.0, 6.0)]
    assert markers == ["a"]


def test_ready_and_error_events() -> None:
    log: List[Any] = []
    result = render(MapView(on_ready=lambda: log.append("ready"), on_error=log.append))
    view = result.get_by_type("MapView")
    result.fire(view, "on_ready")
    result.fire(view, "on_error", "no key")
    assert log == ["ready", "no key"]


def test_ref_publishes_a_typed_handle_that_animates() -> None:
    captured: List[Any] = []

    @pn.component
    def Screen() -> pn.Node:
        map_ref = pn.use_ref()
        captured.append(map_ref)
        return MapView(ref=map_ref)

    result = render(Screen())
    handle = captured[-1].current
    assert isinstance(handle, MapHandle)
    handle.animate_to(REGION)
    result.settle()
    name, arguments = result.backend.commands[-1][1:]
    assert name == "animate_to"
    assert arguments["region"]["center"] == {"latitude": 59.91, "longitude": 10.75}


def test_contract_declares_the_command_and_stays_container_measured() -> None:
    contract = schema.COMPONENTS["MapView"]
    assert contract.measurement == "container"
    assert contract.commands["animate_to"]["required"] == ["region"]
    assert "on_error" in contract.props


def test_generated_contract_matches_the_facade() -> None:
    import json

    document = json.loads((NATIVE / "schema.json").read_text())
    assert set(document["components"]) == {"MapView"}
    assert document["components"]["MapView"]["commands"].keys() == {"animate_to"}


def test_manifest_loads_with_no_required_permissions() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "maps"
    assert plugin.requires_permissions == ()
    assert plugin.manifest["options"]["android_api_key"]["env"] == "GOOGLE_MAPS_API_KEY"
    dependency = plugin.manifest["android"]["dependencies"][0]
    assert dependency.startswith("com.google.android.gms:play-services-maps:")


def _config(tmp_path: Path, extra: str = "") -> Any:
    path = tmp_path / "pythonnative.toml"
    path.write_text(f'[app]\nid = "com.example.a"\nname = "a"\n\n[plugins]\nuse = ["maps"]\n{extra}')
    return AppConfig.load(tmp_path)


def test_api_key_only_reaches_the_manifest_when_it_is_set(tmp_path: Path) -> None:
    plugin = load_plugin(NATIVE)
    without = plugin_config.resolve_plugin(plugin, _config(tmp_path), environ={})
    assert "manifest" not in without.android
    assert without.android["dependencies"]

    from_env = plugin_config.resolve_plugin(plugin, _config(tmp_path), environ={"GOOGLE_MAPS_API_KEY": "from-env"})
    assert from_env.android["manifest"]["application"] == "android/application.xml"
    fragment = plugin_config._read_fragment(from_env, "android/application.xml")
    assert 'android:name="com.google.android.geo.API_KEY"' in fragment
    assert 'android:value="from-env"' in fragment

    table = '\n[plugins.maps]\nandroid_api_key = "from-table"\n'
    from_table = plugin_config.resolve_plugin(
        plugin, _config(tmp_path, table), environ={"GOOGLE_MAPS_API_KEY": "from-env"}
    )
    assert 'android:value="from-table"' in plugin_config._read_fragment(from_table, "android/application.xml")
