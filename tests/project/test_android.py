from pathlib import Path

import pytest

from pythonnative.project import android
from pythonnative.project.config import AppConfig

TEMPLATE_PKG = "com.pythonnative.android_template"

_BUILD_GRADLE = """plugins { id 'com.android.application' }
android {
    namespace 'com.pythonnative.android_template'
    compileSdk 34
    defaultConfig {
        applicationId "com.pythonnative.android_template"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "1.0"
        ndk {
            abiFilters "armeabi-v7a", "arm64-v8a", "x86", "x86_64"
        }
        python {
            version "3.11"
            pip { install "-r", "requirements.txt" }
        }
    }
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
}
dependencies {
    implementation 'androidx.core:core-ktx:1.8.0'
}
"""

_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    <application
        android:label="@string/app_name"
        android:theme="@style/Theme.Android_template"
        tools:targetApi="31">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

_STRINGS = '<resources>\n    <string name="app_name">android_template</string>\n</resources>\n'

_NAV_GRAPH = (
    '<navigation>\n    <fragment android:name="com.pythonnative.android_template.ScreenFragment" />\n</navigation>\n'
)

_MAIN_ACTIVITY = "package com.pythonnative.android_template\n\nclass MainActivity\n"


@pytest.fixture
def template(tmp_path: Path) -> Path:
    root = tmp_path / "android_template"
    app = root / "app"
    (app / "src" / "main").mkdir(parents=True)
    (app / "build.gradle").write_text(_BUILD_GRADLE, encoding="utf-8")
    (app / "src" / "main" / "AndroidManifest.xml").write_text(_MANIFEST, encoding="utf-8")
    (app / "src" / "main" / "res" / "values").mkdir(parents=True)
    (app / "src" / "main" / "res" / "values" / "strings.xml").write_text(_STRINGS, encoding="utf-8")
    (app / "src" / "main" / "res" / "navigation").mkdir(parents=True)
    (app / "src" / "main" / "res" / "navigation" / "nav_graph.xml").write_text(_NAV_GRAPH, encoding="utf-8")
    pkg_dir = app / "src" / "main" / "java" / "com" / "pythonnative" / "android_template"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "MainActivity.kt").write_text(_MAIN_ACTIVITY, encoding="utf-8")
    (root / "settings.gradle").write_text('rootProject.name = "android_template"\n', encoding="utf-8")
    return root


def _config(tmp_path: Path, **overrides: object) -> AppConfig:
    app = {"id": "com.acme.cool", "name": "cool", "display_name": "Cool & Co"}
    data: dict = {"app": app}
    data.update(overrides)
    cfg = AppConfig.from_dict(data, project_root=tmp_path)
    return cfg


def test_relocate_moves_and_rewrites(template: Path) -> None:
    android.relocate_package(template, TEMPLATE_PKG, "com.acme.cool")
    old_dir = template / "app" / "src" / "main" / "java" / "com" / "pythonnative" / "android_template"
    new_dir = template / "app" / "src" / "main" / "java" / "com" / "acme" / "cool"
    assert not old_dir.exists()
    assert (new_dir / "MainActivity.kt").read_text().startswith("package com.acme.cool")
    assert TEMPLATE_PKG not in (template / "app" / "build.gradle").read_text()
    assert (
        "com.acme.cool.ScreenFragment"
        in (template / "app" / "src" / "main" / "res" / "navigation" / "nav_graph.xml").read_text()
    )
    # The empty old package tree is pruned up to (but not including) the source root.
    assert not (template / "app" / "src" / "main" / "java" / "com" / "pythonnative").exists()


def test_relocate_noop_when_same(template: Path) -> None:
    android.relocate_package(template, TEMPLATE_PKG, TEMPLATE_PKG)
    assert (
        template / "app" / "src" / "main" / "java" / "com" / "pythonnative" / "android_template" / "MainActivity.kt"
    ).is_file()


def test_configure_gradle_writes_identity(template: Path, tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        app={"id": "com.acme.cool", "name": "cool", "version": "3.1.4", "build": 42, "python_version": "3.12"},
        android={"min_sdk": 26, "target_sdk": 33, "compile_sdk": 35, "abi_filters": ["arm64-v8a"]},
    )
    android.configure_gradle(template, cfg)
    text = (template / "app" / "build.gradle").read_text()
    assert "versionCode 42" in text
    assert 'versionName "3.1.4"' in text
    assert "minSdk 26" in text
    assert "targetSdk 33" in text
    assert "compileSdk 35" in text
    assert 'version "3.12"' in text
    assert 'abiFilters "arm64-v8a"' in text
    assert "signingConfigs" not in text  # no signing configured


def test_configure_gradle_injects_signing(template: Path, tmp_path: Path) -> None:
    cfg = _config(tmp_path, android={"signing": {"keystore": "rel.keystore", "key_alias": "cool"}})
    android.configure_gradle(template, cfg)
    text = (template / "app" / "build.gradle").read_text()
    assert "signingConfigs {" in text
    assert "signingConfig signingConfigs.release" in text
    assert "rel.keystore" in text
    assert 'System.getenv("PN_ANDROID_KEYSTORE_PASSWORD")' in text


def test_configure_manifest_permissions_and_orientation(template: Path, tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        app={"id": "com.acme.cool", "name": "cool", "orientation": "landscape"},
        permissions={"camera": True, "notifications": True},
    )
    android.configure_manifest(template, cfg)
    text = (template / "app" / "src" / "main" / "AndroidManifest.xml").read_text()
    assert '<uses-permission android:name="android.permission.CAMERA" />' in text
    assert '<uses-permission android:name="android.permission.INTERNET" />' in text
    assert 'android:screenOrientation="sensorLandscape"' in text


def test_configure_manifest_all_orientation_unset(template: Path, tmp_path: Path) -> None:
    cfg = _config(tmp_path, app={"id": "com.acme.cool", "name": "cool", "orientation": "all"})
    android.configure_manifest(template, cfg)
    text = (template / "app" / "src" / "main" / "AndroidManifest.xml").read_text()
    assert "screenOrientation" not in text


def test_configure_strings_escapes(template: Path, tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    android.configure_strings(template, cfg)
    text = (template / "app" / "src" / "main" / "res" / "values" / "strings.xml").read_text()
    assert "Cool &amp; Co" in text


def test_configure_settings_gradle(template: Path, tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    android.configure_settings_gradle(template, cfg)
    assert 'rootProject.name = "cool"' in (template / "settings.gradle").read_text()


def test_write_requirements(template: Path, tmp_path: Path) -> None:
    cfg = _config(tmp_path, requirements={"packages": ["httpx", "humanize"]})
    android.write_requirements(template, cfg)
    text = (template / "app" / "requirements.txt").read_text()
    assert text == "httpx\nhumanize\n"


def test_write_requirements_empty(template: Path, tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    android.write_requirements(template, cfg)
    assert (template / "app" / "requirements.txt").read_text() == ""
