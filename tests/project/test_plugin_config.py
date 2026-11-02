"""Tests for the plugin manifest (v2), first-party plugins, and declarative configuration."""

from __future__ import annotations

import json
import plistlib
from pathlib import Path
from typing import Any, Dict

import pytest

from pythonnative.project import plugin_config, plugins
from pythonnative.project.builder import Builder, BuildError, _prune_wheel_payload
from pythonnative.project.config import AppConfig, ConfigError
from pythonnative.project.plugins import FIRST_PARTY_PLUGINS, PluginError, load_plugin


def make_plugin(root: Path, name: str = "demo", **manifest: Any) -> Path:
    """Write a plugin with one source per platform, and return its directory."""
    folder = root / name
    (folder / "ios").mkdir(parents=True)
    (folder / "ios" / "Demo.swift").write_text("// swift\n")
    (folder / "android").mkdir()
    (folder / "android" / "Demo.kt").write_text("// kotlin\n")
    document: Dict[str, Any] = {"name": name, "ios": {"entry": "DemoPlugin"}, "android": {"entry": "com.x.DemoPlugin"}}
    for key, value in manifest.items():
        if key in ("ios", "android"):
            document[key].update(value)
        else:
            document[key] = value
    (folder / "pn_plugin.json").write_text(json.dumps(document))
    return folder


def config_for(tmp_path: Path, **sections: Any) -> AppConfig:
    data: Dict[str, Any] = {"app": {"id": "com.example.demo", "name": "demo", "display_name": "Demo"}}
    data.update(sections)
    return AppConfig.from_dict(data, project_root=tmp_path)


def ios_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "ios_template").mkdir(parents=True)
    with open(project / "ios_template" / "Info.plist", "wb") as handle:
        plistlib.dump({"Existing": "value", "UIBackgroundModes": ["fetch"]}, handle)
    with open(project / "ios_template" / "PrivacyInfo.xcprivacy", "wb") as handle:
        plistlib.dump(
            {
                "NSPrivacyAccessedAPITypes": [
                    {"NSPrivacyAccessedAPIType": "UserDefaults", "NSPrivacyAccessedAPITypeReasons": ["CA92.1"]}
                ]
            },
            handle,
        )
    return project


def android_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "app" / "src" / "main").mkdir(parents=True)
    (project / "app" / "src" / "main" / "AndroidManifest.xml").write_text(
        '<manifest>\n    <uses-permission android:name="android.permission.INTERNET" />\n'
        "    <application>\n    </application>\n</manifest>\n"
    )
    (project / "build.gradle").write_text("plugins {\n    id 'a' version '1' apply false\n}\n")
    (project / "app" / "build.gradle").write_text("plugins {\n    id 'a'\n}\n")
    return project


def read_plist(path: Path) -> Dict[str, Any]:
    with open(path, "rb") as handle:
        result: Dict[str, Any] = plistlib.load(handle)
    return result


# ======================================================================
# Manifest
# ======================================================================


def test_name_is_required(tmp_path: Path) -> None:
    folder = make_plugin(tmp_path)
    document = json.loads((folder / "pn_plugin.json").read_text())
    del document["name"]
    (folder / "pn_plugin.json").write_text(json.dumps(document))
    with pytest.raises(PluginError, match="must declare a 'name'"):
        load_plugin(folder)


@pytest.mark.parametrize(
    "manifest, match",
    [
        ({"surprise": 1}, "unknown manifest key"),
        ({"ios": {"plist": {}}}, "unknown ios key"),
        ({"requires": {"packages": []}}, "'requires' may only"),
        ({"requires": {"plugins": "camera"}}, "must be a list"),
        ({"options": {"key": {"type": "number"}}}, "needs a type"),
        ({"options": {"key": {"type": "string", "secret": True}}}, "unknown keys"),
        ({"android": {"when": {"missing": {}}}}, "unknown option"),
        ({"options": {"k": {"type": "string"}}, "android": {"when": {"k": {"entry": "x.Y"}}}}, "unknown android.when"),
        ({"web": {"path": "x"}}, "'web' must be"),
    ],
)
def test_invalid_manifests(tmp_path: Path, manifest: Dict[str, Any], match: str) -> None:
    with pytest.raises(PluginError, match=match):
        load_plugin(make_plugin(tmp_path, **manifest))


