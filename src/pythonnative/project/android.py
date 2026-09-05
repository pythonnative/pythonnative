"""Config-driven Android project configurator.

Turns the bundled ``android_template`` into a concrete, buildable Gradle
project for a specific [`AppConfig`][pythonnative.project.config.AppConfig]:

- **Package relocation.** The template lives under
  ``com.pythonnative.android_template``; this module rewrites and moves
  it to the app's own ``application_id`` so each app ships a distinct
  package. The PythonNative Android runtime resolves its helper classes
  (``Navigator``) via ``getPackageName()``, so the relocation needs no
  runtime configuration.
- **Identity & SDKs.** ``applicationId``, ``versionCode``/``versionName``,
  ``minSdk``/``targetSdk``/``compileSdk``, ABI filters, and the embedded
  CPython version are written into ``app/build.gradle``.
- **Permissions.** ``<uses-permission>`` entries (derived from
  ``[permissions]``) and the launch orientation are written into
  ``AndroidManifest.xml``.
- **Signing.** A release ``signingConfig`` is injected when a keystore is
  configured (passwords are read from the environment at build time).
- **Branding.** Launcher icons and an Android 12+ splash screen are
  generated from the configured assets.
- **Python sources.** The user's ``app/`` and (in a dev checkout) the
  in-repo ``pythonnative`` package are staged into Chaquopy's source set,
  and ``requirements.txt`` is generated from ``[requirements].packages``.

Everything here is plain file manipulation, which keeps it fully unit
testable without an Android toolchain.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from . import icons
from .config import AppConfig

TEMPLATE_PACKAGE = "com.pythonnative.android_template"
"""The fixed package the bundled Android template ships under."""

TEXT_SUFFIXES = {".kt", ".java", ".gradle", ".xml", ".pro", ".properties", ".cfg"}

_SOURCE_ROOTS = (
    ("app", "src", "main", "java"),
    ("app", "src", "test", "java"),
    ("app", "src", "androidTest", "java"),
)

Logger = Callable[[str], None]


@dataclass
class AndroidLayout:
    """Resolved paths within a configured Android project.

    Attributes:
        project_dir: The Gradle project root (``.../android_template``).
        application_id: The final Android application id.
        python_root: Chaquopy Python source root
            (``app/src/main/python``).
    """

    project_dir: Path
    application_id: str
    python_root: Path


def configure(
    project_dir: Path,
    config: AppConfig,
    *,
    dev_lib_root: Optional[Path] = None,
    release: bool = False,
    log: Optional[Logger] = None,
) -> AndroidLayout:
    """Fully configure a staged Android template for ``config``.

    Args:
        project_dir: The staged ``android_template`` directory.
        config: The validated app configuration.
        dev_lib_root: Path to an in-repo ``pythonnative`` package to
            bundle (dev checkout); ``None`` to rely on the PyPI install.
        release: Ship bytecode only (Chaquopy ``pyc.src``). Debug builds
            keep the ``.py`` sources in the APK so tracebacks show code
            and the dev client can tell what the app already runs.
        log: Optional progress logger.

    Returns:
        An [`AndroidLayout`][pythonnative.project.android.AndroidLayout]
        describing the configured project.
    """
    emit: Logger = log or (lambda _message: None)
    project_dir = Path(project_dir)

    relocate_package(project_dir, TEMPLATE_PACKAGE, config.application_id)
    configure_gradle(project_dir, config, release=release)
    configure_settings_gradle(project_dir, config)
    configure_strings(project_dir, config)
    configure_manifest(project_dir, config)
    write_requirements(project_dir, config)

    _apply_branding(project_dir, config, emit)

    python_root = stage_python_sources(project_dir, config, dev_lib_root=dev_lib_root)
    emit(f"Configured Android project ({config.application_id}).")
    return AndroidLayout(project_dir=project_dir, application_id=config.application_id, python_root=python_root)


# ======================================================================
# Package relocation
# ======================================================================


def relocate_package(project_dir: Path, old_package: str, new_package: str) -> None:
    """Rewrite and move the template's Java/Kotlin package.

    Replaces every occurrence of ``old_package`` with ``new_package`` in
    all text sources, then moves the source directories from the old
    package path to the new one. A no-op when the packages are equal.

    Args:
        project_dir: The staged Android project root.
        old_package: The dotted package currently in the template.
        new_package: The desired dotted package (the app's id).
    """
    if old_package == new_package:
        return

    _replace_in_tree(project_dir, old_package, new_package)

    old_rel = old_package.replace(".", os.sep)
    new_rel = new_package.replace(".", os.sep)
    for parts in _SOURCE_ROOTS:
        source_root = project_dir.joinpath(*parts)
        old_dir = source_root / old_rel
        if not old_dir.is_dir():
            continue
        new_dir = source_root / new_rel
        new_dir.mkdir(parents=True, exist_ok=True)
        for entry in old_dir.iterdir():
            shutil.move(str(entry), str(new_dir / entry.name))
        _prune_empty_dirs(source_root, old_rel)


def _replace_in_tree(root: Path, needle: str, replacement: str) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if needle in text:
            path.write_text(text.replace(needle, replacement), encoding="utf-8")


def _prune_empty_dirs(source_root: Path, relative: str) -> None:
    current = source_root / relative
    while current != source_root and current.is_dir() and not any(current.iterdir()):
        current.rmdir()
        current = current.parent


# ======================================================================
# Gradle / manifest / resources
# ======================================================================


def configure_gradle(project_dir: Path, config: AppConfig, *, release: bool = False) -> None:
    """Write identity, SDK levels, ABIs, Python version, bytecode policy, and signing.

    Args:
        project_dir: The staged Android project root.
        config: The validated app configuration.
        release: Compile app sources to bytecode and drop the ``.py``
            files from the APK (Chaquopy's default). Debug builds keep
            them, for tracebacks with source lines and for the dev
            client's overlay seeding.
    """
    gradle_path = project_dir / "app" / "build.gradle"
    content = gradle_path.read_text(encoding="utf-8")

    content = re.sub(r"src\s+(true|false)", f"src {'true' if release else 'false'}", content, count=1)

    content = re.sub(r"versionCode\s+\d+", f"versionCode {config.build}", content)
    content = re.sub(r'versionName\s+"[^"]*"', f'versionName "{config.version}"', content)
    content = re.sub(r"minSdk\s+\d+", f"minSdk {config.android.min_sdk}", content)
    content = re.sub(r"targetSdk\s+\d+", f"targetSdk {config.android.target_sdk}", content)
    content = re.sub(r"compileSdk\s+\d+", f"compileSdk {config.android.compile_sdk}", content)
    content = re.sub(r'version\s+"3\.\d+"', f'version "{config.python_version}"', content)

    abi_csv = ", ".join(f'"{abi}"' for abi in config.android.abi_filters)
    content = re.sub(r"abiFilters[^\n]*", f"abiFilters {abi_csv}", content)

    if config.extra_index_urls:
        content = _inject_pip_options(content, config)

    if config.android.signing.is_configured:
        content = _inject_signing(content, config)

    gradle_path.write_text(content, encoding="utf-8")


def _inject_pip_options(content: str, config: AppConfig) -> str:
    """Add ``--extra-index-url`` pip options for ``[requirements].extra_index_urls``.

    Chaquopy runs pip at Gradle build time; ``options`` lines inside the
    ``pip { }`` block are passed straight through, so a private index
    declared once in ``pythonnative.toml`` applies to Android too.
    """
    marker = '                install "-r", "requirements.txt"'
    if marker not in content:
        return content
    lines = "".join(
        f'                options "--extra-index-url", "{_gradle_escape(url)}"\n' for url in config.extra_index_urls
    )
    return content.replace(marker, lines + marker, 1)


def _gradle_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _inject_signing(content: str, config: AppConfig) -> str:
    signing = config.android.signing
    assert signing.keystore is not None and signing.key_alias is not None
    keystore_path = config.resolve_path(signing.keystore).as_posix()
    block = (
        "    signingConfigs {\n"
        "        release {\n"
        f"            storeFile file('{keystore_path}')\n"
        f'            storePassword System.getenv("{signing.store_password_env}")\n'
        f"            keyAlias '{signing.key_alias}'\n"
        f'            keyPassword System.getenv("{signing.key_password_env}")\n'
        "        }\n"
        "    }\n"
    )
    if "signingConfigs {" not in content:
        content = content.replace("    buildTypes {", block + "    buildTypes {", 1)
    if "signingConfig signingConfigs.release" not in content:
        content = content.replace(
            "        release {\n            minifyEnabled false",
            "        release {\n            signingConfig signingConfigs.release\n            minifyEnabled false",
            1,
        )
    return content


def configure_settings_gradle(project_dir: Path, config: AppConfig) -> None:
    """Update ``rootProject.name`` to the configured project name.

    Args:
        project_dir: The staged Android project root.
        config: The validated app configuration.
    """
    settings_path = project_dir / "settings.gradle"
    if not settings_path.is_file():
        return
    content = settings_path.read_text(encoding="utf-8")
    safe_name = re.sub(r"[^A-Za-z0-9_]", "_", config.name) or "app"
    content = re.sub(r'rootProject\.name\s*=\s*"[^"]*"', f'rootProject.name = "{safe_name}"', content)
    settings_path.write_text(content, encoding="utf-8")


def configure_strings(project_dir: Path, config: AppConfig) -> None:
    """Set the ``app_name`` and ``pn_entry_module`` string resources.

    Args:
        project_dir: The staged Android project root.
        config: The validated app configuration.
    """
    strings_path = project_dir / "app" / "src" / "main" / "res" / "values" / "strings.xml"
    if not strings_path.is_file():
        return
    content = strings_path.read_text(encoding="utf-8")
    escaped = _xml_escape(config.display_name)
    content = re.sub(
        r'(<string name="app_name">)(.*?)(</string>)',
        rf"\g<1>{escaped}\g<3>",
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<string name="pn_entry_module"[^>]*>)(.*?)(</string>)',
        rf"\g<1>{_xml_escape(config.entry_module)}\g<3>",
        content,
        flags=re.DOTALL,
    )
    strings_path.write_text(content, encoding="utf-8")


def configure_manifest(project_dir: Path, config: AppConfig) -> None:
    """Inject permissions, the launch orientation, and deep-link filters.

    Args:
        project_dir: The staged Android project root.
        config: The validated app configuration.
    """
    manifest_path = project_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    content = manifest_path.read_text(encoding="utf-8")

    permissions = config.resolved_permissions().android_permissions
    if permissions:
        lines = "".join(f'    <uses-permission android:name="{name}" />\n' for name in permissions)
        content = content.replace("    <application", f"{lines}\n    <application", 1)

    orientation_attr = _ANDROID_ORIENTATION.get(config.orientation)
    if orientation_attr:
        content = content.replace(
            '            android:exported="true"',
            f'            android:exported="true"\n            android:screenOrientation="{orientation_attr}"',
            1,
        )

    if config.url_schemes:
        schemes = "".join(f'                <data android:scheme="{scheme}" />\n' for scheme in config.url_schemes)
        deep_link_filter = (
            "            <intent-filter>\n"
            '                <action android:name="android.intent.action.VIEW" />\n'
            '                <category android:name="android.intent.category.DEFAULT" />\n'
            '                <category android:name="android.intent.category.BROWSABLE" />\n'
            f"{schemes}"
            "            </intent-filter>\n"
        )
        content = content.replace("        </activity>", f"{deep_link_filter}        </activity>", 1)

    manifest_path.write_text(content, encoding="utf-8")


_ANDROID_ORIENTATION = {
    "portrait": "portrait",
    "landscape": "sensorLandscape",
}


def write_requirements(project_dir: Path, config: AppConfig) -> None:
    """Generate ``app/requirements.txt`` from ``[requirements].packages``.

    Chaquopy installs from this file (referenced by ``build.gradle``).

    Args:
        project_dir: The staged Android project root.
        config: The validated app configuration.
    """
    requirements_path = project_dir / "app" / "requirements.txt"
    body = "\n".join(config.requirements)
    requirements_path.write_text(body + ("\n" if body else ""), encoding="utf-8")


# ======================================================================
# Branding (icons + splash)
# ======================================================================


def _apply_branding(project_dir: Path, config: AppConfig, emit: Logger) -> None:
    res_dir = project_dir / "app" / "src" / "main" / "res"
    icon_path = config.resolve_path(config.icon) if config.icon else None
    splash_path = config.resolve_path(config.splash) if config.splash else None

    if icon_path and icons.has_source(icon_path):
        if icons.generate_android_icons(icon_path, res_dir):
            emit("Generated Android launcher icons.")
        else:
            emit("Skipping Android icons: Pillow not installed (pip install 'pythonnative[build]').")

    if splash_path and icons.has_source(splash_path):
        if icons.pillow_available():
            configure_splash(project_dir, config, splash_path)
            emit("Configured Android splash screen.")
        else:
            emit("Skipping Android splash: Pillow not installed (pip install 'pythonnative[build]').")


def configure_splash(project_dir: Path, config: AppConfig, splash_path: Path) -> None:
    """Wire up an Android 12+ splash screen from the splash asset.

    Adds the ``androidx.core:core-splashscreen`` dependency, a
    ``Theme.App.Starting`` splash theme (with the splash background color
    and centered icon), installs the splash in ``MainActivity``, and
    points the launcher activity at the splash theme.

    Args:
        project_dir: The staged Android project root.
        config: The validated app configuration.
        splash_path: Path to the source splash image.
    """
    res_dir = project_dir / "app" / "src" / "main" / "res"
    background = icons.dominant_background_color(splash_path) or "#FFFFFF"

    icons.generate_android_splash_icon(splash_path, res_dir / "drawable-xxxhdpi" / "pn_splash_icon.png")

    _upsert_color(res_dir / "values" / "colors.xml", "pn_splash_background", background)

    splash_style = (
        '    <style name="Theme.App.Starting" parent="Theme.SplashScreen">\n'
        '        <item name="windowSplashScreenBackground">@color/pn_splash_background</item>\n'
        '        <item name="windowSplashScreenAnimatedIcon">@drawable/pn_splash_icon</item>\n'
        '        <item name="postSplashScreenTheme">@style/Theme.Android_template</item>\n'
        "    </style>\n"
    )
    for themes in (res_dir / "values" / "themes.xml", res_dir / "values-night" / "themes.xml"):
        _insert_style(themes, splash_style)

    _add_gradle_dependency(
        project_dir / "app" / "build.gradle",
        "implementation 'androidx.core:core-splashscreen:1.0.1'",
    )
    _install_splash_in_activity(project_dir, config)

    # Point the app theme at the splash theme; ``installSplashScreen()`` swaps
    # to ``postSplashScreenTheme`` (the original theme) right after launch.
    manifest_path = project_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = manifest.replace(
        'android:theme="@style/Theme.Android_template"',
        'android:theme="@style/Theme.App.Starting"',
        1,
    )
    manifest_path.write_text(manifest, encoding="utf-8")


def _install_splash_in_activity(project_dir: Path, config: AppConfig) -> None:
    activity = project_dir / "app" / "src" / "main" / "java" / config.android_package_path / "MainActivity.kt"
    if not activity.is_file():
        return
    content = activity.read_text(encoding="utf-8")
    if "installSplashScreen" in content:
        return
    content = content.replace(
        "import androidx.appcompat.app.AppCompatActivity",
        "import androidx.appcompat.app.AppCompatActivity\n"
        "import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen",
        1,
    )
    content = content.replace(
        "        super.onCreate(savedInstanceState)",
        "        installSplashScreen()\n        super.onCreate(savedInstanceState)",
        1,
    )
    activity.write_text(content, encoding="utf-8")


# ======================================================================
# Python source staging
# ======================================================================


def stage_python_sources(
    project_dir: Path,
    config: AppConfig,
    *,
    dev_lib_root: Optional[Path] = None,
) -> Path:
    """Copy the user's ``app/`` and (optionally) the in-repo library.

    Args:
        project_dir: The staged Android project root.
        config: The validated app configuration.
        dev_lib_root: Path to an in-repo ``pythonnative`` package to
            bundle, or ``None``.

    Returns:
        The Chaquopy Python source root (``app/src/main/python``).
    """
    python_root = project_dir / "app" / "src" / "main" / "python"
    python_root.mkdir(parents=True, exist_ok=True)

    app_src = config.project_root / "app"
    if app_src.is_dir():
        shutil.copytree(app_src, python_root / "app", dirs_exist_ok=True)

    if dev_lib_root and dev_lib_root.is_dir():
        shutil.copytree(
            dev_lib_root,
            python_root / "pythonnative",
            dirs_exist_ok=True,
            ignore=LIB_IGNORE,
        )

    return python_root


LIB_IGNORE = shutil.ignore_patterns("templates", "__pycache__", "*.pyc", "*.pyo")
"""Ignore rules for bundling the ``pythonnative`` package (skips templates)."""


# ======================================================================
# Small XML/text helpers
# ======================================================================


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _upsert_color(colors_path: Path, name: str, value: str) -> None:
    if not colors_path.is_file():
        colors_path.parent.mkdir(parents=True, exist_ok=True)
        colors_path.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n</resources>\n',
            encoding="utf-8",
        )
    content = colors_path.read_text(encoding="utf-8")
    entry = f'    <color name="{name}">{value}</color>\n'
    if f'name="{name}"' in content:
        content = re.sub(
            rf'(<color name="{re.escape(name)}">)(.*?)(</color>)',
            rf"\g<1>{value}\g<3>",
            content,
        )
    else:
        content = content.replace("</resources>", f"{entry}</resources>", 1)
    colors_path.write_text(content, encoding="utf-8")


def _insert_style(themes_path: Path, style_block: str) -> None:
    if not themes_path.is_file():
        return
    content = themes_path.read_text(encoding="utf-8")
    if "Theme.App.Starting" in content:
        return
    content = content.replace("</resources>", f"{style_block}</resources>", 1)
    themes_path.write_text(content, encoding="utf-8")


def _add_gradle_dependency(gradle_path: Path, dependency: str) -> None:
    content = gradle_path.read_text(encoding="utf-8")
    if dependency in content:
        return
    content = content.replace("dependencies {\n", f"dependencies {{\n    {dependency}\n", 1)
    gradle_path.write_text(content, encoding="utf-8")


def collect_logcat_filters() -> List[str]:
    """Return the logcat tag filters used when streaming device logs.

    Returns:
        A list of ``tag:level`` filter specs ending with ``*:S`` to
        silence everything else.
    """
    return [
        "python.stdout:V",
        "python.stderr:V",
        "PythonNative:V",
        "AndroidRuntime:E",
        "System.err:W",
        "*:S",
    ]
