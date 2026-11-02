"""``pythonnative.audio``: the off-device fallback, the facade, and the plugin manifest."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

import pythonnative as pn
import pythonnative.audio as audio
from pythonnative.audio import Audio, Recorder, Recording, Sound
from pythonnative.native_modules.registry import (
    NativeModuleError,
    emit,
    native_module,
    register_python_module,
)
from pythonnative.project.plugins import load_plugin
from pythonnative.sdk import schema

NATIVE = Path(audio.__file__).parent / "native"


@pytest.fixture(autouse=True)
def _fresh_fallback() -> Any:
    register_python_module("Audio", audio._Fallback)
    yield
    register_python_module("Audio", audio._Fallback)


def _impl() -> Any:
    return native_module("Audio").impl  # type: ignore[attr-defined]


def test_sound_runs_against_the_fallback() -> None:
    async def run() -> None:
        sound = await Sound.load("https://example.com/a.mp3", volume=0.5, rate=2.0, looping=True)
        assert sound.looping is True
        assert sound.duration == 0.0
        assert sound.position == 0.0
        sound.play()
        assert _impl().sounds[1]["playing"] is True
        sound.seek(2)
        assert sound.position == 2.0
        sound.pause()
        assert _impl().sounds[1]["playing"] is False
        sound.stop()
        assert sound.position == 0.0
        sound.set_volume(0.25)
        sound.set_rate(1.5)
        sound.looping = False
        assert sound.looping is False
        assert _impl().sounds[1]["volume"] == 0.25
        assert _impl().sounds[1]["rate"] == 1.5

    asyncio.run(run())


def test_sources_become_uris() -> None:
    async def run() -> List[str]:
        first = await Sound.load(pn.asset("a.m4a"))
        second = await Sound.load(Path("/tmp/b.m4a"))
        return [_impl().sounds[first._id]["source"], _impl().sounds[second._id]["source"]]

    assert asyncio.run(run()) == ["asset://a.m4a", "/tmp/b.m4a"]


def test_empty_source_is_rejected_before_native() -> None:
    with pytest.raises(ValueError):
        asyncio.run(Sound.load(""))


def test_on_end_filters_by_sound_and_can_be_removed() -> None:
    async def run() -> None:
        first = await Sound.load("a.m4a")
        second = await Sound.load("b.m4a")
        ended: List[str] = []
        remove = first.on_end(lambda: ended.append("first"))
        second.on_end(lambda: ended.append("second"))
        emit("Audio", "sound_ended", {"id": first._id})
        assert ended == ["first"]
        emit("Audio", "sound_ended", {"id": second._id})
        assert ended == ["first", "second"]
        remove()
        emit("Audio", "sound_ended", {"id": first._id})
        assert ended == ["first", "second"]

    asyncio.run(run())


def test_unload_is_idempotent_and_ends_the_sound() -> None:
    async def run() -> None:
        sound = await Sound.load("a.m4a")
        sound.on_end(lambda: None)
        assert native_module("Audio").listener_count("sound_ended") == 1
        sound.unload()
        sound.unload()
        assert native_module("Audio").listener_count("sound_ended") == 0
        assert _impl().sounds == {}
        with pytest.raises(NativeModuleError) as failure:
            sound.play()
        assert failure.value.code == "unloaded"
        with pytest.raises(NativeModuleError):
            _ = sound.position

    asyncio.run(run())


def test_context_manager_unloads_even_on_error() -> None:
    async def run() -> None:
        with pytest.raises(RuntimeError):
            async with await Sound.load("a.m4a") as sound:
                sound.play()
                assert _impl().sounds
                raise RuntimeError("boom")
        assert _impl().sounds == {}

    asyncio.run(run())


def test_recorder_lifecycle() -> None:
    async def run() -> None:
        recorder = await Recorder.start("note.m4a", quality="low")
        recorder.pause()
        recorder.resume()
        assert recorder.metering() == -160.0
        recording = await recorder.stop()
        assert recording == Recording(path="note.m4a", duration=0.0)
        with pytest.raises(NativeModuleError) as failure:
            await recorder.stop()
        assert failure.value.code == "stopped"
        with pytest.raises(NativeModuleError):
            recorder.pause()

    asyncio.run(run())


def test_recorder_without_a_path_names_a_file() -> None:
    async def run() -> Recording:
        return await (await Recorder.start()).stop()

    assert asyncio.run(run()).path.endswith(".m4a")


def test_recorder_start_surfaces_a_missing_usage_string() -> None:
    class Missing(audio._Fallback):
        def start_recording(self, *, path: Any = None, quality: str = "high") -> int:
            raise NativeModuleError("Audio", "start_recording", "add microphone", "missing_usage_string")

    register_python_module("Audio", Missing)

    with pytest.raises(NativeModuleError) as failure:
        asyncio.run(Recorder.start())
    assert failure.value.code == "missing_usage_string"


def test_stop_accepts_a_plain_mapping_from_the_page() -> None:
    class Page(audio._Fallback):
        def stop_recording(self, *, id: int) -> Dict[str, Any]:  # type: ignore[override]
            return {"path": "blob:x", "duration": 1.5}

    register_python_module("Audio", Page)
    contract = schema.MODULES["Audio"]
    assert contract.methods["stop_recording"]["async"] is True

    async def run() -> Recording:
        return await (await Recorder.start()).stop()

    assert asyncio.run(run()) == Recording("blob:x", 1.5)


def test_set_mode_passes_every_option() -> None:
    Audio.set_mode(category="play_and_record", mix_with_others=True, default_to_speaker=True)
    assert _impl().mode == {
        "category": "play_and_record",
        "mix_with_others": True,
        "duck_others": False,
        "default_to_speaker": True,
        "allow_bluetooth": False,
    }


def test_set_mode_rejects_an_unknown_category() -> None:
    with pytest.raises(Exception, match="category"):
        Audio.set_mode(category="loud")  # type: ignore[arg-type]


def test_contract_declares_sync_and_async_methods() -> None:
    methods = schema.MODULES["Audio"].methods
    for name in ("load_sound", "start_recording", "stop_recording"):
        assert methods[name]["async"] is True
    for name in ("play_sound", "sound_position", "recording_metering", "set_mode"):
        assert not methods[name].get("async")
    assert "platforms" not in methods["set_mode"]


def test_manifest_loads_without_requiring_the_microphone() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "audio"
    assert plugin.ios_entry == "AudioPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.audio.AudioPlugin"
    assert plugin.ios_sources and plugin.android_sources
    raw = json.loads((NATIVE / "pn_plugin.json").read_text())
    assert "requires" not in raw
    assert (NATIVE / "web" / "index.js").is_file()


def test_media3_version_matches_the_video_plugin() -> None:
    import pythonnative.video as video

    ours = json.loads((NATIVE / "pn_plugin.json").read_text())["android"]["dependencies"]
    theirs = json.loads((Path(video.__file__).parent / "native" / "pn_plugin.json").read_text())["android"][
        "dependencies"
    ]
    versions = {dep.rsplit(":", 1)[1] for dep in [*ours, *theirs] if dep.startswith("androidx.media3:")}
    assert len(versions) == 1


def test_generated_contract_matches_the_declarations() -> None:
    written = json.loads((NATIVE / "schema.json").read_text())
    assert written["components"] == {}
    assert list(written["modules"]) == ["Audio"]
    assert set(written["modules"]["Audio"]["methods"]) == set(schema.MODULES["Audio"].methods)