def test_v2_properties(tmp_path: Path) -> None:
    plugin = load_plugin(
        make_plugin(tmp_path, requires={"plugins": ["a"], "permissions": ["camera"]}, web={"entry": "web/index.js"})
    )
    assert plugin.requires_plugins == ("a",)
    assert plugin.requires_permissions == ("camera",)
    assert plugin.web_entry == "web/index.js"


def test_every_shipped_first_party_plugin_loads() -> None:
    package = Path(plugins.__file__).resolve().parents[1]
    for name in FIRST_PARTY_PLUGINS:
        if (package / name / "native" / plugins.MANIFEST_NAME).is_file():
            assert plugins.first_party_plugins([name])[0].name == name


def test_unknown_capability(tmp_path: Path) -> None:
    with pytest.raises(PluginError, match="Unknown capability 'bluetooth'"):
        plugins.first_party_plugins(["bluetooth"])
    with pytest.raises(ConfigError, match="bluetooth"):
        config_for(tmp_path, plugins={"use": ["bluetooth"]})


def test_config_reads_use_paths_and_option_tables(tmp_path: Path) -> None:
    config = config_for(tmp_path, plugins={"use": ["camera"], "paths": ["native/x"], "maps": {"android_api_key": "k"}})
    assert config.plugin_use == ["camera"]
    assert config.plugin_paths == ["native/x"]
    assert config.plugin_options == {"maps": {"android_api_key": "k"}}
    with pytest.raises(ConfigError, match="must be a table"):
        config_for(tmp_path, plugins={"maps": 3})


# ======================================================================
# Options
# ======================================================================


def options_plugin(tmp_path: Path, **spec: Any) -> plugins.NativePlugin:
    return load_plugin(make_plugin(tmp_path, options={"key": spec}))


def test_option_sources_in_order(tmp_path: Path) -> None:
    plugin = options_plugin(tmp_path, type="string", default="default", env="DEMO_KEY")
    resolve = plugin_config.resolve_plugin
    assert resolve(plugin, config_for(tmp_path), environ={}).options["key"] == "default"
    assert resolve(plugin, config_for(tmp_path), environ={"DEMO_KEY": "env"}).options["key"] == "env"
    table = config_for(tmp_path, plugins={"demo": {"key": "table"}})
    assert resolve(plugin, table, environ={"DEMO_KEY": "env"}).options["key"] == "table"


def test_required_option_names_its_sources(tmp_path: Path) -> None:
    plugin = options_plugin(tmp_path, type="string", required=True, env="DEMO_KEY")
    with pytest.raises(PluginError, match=r"\[plugins.demo\].key or set DEMO_KEY"):
        plugin_config.resolve_plugin(plugin, config_for(tmp_path), environ={})


def test_unknown_and_mistyped_options(tmp_path: Path) -> None:
    plugin = options_plugin(tmp_path, type="integer")
    with pytest.raises(PluginError, match="unknown option"):
        plugin_config.resolve_plugin(plugin, config_for(tmp_path, plugins={"demo": {"other": 1}}), environ={})
    with pytest.raises(PluginError, match="must be a integer"):
        plugin_config.resolve_plugin(plugin, config_for(tmp_path, plugins={"demo": {"key": "x"}}), environ={})
    assert plugin_config.resolve_plugin(plugin, config_for(tmp_path), environ={"X": "1"}).options["key"] is None


def test_path_options_resolve_and_must_exist(tmp_path: Path) -> None:
    plugin = options_plugin(tmp_path, type="path")
    with pytest.raises(PluginError, match="doesn't exist"):
        plugin_config.resolve_plugin(plugin, config_for(tmp_path, plugins={"demo": {"key": "a.json"}}), environ={})
    (tmp_path / "a.json").write_text("{}")
    resolved = plugin_config.resolve_plugin(
        plugin, config_for(tmp_path, plugins={"demo": {"key": "a.json"}}), environ={}
    )
    assert resolved.options["key"] == str(tmp_path / "a.json")


def test_substitution_keeps_types_and_rejects_unknown_names(tmp_path: Path) -> None:
    plugin = load_plugin(
        make_plugin(
            tmp_path,
            options={"tasks": {"type": "list", "default": ["sync"]}, "name": {"type": "string", "default": "n"}},
            ios={"info_plist": {"Tasks": "${tasks}", "Label": "app-${name}-${app_id}"}},
        )
    )
    section = plugin_config.resolve_plugin(plugin, config_for(tmp_path), environ={}).ios["info_plist"]
    assert section == {"Tasks": ["sync"], "Label": "app-n-com.example.demo"}

    bad = load_plugin(make_plugin(tmp_path / "bad", ios={"info_plist": {"A": "${nope}"}}))
    with pytest.raises(PluginError, match="unknown option"):
        plugin_config.resolve_plugin(bad, config_for(tmp_path), environ={})


