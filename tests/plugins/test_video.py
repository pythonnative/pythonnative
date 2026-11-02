"""``pythonnative.video``: the props contract, the handle, events, and the plugin manifest."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, List

import pytest

import pythonnative as pn
import pythonnative.video as video
from pythonnative.handles import make_handle
from pythonnative.project.plugins import load_plugin
from pythonnative.sdk import schema
from pythonnative.testing import render
from pythonnative.video import Video, VideoHandle, VideoInfo

NATIVE = Path(video.__file__).parent / "native"


def test_defaults_and_props_reach_the_view() -> None:
    result = render(Video(source="https://example.com/a.mp4", style=pn.style(height=200)))
    view = result.get_by_type("Video")
    assert view.props["source"] == "https://example.com/a.mp4"
    assert view.props["controls"] is False
    assert view.props["autoplay"] is False
    assert view.props["loop"] is False
    assert view.props["muted"] is False
    assert view.props["volume"] == 1.0
    assert view.props["rate"] == 1.0
    assert view.props["resize_mode"] == "contain"
    assert view.props["progress_interval"] == 0.25
    assert "poster" not in view.props or view.props["poster"] is None


def test_every_prop_is_passed_on() -> None:
    result = render(
        Video(
            "https://example.com/a.mp4",
            controls=True,
            autoplay=True,
            loop=True,
            muted=True,
            volume=0.5,
            rate=2.0,
            resize_mode="cover",
            poster="https://example.com/a.png",
            progress_interval=1.0,
        )
    )
    view = result.get_by_type("Video")
    for name, expected in {
        "controls": True,
        "autoplay": True,
        "loop": True,
        "muted": True,
        "volume": 0.5,
        "rate": 2.0,
        "resize_mode": "cover",
        "poster": "https://example.com/a.png",
        "progress_interval": 1.0,
    }.items():
        assert view.props[name] == expected


def test_asset_and_path_sources_become_uris() -> None:
    result = render(pn.Column(Video(pn.asset("clips/a.mp4")), Video(Path("/tmp/b.mp4"), poster=pn.asset("a.png"))))
    first, second = result.get_all_by_type("Video")
    assert first.props["source"] == "asset://clips/a.mp4"
    assert second.props["source"] == "/tmp/b.mp4"
    assert second.props["poster"] == "asset://a.png"


def test_invalid_resize_mode_is_rejected() -> None:
    with pytest.raises(Exception, match="resize_mode"):
        render(Video(resize_mode="zoom"))  # type: ignore[arg-type]


def test_events_arrive_as_typed_values() -> None:
    ready: List[VideoInfo] = []
    progress: List[Any] = []
    ended: List[bool] = []
    errors: List[str] = []
    buffering: List[bool] = []
    result = render(
        Video(
            "a.mp4",
            on_ready=ready.append,
            on_progress=lambda position, duration: progress.append((position, duration)),
            on_end=lambda: ended.append(True),
            on_error=errors.append,
            on_buffering=buffering.append,
        )
    )
    view = result.get_by_type("Video")
    result.fire(view, "on_ready", {"duration": 4.0, "width": 320, "height": 180})
    result.fire(view, "on_progress", 1.5, 4.0)
    result.fire(view, "on_buffering", True)
    result.fire(view, "on_end")
    result.fire(view, "on_error", "bad file")
    assert ready == [VideoInfo(4.0, 320, 180)]
    assert isinstance(ready[0], VideoInfo)
    assert progress == [(1.5, 4.0)]
    assert buffering == [True]
    assert ended == [True]
    assert errors == ["bad file"]


def test_ref_publishes_the_typed_handle_and_clears_on_unmount() -> None:
    ref = pn.Ref()
    result = render(Video("a.mp4", ref=ref))
    assert isinstance(ref.current, VideoHandle)
    assert ref.current.type_name == "Video"
    assert "ref" not in result.get_by_type("Video").props
    result.unmount()
    assert ref.current is None


def test_handle_commands_cross_the_contract() -> None:
    ref = pn.Ref()
    result = render(Video("a.mp4", ref=ref))
    handle = ref.current
    handle.play()
    handle.pause()
    handle.seek(3)
    result.settle()
    names = [(name, args) for _, name, args in result.backend.commands]
    assert names == [("play", {}), ("pause", {}), ("seek", {"seconds": 3.0})]


def test_handle_position_awaits_the_view() -> None:
    class Backend:
        def command(self, tag: int, name: str, args: Any) -> Any:
            assert (tag, name, args) == (7, "position", {})
            future: Any = asyncio.get_running_loop().create_future()
            future.set_result(2.5)
            return future

    async def ask() -> float:
        return await make_handle("Video", 7, Backend()).position()  # type: ignore[attr-defined]

    assert asyncio.run(ask()) == 2.5


def test_contract_declares_the_commands_and_container_measurement() -> None:
    contract = schema.COMPONENTS["Video"]
    assert contract.measurement == "container"
    assert set(contract.commands) == {"play", "pause", "seek", "position"}
    assert contract.commands["seek"]["required"] == ["seconds"]
    assert contract.commands["position"]["result"] == {"type": "number"}


def test_manifest_loads_and_pins_media3() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "video"
    assert plugin.ios_entry == "VideoPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.video.VideoPlugin"
    assert plugin.maven_dependencies == (
        "androidx.media3:media3-exoplayer:1.5.1",
        "androidx.media3:media3-ui:1.5.1",
    )
    assert plugin.ios_sources and plugin.android_sources
    assert (NATIVE / "web" / "index.js").is_file()


def test_generated_contract_matches_the_declarations() -> None:
    import json

    written = json.loads((NATIVE / "schema.json").read_text())
    assert list(written["components"]) == ["Video"]
    assert written["modules"] == {}
    assert set(written["components"]["Video"]["commands"]) == {"play", "pause", "seek", "position"}
