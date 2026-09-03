"""Native plugin discovery and staging (``pn build`` side of the plugin system)."""

import json
from pathlib import Path
from typing import List

import pytest

from pythonnative.project import builder as builder_mod
from pythonnative.project import plugins as plugins_mod
from pythonnative.project import runtime_assets
from pythonnative.project.builder import Builder, BuildError
from pythonnative.project.config import AppConfig
from pythonnative.project.plugins import (
    PluginError,
    discover_plugins,
    load_plugin,
    stage_android_plugins,
    stage_ios_plugins,
)


def _write_plugin(root: Path, *, ios: bool = True, android: bool = True, name: str = "blur") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if ios:
        manifest["ios"] = {"entry": "BlurPlugin"}
        (root / "ios").mkdir(exist_ok=True)
        (root / "ios" / "BlurPlugin.swift").write_text(
            "import PythonNativeKit\npublic enum BlurPlugin: PNPlugin {\n"
            "    public static func register(into registry: PNRegistry) {}\n}\n",
            encoding="utf-8",
        )
    if android:
        manifest["android"] = {"entry": "com.example.blur.BlurPlugin"}
        pkg = root / "android" / "com" / "example" / "blur"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "BlurPlugin.kt").write_text(
            "package com.example.blur\n"
            "import com.pythonnative.runtime.bridge.PNPlugin\n"
            "import com.pythonnative.runtime.bridge.PNRegistry\n"
            "object BlurPlugin : PNPlugin { override fun register(registry: PNRegistry) {} }\n",
            encoding="utf-8",
        )
    (root / "pn_plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


# ----------------------------------------------------------------------
# Manifest parsing
# ----------------------------------------------------------------------


def test_load_plugin_reads_manifest_and_sources(tmp_path: Path) -> None:
    plugin = load_plugin(_write_plugin(tmp_path / "blur"))
    assert plugin.name == "blur"
    assert plugin.ios_entry == "BlurPlugin"
    assert plugin.android_entry == "com.example.blur.BlurPlugin"
    assert [p.as_posix() for p in plugin.ios_sources] == ["ios/BlurPlugin.swift"]
    assert [p.as_posix() for p in plugin.android_sources] == ["android/com/example/blur/BlurPlugin.kt"]


def test_load_plugin_single_platform(tmp_path: Path) -> None:
    plugin = load_plugin(_write_plugin(tmp_path / "ios_only", android=False))
    assert plugin.has_ios and not plugin.has_android


def test_load_plugin_rejects_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(PluginError, match="pn_plugin.json"):
        load_plugin(tmp_path)


def test_load_plugin_rejects_entry_without_sources(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    (root / "pn_plugin.json").write_text(json.dumps({"ios": {"entry": "Nope"}}), encoding="utf-8")
    with pytest.raises(PluginError, match="no .swift files"):
        load_plugin(root)


def test_load_plugin_rejects_bad_entry_names(tmp_path: Path) -> None:
    root = _write_plugin(tmp_path / "bad")
    (root / "pn_plugin.json").write_text(json.dumps({"ios": {"entry": "Not A Type"}}), encoding="utf-8")
    with pytest.raises(PluginError, match="Swift type name"):
        load_plugin(root)
    (root / "pn_plugin.json").write_text(json.dumps({"android": {"entry": "NoPackage"}}), encoding="utf-8")
    with pytest.raises(PluginError, match="fully qualified"):
        load_plugin(root)


def test_load_plugin_rejects_no_platforms(tmp_path: Path) -> None:
    root = tmp_path / "none"
    root.mkdir()
    (root / "pn_plugin.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PluginError, match="neither"):
        load_plugin(root)


# ----------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------


def test_discover_plugins_merges_entry_points_and_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ep_root = _write_plugin(tmp_path / "from_ep", android=False)
    local_root = _write_plugin(tmp_path / "local", ios=False)
    monkeypatch.setattr(plugins_mod, "_entry_points", lambda: {"ep_blur": "some.module"})
    monkeypatch.setattr(plugins_mod, "_resolve_entry_point", lambda target: ep_root)

    found = discover_plugins(extra_paths=[local_root])
    assert [p.name for p in found] == ["ep_blur", "local"]


def test_discover_plugins_skips_broken_entry_points(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugins_mod, "_entry_points", lambda: {"broken": "nope.module"})

    def _boom(target: str) -> Path:
        raise ImportError("no module named nope")

    monkeypatch.setattr(plugins_mod, "_resolve_entry_point", _boom)
    messages: List[str] = []
    assert discover_plugins(log=messages.append) == []
    assert any("broken" in m for m in messages)


def test_discover_plugins_rejects_duplicate_local_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write_plugin(tmp_path / "blur")
    monkeypatch.setattr(plugins_mod, "_entry_points", lambda: {})
    with pytest.raises(PluginError, match="twice"):
        discover_plugins(extra_paths=[root, root])


# ----------------------------------------------------------------------
# Staging
# ----------------------------------------------------------------------


def _fake_ios_project(root: Path) -> Path:
    plugins_dir = root / "PythonNativeKit" / "Sources" / "PythonNativeKit" / "Plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "PNPluginRegistration.swift").write_text("stale", encoding="utf-8")
    (plugins_dir / "old_plugin").mkdir()
    (plugins_dir / "old_plugin" / "Old.swift").write_text("stale", encoding="utf-8")
    return root


def test_stage_ios_plugins_copies_sources_and_generates_registration(tmp_path: Path) -> None:
    project = _fake_ios_project(tmp_path / "ios_template")
    plugin = load_plugin(_write_plugin(tmp_path / "blur"))

    stage_ios_plugins(project, [plugin])

    plugins_dir = project / "PythonNativeKit" / "Sources" / "PythonNativeKit" / "Plugins"
    assert (plugins_dir / "blur" / "BlurPlugin.swift").is_file()
    assert not (plugins_dir / "old_plugin").exists(), "stale plugin folders are removed"
    registration = (plugins_dir / "PNPluginRegistration.swift").read_text(encoding="utf-8")
    assert "BlurPlugin.register(into: registry)" in registration
    assert "public enum PNGeneratedPlugins" in registration


def test_stage_ios_plugins_without_plugins_writes_empty_hook(tmp_path: Path) -> None:
    project = _fake_ios_project(tmp_path / "ios_template")
    stage_ios_plugins(project, [])
    registration = (
        project / "PythonNativeKit" / "Sources" / "PythonNativeKit" / "Plugins" / "PNPluginRegistration.swift"
    )
    assert "registerAll(into registry: PNRegistry) {}" in registration.read_text(encoding="utf-8")


def test_stage_android_plugins_preserves_package_layout(tmp_path: Path) -> None:
    project = tmp_path / "android_template"
    plugin = load_plugin(_write_plugin(tmp_path / "blur"))

    stage_android_plugins(project, [plugin])

    java = project / "pythonnative" / "src" / "main" / "java"
    assert (java / "com" / "example" / "blur" / "BlurPlugin.kt").is_file()
    registration = (java / "com" / "pythonnative" / "runtime" / "plugins" / "GeneratedPlugins.kt").read_text(
        encoding="utf-8"
    )
    assert "com.example.blur.BlurPlugin.register(registry)" in registration
    assert "object GeneratedPlugins" in registration


def test_stage_android_plugins_without_plugins_writes_empty_hook(tmp_path: Path) -> None:
    project = tmp_path / "android_template"
    stage_android_plugins(project, [])
    registration = (
        project / "pythonnative" / "src" / "main" / "java" / "com" / "pythonnative" / "runtime" / "plugins"
    ) / "GeneratedPlugins.kt"
    assert "fun registerAll(registry: PNRegistry) {}" in registration.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Builder integration
# ----------------------------------------------------------------------

_TOML = """
[app]
id = "com.acme.cool"
name = "cool"
python_version = "3.13"
[plugins]
paths = ["native/blur"]
"""


def _project(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("import pythonnative as pn\n", encoding="utf-8")
    (tmp_path / "pythonnative.toml").write_text(_TOML, encoding="utf-8")
    _write_plugin(tmp_path / "native" / "blur")
    return tmp_path


def test_builder_bundles_local_plugins_into_android(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugins_mod, "_entry_points", lambda: {})
    cfg = AppConfig.load(_project(tmp_path))
    assert cfg.plugin_paths == ["native/blur"]

    prepared = Builder(cfg, log=lambda _m: None).prepare("android")

    java = prepared.project_dir / "pythonnative" / "src" / "main" / "java"
    assert (java / "com" / "example" / "blur" / "BlurPlugin.kt").is_file()
    generated = java / "com" / "pythonnative" / "runtime" / "plugins" / "GeneratedPlugins.kt"
    assert "com.example.blur.BlurPlugin.register(registry)" in generated.read_text(encoding="utf-8")
    # The staged template never carries build outputs from a dev checkout.
    assert not (prepared.project_dir / "pythonnative" / "build").exists()
    assert not (prepared.project_dir / ".gradle").exists()


def test_builder_bundles_local_plugins_into_ios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugins_mod, "_entry_points", lambda: {})
    xcframework = tmp_path / "fake_runtime" / "Python.xcframework"
    (xcframework / "build").mkdir(parents=True)
    runtime = runtime_assets.IOSRuntime(python_version="3.13", xcframework_dir=xcframework)
    monkeypatch.setattr(builder_mod.runtime_assets, "prepare_ios_runtime", lambda *a, **k: runtime)
    cfg = AppConfig.load(_project(tmp_path))

    prepared = Builder(cfg, log=lambda _m: None).prepare("ios")

    plugins_dir = prepared.project_dir / "PythonNativeKit" / "Sources" / "PythonNativeKit" / "Plugins"
    assert (plugins_dir / "blur" / "BlurPlugin.swift").is_file()
    assert "BlurPlugin.register(into: registry)" in (plugins_dir / "PNPluginRegistration.swift").read_text(
        encoding="utf-8"
    )
    assert not (prepared.project_dir / "PythonNativeKit" / ".build").exists()


def test_builder_reports_invalid_local_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plugins_mod, "_entry_points", lambda: {})
    root = _project(tmp_path)
    (root / "native" / "blur" / "pn_plugin.json").unlink()
    cfg = AppConfig.load(root)
    with pytest.raises(BuildError, match="Invalid native plugin"):
        Builder(cfg, log=lambda _m: None).prepare("android")