def test_when_applies_only_with_a_value(tmp_path: Path) -> None:
    plugin = load_plugin(
        make_plugin(
            tmp_path,
            options={"key": {"type": "string"}},
            android={"permissions": ["a"], "when": {"key": {"permissions": ["b"], "gradle_plugins": []}}},
        )
    )
    off = plugin_config.resolve_plugin(plugin, config_for(tmp_path), environ={}).android
    assert off["permissions"] == ["a"] and "gradle_plugins" not in off
    table = config_for(tmp_path, plugins={"demo": {"key": "x"}})
    on = plugin_config.resolve_plugin(plugin, table, environ={}).android
    assert on["permissions"] == ["a", "b"]


# ======================================================================
# Requirements
# ======================================================================


def test_requirements_name_what_to_add(tmp_path: Path) -> None:
    needs_permission = load_plugin(make_plugin(tmp_path / "a", requires={"permissions": ["camera"]}))
    with pytest.raises(PluginError, match="needs 'camera' declared under"):
        plugin_config.check_requirements([needs_permission], config_for(tmp_path))
    with pytest.raises(PluginError, match="needs 'camera'"):
        plugin_config.check_requirements([needs_permission], config_for(tmp_path, permissions={"camera": False}))
    plugin_config.check_requirements([needs_permission], config_for(tmp_path, permissions={"camera": "why"}))

    needs_plugin = load_plugin(make_plugin(tmp_path / "b", requires={"plugins": ["other"]}))
    with pytest.raises(PluginError, match="requires 'other'"):
        plugin_config.check_requirements([needs_plugin], config_for(tmp_path))


def test_option_table_for_an_absent_plugin(tmp_path: Path) -> None:
    with pytest.raises(PluginError, match="Add 'maps' to"):
        plugin_config.check_requirements([], config_for(tmp_path, plugins={"maps": {"k": 1}}))
    with pytest.raises(PluginError, match="isn't in this build"):
        plugin_config.check_requirements([], config_for(tmp_path, plugins={"other": {"k": 1}}))


# ======================================================================
# Merging
# ======================================================================


def test_merge_rules() -> None:
    owners: Dict[str, str] = {}
    target: Dict[str, Any] = {}
    plugin_config.merge(target, {"list": ["a"], "dict": {"x": 1}, "same": 1}, owner="p1", owners=owners)
    plugin_config.merge(target, {"list": ["a", "b"], "dict": {"y": 2}, "same": 1}, owner="p2", owners=owners)
    assert target == {"list": ["a", "b"], "dict": {"x": 1, "y": 2}, "same": 1}
    with pytest.raises(PluginError, match="Plugins 'p1' and 'p3' set dict.x"):
        plugin_config.merge(target, {"dict": {"x": 9}}, owner="p3", owners=owners)


def test_merge_copies_so_plugins_dont_share_lists() -> None:
    source = {"list": ["a"]}
    target: Dict[str, Any] = {}
    plugin_config.merge(target, source, owner="p", owners={})
    target["list"].append("b")
    assert source == {"list": ["a"]}


# ======================================================================
# Applying to iOS
# ======================================================================


def test_apply_ios_merges_plist_entitlements_and_privacy(tmp_path: Path) -> None:
    project = ios_project(tmp_path)
    plugin = load_plugin(
        make_plugin(
            tmp_path / "p",
            ios={
                "info_plist": {"UIBackgroundModes": ["fetch", "audio"], "Mine": "x", "Override": "plugin"},
                "entitlements": {"com.apple.ability": True},
                "privacy": {
                    "accessed_api_types": [
                        {"type": "UserDefaults", "reasons": ["CA92.1", "1C8F.1"]},
                        {"type": "DiskSpace", "reasons": ["E174.1"]},
                    ],
                    "collected_data_types": [{"NSPrivacyCollectedDataType": "x"}],
                    "tracking_domains": ["t.example.com"],
                },
            },
        )
    )
    config = config_for(tmp_path, ios={"extra_info_plist": {"Override": "app"}})
    plugin_config.apply_ios(project, config, [plugin])

    info = read_plist(project / "ios_template" / "Info.plist")
    assert info["Existing"] == "value"
    assert info["UIBackgroundModes"] == ["fetch", "audio"]
    assert info["Override"] == "app"
    entitlements = read_plist(project / "ios_template" / "ios_template.entitlements")
    assert entitlements == {"com.apple.ability": True}
    privacy = read_plist(project / "ios_template" / "PrivacyInfo.xcprivacy")
    types = {
        item["NSPrivacyAccessedAPIType"]: item["NSPrivacyAccessedAPITypeReasons"]
        for item in privacy["NSPrivacyAccessedAPITypes"]
    }
    assert types == {"UserDefaults": ["CA92.1", "1C8F.1"], "DiskSpace": ["E174.1"]}
    assert privacy["NSPrivacyTracking"] is True
    assert privacy["NSPrivacyTrackingDomains"] == ["t.example.com"]


