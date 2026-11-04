"""``pythonnative.camera``: the facade, the handle, events, the contract, and the plugin manifest."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, List

import pytest

import pythonnative as pn
import pythonnative.camera as camera
from pythonnative.camera import Barcode, Camera, CameraError, CameraView, CameraViewHandle, Photo, VideoRecording
from pythonnative.native_modules.registry import native_module
from pythonnative.project import plugin_config
from pythonnative.project.config import AppConfig
from pythonnative.project.plugins import PluginError, load_plugin
from pythonnative.sdk import schema
from pythonnative.testing import render

NATIVE = Path(camera.__file__).parent / "native"


def _config(**permissions: Any) -> AppConfig:
    config = AppConfig.__new__(AppConfig)
    object.__setattr__(config, "permissions", permissions)
    object.__setattr__(config, "plugin_options", {})
    return config


def test_take_photo_falls_back_to_a_cancel_off_device() -> None:
    assert asyncio.run(Camera.take_photo()) is None


def test_take_photo_rejects_a_quality_out_of_range() -> None:
    with pytest.raises(ValueError, match="quality"):
        asyncio.run(Camera.take_photo(quality=1.5))


def test_camera_view_sends_its_props() -> None:
    result = render(
        CameraView(facing="front", flash="torch", zoom=2.0, barcode_types=["qr", "ean13"], style=pn.style(height=200))
    )
    view = result.get_by_type("CameraView")
    assert view.props["facing"] == "front"
    assert view.props["flash"] == "torch"
    assert view.props["zoom"] == 2.0
    assert view.props["barcode_types"] == ["qr", "ean13"]


def test_camera_view_defaults_mean_the_back_lens_and_no_scanning() -> None:
    props = camera.CameraViewProps()
    assert (props.facing, props.flash, props.zoom, props.barcode_types) == ("back", "off", 1.0, None)


@pytest.mark.parametrize("bad", [{"facing": "side"}, {"flash": "strobe"}, {"barcode_types": ["morse"]}])
def test_invalid_props_are_rejected(bad: Any) -> None:
    with pytest.raises(Exception, match=next(iter(bad))):
        render(CameraView(**bad))


def test_events_arrive_as_records() -> None:
    barcodes: List[Barcode] = []
    errors: List[CameraError] = []
    ready: List[bool] = []
    result = render(CameraView(on_barcode=barcodes.append, on_error=errors.append, on_ready=lambda: ready.append(True)))
    view = result.get_by_type("CameraView")
    result.fire(view, "on_ready")
    result.fire(view, "on_barcode", {"type": "qr", "data": "hello"})
    result.fire(view, "on_error", {"code": "unavailable", "message": "no camera"})
    assert ready == [True]
    assert barcodes == [Barcode(type="qr", data="hello")]
    assert errors == [CameraError(code="unavailable", message="no camera")]


def test_children_draw_on_top_of_the_preview() -> None:
    result = render(CameraView(pn.Text("Align the code")))
    assert result.get_by_text("Align the code") is not None


def test_ref_publishes_the_typed_handle() -> None:
    ref: pn.Ref[Any] = pn.Ref()
    result = render(CameraView(ref=ref))
    handle = ref.current
    assert isinstance(handle, CameraViewHandle)
    assert handle.tag == result.get_by_type("CameraView").tag


def test_handle_runs_against_the_fallback() -> None:
    ref: pn.Ref[Any] = pn.Ref()
    render(CameraView(ref=ref))
    handle = ref.current

    async def capture() -> Any:
        photo = await handle.take_picture(quality=0.5)
        await handle.start_recording()
        recording = await handle.stop_recording()
        return photo, recording

    assert asyncio.run(capture()) == (Photo(path="", width=0, height=0), VideoRecording(path="", duration=0.0))


def test_handle_validates_quality_before_the_bridge() -> None:
    ref: pn.Ref[Any] = pn.Ref()
    render(CameraView(ref=ref))
    with pytest.raises(ValueError, match="quality"):
        asyncio.run(ref.current.take_picture(quality=-0.1))


def test_the_handle_addresses_the_module_by_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    ref: pn.Ref[Any] = pn.Ref()
    render(CameraView(ref=ref))
    handle = ref.current
    module = native_module("Camera")
    seen: List[Any] = []

    async def call_async(method: str, **kwargs: Any) -> Any:
        seen.append((method, kwargs))
        return None

    monkeypatch.setattr(module, "call_async", call_async)
    monkeypatch.setattr(camera, "native_module", lambda name: module)
    asyncio.run(handle.start_recording(audio=False))
    assert seen == [("start_recording", {"tag": handle.tag, "audio": False})]


def test_contract_declares_the_module_and_the_component() -> None:
    document = json.loads((NATIVE / "schema.json").read_text())
    assert set(document["modules"]) == {"Camera"}
    assert set(document["components"]) == {"CameraView"}
    methods = document["modules"]["Camera"]["methods"]
    assert set(methods) == {"take_photo", "take_picture", "start_recording", "stop_recording"}
    assert all(method["async"] for method in methods.values())
    assert document["components"]["CameraView"]["measurement"] == "container"


def test_module_is_declared_in_the_live_schema() -> None:
    assert "Camera" in schema.MODULES
    assert schema.MODULES["Camera"].methods["take_picture"]["required"] == ["tag"]


def test_plugin_loads_with_its_android_configuration() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "camera"
    assert plugin.requires_permissions == ("camera",)
    assert plugin.ios_entry == "CameraPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.camera.CameraPlugin"
    assert plugin.web_entry == "web/index.js"
    assert Path("android/res/xml/pn_camera_file_paths.xml") in plugin.android_resources
    assert any(item.startswith("androidx.camera:camera-video:") for item in plugin.maven_dependencies)


def test_dependencies_name_one_camerax_version() -> None:
    plugin = load_plugin(NATIVE)
    versions = {item.rsplit(":", 1)[1] for item in plugin.maven_dependencies if item.startswith("androidx.camera:")}
    assert len(versions) == 1


def test_a_missing_camera_permission_is_a_build_error() -> None:
    with pytest.raises(PluginError, match="camera"):
        plugin_config.check_requirements([load_plugin(NATIVE)], _config())
    plugin_config.check_requirements([load_plugin(NATIVE)], _config(camera="Scan receipts."))


def test_manifest_fragments_declare_the_provider_and_optional_hardware(tmp_path: Path) -> None:
    manifest = tmp_path / "app" / "src" / "main" / "AndroidManifest.xml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("<manifest>\n    <application>\n    </application>\n</manifest>\n", encoding="utf-8")
    plugin = load_plugin(NATIVE)
    plugin_config._apply_manifest(tmp_path, [plugin_config.ResolvedPlugin(plugin, {}, {}, plugin.manifest["android"])])
    content = manifest.read_text(encoding="utf-8")
    assert "${applicationId}.pythonnative.fileprovider" in content
    assert "@xml/pn_camera_file_paths" in content
    assert 'android:name="android.hardware.camera" android:required="false"' in content
    assert "android.media.action.IMAGE_CAPTURE" in content
