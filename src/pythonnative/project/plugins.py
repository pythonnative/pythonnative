"""Native plugin staging for ``pn build``.

A PyPI package can ship Swift and Kotlin next to its Python facade. It
declares an entry point in the ``pythonnative.plugins`` group whose
value is an importable package directory containing:

```text
my_blur/native/
    pn_plugin.json
    ios/BlurViewManager.swift
    android/com/example/myblur/BlurViewManager.kt
```

``pn_plugin.json`` names the registration entry on each platform:

```json
{"ios": {"entry": "MyBlurPlugin"}, "android": {"entry": "com.example.myblur.MyBlurPlugin"}}
```

At build time this module copies each plugin's sources into the staged
native project (``PythonNativeKit/Sources/PythonNativeKit/Plugins/<name>``
on iOS, ``pythonnative/src/main/java`` on Android) and regenerates the
registration file that calls every entry's ``register``. SwiftPM and
Gradle compile whatever lands under those roots, so no project-file
surgery is needed.

Projects can also bundle plugins that aren't installed as distributions
by listing directories under ``[plugins].paths`` in ``pythonnative.toml``;
each path must contain the same ``pn_plugin.json`` layout.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

__all__ = [
    "ENTRY_POINT_GROUP",
    "MANIFEST_NAME",
    "NativePlugin",
    "PluginError",
    "discover_plugins",
    "load_plugin",
    "stage_android_plugins",
    "stage_ios_plugins",
]

ENTRY_POINT_GROUP = "pythonnative.plugins"
"""Entry-point group whose values name plugin directories (as packages)."""

MANIFEST_NAME = "pn_plugin.json"
"""File name of the per-plugin manifest."""

Logger = Callable[[str], None]

_IOS_PLUGIN_DIR = ("PythonNativeKit", "Sources", "PythonNativeKit", "Plugins")
_IOS_REGISTRATION = (*_IOS_PLUGIN_DIR, "PNPluginRegistration.swift")
_ANDROID_SOURCE_ROOT = ("pythonnative", "src", "main", "java")
_ANDROID_REGISTRATION = (*_ANDROID_SOURCE_ROOT, "com", "pythonnative", "runtime", "plugins", "GeneratedPlugins.kt")

_SWIFT_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KOTLIN_FQN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")


class PluginError(RuntimeError):
    """A plugin manifest or source layout is invalid."""


@dataclass(frozen=True)
class NativePlugin:
    """A discovered native plugin.

    Attributes:
        name: Stable identifier (the entry-point name or the directory
            name for path plugins). Used for the iOS subfolder.
        root: Directory containing ``pn_plugin.json``.
        ios_entry: Swift type conforming to ``PNPlugin``, or ``None``
            when the plugin has no iOS side.
        android_entry: Fully qualified Kotlin object implementing
            ``PNPlugin``, or ``None`` when the plugin has no Android side.
        ios_sources: Swift files under ``ios/``.
        android_sources: Kotlin files under ``android/`` (relative
            paths are preserved so packages land in the right folders).
    """

    name: str
    root: Path
    ios_entry: Optional[str] = None
    android_entry: Optional[str] = None
    ios_sources: Sequence[Path] = field(default_factory=tuple)
    android_sources: Sequence[Path] = field(default_factory=tuple)

    @property
    def has_ios(self) -> bool:
        """Whether this plugin contributes Swift code."""
        return self.ios_entry is not None

    @property
    def has_android(self) -> bool:
        """Whether this plugin contributes Kotlin code."""
        return self.android_entry is not None


# ======================================================================
# Discovery
# ======================================================================


def load_plugin(root: Path, *, name: Optional[str] = None) -> NativePlugin:
    """Read ``pn_plugin.json`` under ``root`` and collect its sources.

    Args:
        root: Directory containing the manifest.
        name: Identifier override (defaults to the directory name).

    Returns:
        The parsed plugin.

    Raises:
        PluginError: If the manifest is missing or malformed, or an
            entry is declared without any matching sources.
    """
    root = Path(root).resolve()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise PluginError(f"{root} has no {MANIFEST_NAME}.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PluginError(f"Could not parse {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise PluginError(f"{manifest_path} must contain a JSON object.")

    plugin_name = name or manifest.get("name") or root.name
    if not _SWIFT_IDENT.match(str(plugin_name).replace("-", "_")):
        raise PluginError(f"Plugin name {plugin_name!r} must be an identifier.")
    plugin_name = str(plugin_name).replace("-", "_")

    ios_entry = _entry(manifest, "ios", manifest_path)
    android_entry = _entry(manifest, "android", manifest_path)
    if ios_entry is None and android_entry is None:
        raise PluginError(f"{manifest_path} declares neither an 'ios' nor an 'android' entry.")

    ios_sources: List[Path] = []
    android_sources: List[Path] = []
    if ios_entry is not None:
        if not _SWIFT_IDENT.match(ios_entry):
            raise PluginError(f"{manifest_path}: ios.entry {ios_entry!r} is not a Swift type name.")
        ios_sources = sorted(p.relative_to(root) for p in (root / "ios").rglob("*.swift") if p.is_file())
        if not ios_sources:
            raise PluginError(f"{root} declares an iOS entry but ios/ contains no .swift files.")
    if android_entry is not None:
        if not _KOTLIN_FQN.match(android_entry):
            raise PluginError(f"{manifest_path}: android.entry {android_entry!r} must be a fully qualified name.")
        android_sources = sorted(
            p.relative_to(root) for p in (root / "android").rglob("*") if p.is_file() and p.suffix in (".kt", ".java")
        )
        if not android_sources:
            raise PluginError(f"{root} declares an Android entry but android/ contains no .kt or .java files.")

    return NativePlugin(
        name=plugin_name,
        root=root,
        ios_entry=ios_entry,
        android_entry=android_entry,
        ios_sources=tuple(ios_sources),
        android_sources=tuple(android_sources),
    )


def _entry(manifest: Dict[str, object], platform: str, manifest_path: Path) -> Optional[str]:
    section = manifest.get(platform)
    if section is None:
        return None
    if not isinstance(section, dict) or not isinstance(section.get("entry"), str):
        raise PluginError(f"{manifest_path}: '{platform}' must be an object with a string 'entry'.")
    return str(section["entry"])


def discover_plugins(
    *,
    extra_paths: Iterable[Path] = (),
    log: Optional[Logger] = None,
) -> List[NativePlugin]:
    """Find every plugin visible to this interpreter.

    Args:
        extra_paths: Plugin directories to include in addition to the
            ``pythonnative.plugins`` entry points (from
            ``[plugins].paths`` in the project config).
        log: Optional progress logger; broken entry points are reported
            here and skipped rather than failing the build.

    Returns:
        Plugins in a stable order (entry points sorted by name, then
        explicit paths in the order given).
    """
    emit: Logger = log or (lambda _message: None)
    plugins: List[NativePlugin] = []
    seen: set = set()

    for ep_name, target in sorted(_entry_points().items()):
        try:
            root = _resolve_entry_point(target)
            plugin = load_plugin(root, name=ep_name)
        except (PluginError, ImportError, AttributeError) as exc:
            emit(f"Skipping native plugin {ep_name!r}: {exc}")
            continue
        if plugin.name in seen:
            emit(f"Skipping duplicate native plugin {plugin.name!r}.")
            continue
        seen.add(plugin.name)
        plugins.append(plugin)

    for path in extra_paths:
        plugin = load_plugin(Path(path))
        if plugin.name in seen:
            raise PluginError(f"Native plugin {plugin.name!r} is declared twice.")
        seen.add(plugin.name)
        plugins.append(plugin)

    return plugins


def _entry_points() -> Dict[str, str]:
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - Python < 3.8
        return {}
    try:
        eps = entry_points()
    except Exception:
        return {}
    selected = []
    if hasattr(eps, "select"):
        selected = list(eps.select(group=ENTRY_POINT_GROUP))
    else:  # pragma: no cover - importlib.metadata < 3.10
        getter = getattr(eps, "get", None)
        if callable(getter):
            selected = list(getter(ENTRY_POINT_GROUP, []))
    return {ep.name: ep.value for ep in selected}


def _resolve_entry_point(target: str) -> Path:
    """Turn ``"pkg.subpkg"`` (or ``"pkg.subpkg:attr"``) into a directory."""
    module_name, _, attr = target.partition(":")
    module = import_module(module_name.strip())
    if attr:
        value = getattr(module, attr.strip())
        return Path(str(value))
    location = getattr(module, "__file__", None)
    if location is None:
        raise PluginError(f"{module_name!r} is a namespace package; point the entry point at a regular package.")
    return Path(location).resolve().parent


# ======================================================================
# Staging
# ======================================================================


def stage_ios_plugins(project_dir: Path, plugins: Sequence[NativePlugin], *, log: Optional[Logger] = None) -> None:
    """Copy Swift sources into ``PythonNativeKit`` and write the registration file.

    Args:
        project_dir: The staged ``ios_template`` directory.
        plugins: Plugins to bundle; ones without an iOS side are skipped.
        log: Optional progress logger.
    """
    emit: Logger = log or (lambda _message: None)
    plugins_dir = Path(project_dir).joinpath(*_IOS_PLUGIN_DIR)
    registration = Path(project_dir).joinpath(*_IOS_REGISTRATION)
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # Wipe previous plugin folders so removed plugins don't linger in an
    # incremental build directory; the registration file is regenerated.
    for child in plugins_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)

    bundled = [p for p in plugins if p.has_ios]
    for plugin in bundled:
        target = plugins_dir / plugin.name
        for rel in plugin.ios_sources:
            dest = target / Path(*rel.parts[1:])  # strip the leading "ios/"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plugin.root / rel, dest)
    registration.write_text(_render_swift_registration(bundled), encoding="utf-8")
    if bundled:
        emit(
            f"Bundled {len(bundled)} native plugin(s) into PythonNativeKit: " + ", ".join(p.name for p in bundled) + "."
        )


def stage_android_plugins(project_dir: Path, plugins: Sequence[NativePlugin], *, log: Optional[Logger] = None) -> None:
    """Copy Kotlin sources into the ``pythonnative`` module and write the registration file.

    Args:
        project_dir: The staged ``android_template`` directory.
        plugins: Plugins to bundle; ones without an Android side are skipped.
        log: Optional progress logger.
    """
    emit: Logger = log or (lambda _message: None)
    source_root = Path(project_dir).joinpath(*_ANDROID_SOURCE_ROOT)
    registration = Path(project_dir).joinpath(*_ANDROID_REGISTRATION)
    source_root.mkdir(parents=True, exist_ok=True)

    bundled = [p for p in plugins if p.has_android]
    for plugin in bundled:
        for rel in plugin.android_sources:
            dest = source_root / Path(*rel.parts[1:])  # strip the leading "android/"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plugin.root / rel, dest)
    registration.parent.mkdir(parents=True, exist_ok=True)
    registration.write_text(_render_kotlin_registration(bundled), encoding="utf-8")
    if bundled:
        emit(
            f"Bundled {len(bundled)} native plugin(s) into the pythonnative module: "
            + ", ".join(p.name for p in bundled)
            + "."
        )


def _render_swift_registration(plugins: Sequence[NativePlugin]) -> str:
    calls = "".join(f"        {p.ios_entry}.register(into: registry)\n" for p in plugins)
    body = f" {{\n{calls}    }}" if calls else " {}"
    return (
        "// Generated by `pn build`. Do not edit: the PythonNative build tool\n"
        "// overwrites this file with one `register(into:)` call per bundled plugin.\n"
        "\n"
        "/// Registration hook for plugins copied into `Sources/Plugins` by `pn build`.\n"
        "public enum PNGeneratedPlugins {\n"
        "    /// Register every generated plugin into `registry`.\n"
        f"    public static func registerAll(into registry: PNRegistry){body}\n"
        "}\n"
    )


def _render_kotlin_registration(plugins: Sequence[NativePlugin]) -> str:
    calls = "".join(f"        {p.android_entry}.register(registry)\n" for p in plugins)
    if calls:
        method = f"    fun registerAll(registry: PNRegistry) {{\n{calls}    }}\n"
    else:
        method = '    @Suppress("UNUSED_PARAMETER")\n    fun registerAll(registry: PNRegistry) {}\n'
    return (
        "package com.pythonnative.runtime.plugins\n"
        "\n"
        "import com.pythonnative.runtime.bridge.PNRegistry\n"
        "\n"
        "/**\n"
        " * Plugin registrations generated by `pn build`.\n"
        " *\n"
        " * The build tool overwrites this file with one `register` call per\n"
        " * plugin entry declared in the project's `pythonnative.plugins` entry\n"
        " * points. Nothing else may depend on its content beyond [registerAll].\n"
        " */\n"
        "object GeneratedPlugins {\n"
        "    /** Register every generated plugin with `registry`. */\n"
        f"{method}"
        "}\n"
    )