def test_apply_ios_conflict_and_no_entitlements_file(tmp_path: Path) -> None:
    project = ios_project(tmp_path)
    one = load_plugin(make_plugin(tmp_path / "1", name="one", ios={"info_plist": {"Key": "a"}}))
    two = load_plugin(make_plugin(tmp_path / "2", name="two", ios={"info_plist": {"Key": "b"}}))
    with pytest.raises(PluginError, match="'one' and 'two' set Key"):
        plugin_config.apply_ios(project, config_for(tmp_path), [one, two])
    plugin_config.apply_ios(project, config_for(tmp_path), [one])
    assert not (project / "ios_template" / "ios_template.entitlements").exists()


# ======================================================================
# Applying to Android
# ======================================================================


def test_apply_android_manifest_gradle_and_files(tmp_path: Path) -> None:
    project = android_project(tmp_path)
    (tmp_path / "services.json").write_text("{}")
    folder = make_plugin(
        tmp_path / "p",
        options={"services": {"type": "path"}, "channel": {"type": "string", "default": "news"}},
        android={
            "permissions": ["android.permission.INTERNET", "android.permission.CAMERA"],
            "manifest": {"application": "android/application.xml", "root": "android/root.xml"},
            "when": {
                "services": {
                    "gradle_plugins": [{"id": "com.google.gms.google-services", "version": "4.4.2"}],
                    "files": [{"from": "${services}", "to": "app/google-services.json"}],
                }
            },
        },
    )
    (folder / "android" / "application.xml").write_text(
        '        <service android:name="x" android:authorities="${applicationId}.c" android:label="${channel}" />\n'
    )
    (folder / "android" / "root.xml").write_text('    <queries><package android:name="y" /></queries>\n')
    config = config_for(tmp_path, plugins={"demo": {"services": "services.json"}})
    plugin_config.apply_android(project, config, [load_plugin(folder)])

    manifest = (project / "app" / "src" / "main" / "AndroidManifest.xml").read_text()
    assert manifest.count("android.permission.INTERNET") == 1
    assert '<uses-permission android:name="android.permission.CAMERA" />' in manifest
    assert manifest.index("<queries>") < manifest.index("<application>")
    assert '${applicationId}.c" android:label="news"' in manifest
    assert manifest.index("<service") > manifest.index("<application>")
    assert "id 'com.google.gms.google-services' version '4.4.2' apply false" in (project / "build.gradle").read_text()
    assert "    id 'com.google.gms.google-services'\n" in (project / "app" / "build.gradle").read_text()
    assert (project / "app" / "google-services.json").read_text() == "{}"


def test_android_conflicting_gradle_plugins_and_escaping_paths(tmp_path: Path) -> None:
    project = android_project(tmp_path)
    one = load_plugin(
        make_plugin(tmp_path / "1", name="one", android={"gradle_plugins": [{"id": "p", "version": "1"}]})
    )
    two = load_plugin(
        make_plugin(tmp_path / "2", name="two", android={"gradle_plugins": [{"id": "p", "version": "2"}]})
    )
    with pytest.raises(PluginError, match="Conflicting versions"):
        plugin_config.apply_android(project, config_for(tmp_path), [one, two])

    folder = make_plugin(
        tmp_path / "3", name="three", android={"files": [{"from": "android/Demo.kt", "to": "../../evil"}]}
    )
    with pytest.raises(PluginError, match="escapes the project"):
        plugin_config.apply_android(project, config_for(tmp_path), [load_plugin(folder)])

    fragment = make_plugin(tmp_path / "4", name="four", android={"manifest": {"root": "../outside.xml"}})
    with pytest.raises(PluginError, match="must be a file inside"):
        plugin_config.apply_android(project, config_for(tmp_path), [load_plugin(fragment)])


# ======================================================================
# Native targets
# ======================================================================


def test_c_and_xcframework_targets_reach_package_swift(tmp_path: Path) -> None:
    package = tmp_path / "project" / "PythonNativeKit"
    (package / "Sources" / "PythonNativeKit" / "Plugins").mkdir(parents=True)
    (package / "Package.swift").write_text(
        "// pn:packages\n// pn:end-packages\n// pn:targets\n// pn:end-targets\n"
        '// pn:products\n// pn:end-products\n.process("Resources")\n'
    )
    folder = make_plugin(
        tmp_path,
        ios={
            "c_target": {"sources": "ios/c", "public_headers": "ios/c/include"},
            "binary_targets": ["ios/Foo.xcframework"],
        },
    )
    (folder / "ios" / "c" / "include").mkdir(parents=True)
    (folder / "ios" / "c" / "include" / "demo.h").write_text("int demo(void);\n")
    (folder / "ios" / "c" / "demo.c").write_text("int demo(void) { return 1; }\n")
    (folder / "ios" / "Foo.xcframework" / "ios").mkdir(parents=True)
    (folder / "ios" / "Foo.xcframework" / "ios" / "Vendored.swift").write_text("// not plugin source\n")

    plugin = load_plugin(folder)
    assert [str(path) for path in plugin.ios_sources] == ["ios/Demo.swift"]
    plugins.stage_ios_plugins(tmp_path / "project", [plugin])

    contents = (package / "Package.swift").read_text()
    assert '.binaryTarget(name: "Foo", path: "PluginBinaries/demo/Foo.xcframework")' in contents
    assert '.target(name: "PNC_demo", path: "PluginC/demo", publicHeadersPath: "include")' in contents
    assert '"PNC_demo",' in contents and '"Foo",' in contents
    assert (package / "PluginC" / "demo" / "demo.c").is_file()
    assert (package / "PluginBinaries" / "demo" / "Foo.xcframework").is_dir()


def test_cmake_plugins_generate_an_include(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "pythonnative" / "src" / "main" / "cpp").mkdir(parents=True)
    folder = make_plugin(tmp_path, android={"cmake": "android/cpp/CMakeLists.txt"})
    (folder / "android" / "cpp").mkdir()
    (folder / "android" / "cpp" / "CMakeLists.txt").write_text("add_library(demo SHARED demo.c)\n")
    (folder / "android" / "cpp" / "demo.c").write_text("int demo(void) { return 1; }\n")

    plugins.stage_android_plugins(project, [load_plugin(folder)])
    root = project / "pythonnative" / "src" / "main" / "cpp"
    assert "add_subdirectory(plugins/demo" in (root / "plugins.cmake").read_text()
    assert (root / "plugins" / "demo" / "demo.c").is_file()

    plugins.stage_android_plugins(project, [])
    assert "add_subdirectory(" not in (root / "plugins.cmake").read_text()
    assert not (root / "plugins" / "demo").exists()


# ======================================================================
# Builder
# ======================================================================


def test_builder_collects_first_party_and_rejects_duplicates(tmp_path: Path) -> None:
    (tmp_path / "local").mkdir()
    folder = make_plugin(tmp_path / "local", name="location")
    config = config_for(
        tmp_path,
        plugins={"use": ["location"], "paths": [str(folder.relative_to(tmp_path))]},
        permissions={"location_when_in_use": "why"},
    )
    with pytest.raises(BuildError, match="Two native plugins are named 'location'"):
        Builder(config, log=lambda _: None)._discover_plugins()


def test_release_pruning_removes_scripts_and_tests(tmp_path: Path) -> None:
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "f2py").write_text("#!/build/machine/python\n")
    keep = tmp_path / "numpy" / "testing"
    keep.mkdir(parents=True)
    (tmp_path / "numpy" / "tests").mkdir()
    (tmp_path / "numpy" / "core" / "tests" / "data").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    _prune_wheel_payload(tmp_path)
    assert not (tmp_path / "bin").exists()
    assert keep.is_dir()
    assert not (tmp_path / "numpy" / "tests").exists()
    assert not (tmp_path / "numpy" / "core" / "tests").exists()
    # A top-level package named `tests` could be the app's own dependency.
    assert (tmp_path / "tests").is_dir()
