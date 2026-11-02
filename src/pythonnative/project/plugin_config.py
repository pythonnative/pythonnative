"""Apply native plugins' declarative configuration to a staged project.

This is PythonNative's counterpart to Expo's config plugins. A
``pn_plugin.json`` can declare options, required permissions, and changes
to ``Info.plist``, entitlements, the privacy manifest,
``AndroidManifest.xml``, Gradle plugins, and project files. Nothing here
imports or runs plugin code: target wheels stay data, so reading a plugin
can't execute anything on the build machine.

The merge rules, which RFC 0008 specifies:

- Dictionaries merge recursively and lists merge as ordered unions.
- Two plugins setting one scalar to different values is an error naming both.
- ``[ios].extra_info_plist`` applies last, so the app has the final say.
- ``${option}`` substitutes in strings; an unknown name is an error.
"""

from __future__ import annotations

import os
import plistlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .config import AppConfig
from .plugins import FIRST_PARTY_PLUGINS, NativePlugin, PluginError

__all__ = [
    "ResolvedPlugin",
    "apply_android",
    "apply_ios",
    "check_requirements",
    "merge",
    "resolve_all",
    "resolve_plugin",
]

_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Gradle resolves these itself while merging the Android manifest.
_GRADLE_PLACEHOLDERS = frozenset({"applicationId"})

_PERMISSION_LINE = '    <uses-permission android:name="{name}" />\n'


@dataclass(frozen=True)
class ResolvedPlugin:
    """A plugin with its options read and its conditional sections applied.

    Attributes:
        plugin: The parsed plugin.
        options: Final option values, by name; ``None`` means unset.
        ios: The ``ios`` section with ``when`` applied and options substituted.
        android: The ``android`` section with ``when`` applied and options substituted.
    """

    plugin: NativePlugin
    options: Dict[str, Any] = field(default_factory=dict)
    ios: Dict[str, Any] = field(default_factory=dict)
    android: Dict[str, Any] = field(default_factory=dict)


# ======================================================================
# Options
# ======================================================================


def _read_options(plugin: NativePlugin, config: AppConfig, environ: Mapping[str, str]) -> Dict[str, Any]:
    declared: Dict[str, Dict[str, Any]] = plugin.manifest.get("options", {})
    given = dict(config.plugin_options.get(plugin.name, {}))
    unknown = sorted(set(given) - set(declared))
    if unknown:
        known = ", ".join(sorted(declared)) or "none"
        raise PluginError(
            f"[plugins.{plugin.name}] has unknown option(s) {', '.join(unknown)}. Known options: {known}."
        )
    values: Dict[str, Any] = {}
    for name, spec in declared.items():
        value = given.get(name)
        if value is None and spec.get("env"):
            value = environ.get(str(spec["env"])) or None
        if value is None:
            value = spec.get("default")
        if value is None and spec.get("required"):
            source = f" or set {spec['env']}" if spec.get("env") else ""
            raise PluginError(f"Plugin {plugin.name!r} requires [plugins.{plugin.name}].{name}{source}.")
        values[name] = None if value is None else _coerce(plugin, name, spec, value, config)
    return values


def _coerce(plugin: NativePlugin, name: str, spec: Dict[str, Any], value: Any, config: AppConfig) -> Any:
    kind = spec["type"]
    expected: Dict[str, type] = {"string": str, "integer": int, "boolean": bool, "path": str, "list": list}
    if kind == "integer" and isinstance(value, str) and value.lstrip("-").isdigit():
        value = int(value)
    if not isinstance(value, expected[kind]) or (kind == "integer" and isinstance(value, bool)):
        raise PluginError(f"[plugins.{plugin.name}].{name} must be a {kind}, got {value!r}.")
    if kind == "path":
        resolved = config.resolve_path(str(value))
        if not Path(resolved).exists():
            raise PluginError(f"[plugins.{plugin.name}].{name}: {value!r} doesn't exist.")
        return str(resolved)
    return value


def _substitute(value: Any, options: Mapping[str, Any], plugin: NativePlugin) -> Any:
    """Replace ``${option}`` in strings, keeping a whole-value reference's type."""
    if isinstance(value, dict):
        return {key: _substitute(item, options, plugin) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item, options, plugin) for item in value]
    if not isinstance(value, str):
        return value
    whole = _VARIABLE.fullmatch(value)
    if whole and whole.group(1) in options:
        return options[whole.group(1)]

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in _GRADLE_PLACEHOLDERS:
            return match.group(0)
        if name not in options:
            raise PluginError(f"Plugin {plugin.name!r} references unknown option ${{{name}}}.")
        return "" if options[name] is None else str(options[name])

    return _VARIABLE.sub(replace, value)


def _section(plugin: NativePlugin, platform: str, options: Mapping[str, Any]) -> Dict[str, Any]:
    raw = dict(plugin.manifest.get(platform) or {})
    conditional = raw.pop("when", {})
    section: Dict[str, Any] = _substitute(raw, options, plugin)
    for option, nested in conditional.items():
        if options.get(option) not in (None, False, "", []):
            merge(section, _substitute(nested, options, plugin), owner=plugin.name, owners={})
    return section


def resolve_plugin(
    plugin: NativePlugin, config: AppConfig, *, environ: Optional[Mapping[str, str]] = None
) -> ResolvedPlugin:
    """Read ``plugin``'s options and apply its ``when`` sections."""
    options = _read_options(plugin, config, os.environ if environ is None else environ)
    options = {"app_id": config.app_id, "display_name": config.display_name, **options}
    return ResolvedPlugin(plugin, options, _section(plugin, "ios", options), _section(plugin, "android", options))


def resolve_all(
    plugins: Sequence[NativePlugin], config: AppConfig, *, environ: Optional[Mapping[str, str]] = None
) -> List[ResolvedPlugin]:
    """Validate ``plugins`` against ``config`` and resolve each one."""
    check_requirements(plugins, config)
    return [resolve_plugin(plugin, config, environ=environ) for plugin in plugins]


def check_requirements(plugins: Sequence[NativePlugin], config: AppConfig) -> None:
    """Require every declared permission, required plugin, and option table to have a counterpart.

    Raises:
        PluginError: Naming the exact ``pythonnative.toml`` line to add.
    """
    names = {plugin.name for plugin in plugins}
    for option_table in config.plugin_options:
        if option_table not in names:
            raise PluginError(
                f"[plugins.{option_table}] configures a plugin that isn't in this build. "
                f"Add {option_table!r} to [plugins].use, or remove the table."
                if option_table in FIRST_PARTY_PLUGINS
                else f"[plugins.{option_table}] configures a plugin that isn't in this build."
            )
    enabled = {key for key, value in config.permissions.items() if value}
    for plugin in plugins:
        for required in plugin.requires_plugins:
            if required not in names:
                raise PluginError(f"Plugin {plugin.name!r} requires {required!r}: add it to [plugins].use.")
        for permission in plugin.requires_permissions:
            if permission not in enabled:
                raise PluginError(
                    f"Plugin {plugin.name!r} needs {permission!r} declared under [permissions] in "
                    f"pythonnative.toml, with the reason the system prompt shows."
                )


# ======================================================================
# Merging
# ======================================================================


def merge(
    target: Dict[str, Any],
    source: Mapping[str, Any],
    *,
    owner: str,
    owners: Dict[str, str],
    path: str = "",
) -> Dict[str, Any]:
    """Merge ``source`` into ``target``, recording who set each scalar in ``owners``.

    Raises:
        PluginError: If two owners set one scalar to different values.
    """
    for key, value in source.items():
        location = f"{path}{key}"
        current = target.get(key)
        if key not in target and isinstance(value, dict):
            target[key] = {}
            merge(target[key], value, owner=owner, owners=owners, path=f"{location}.")
        elif key not in target:
            target[key] = _copy(value)
            owners.setdefault(location, owner)
        elif isinstance(current, dict) and isinstance(value, dict):
            merge(current, value, owner=owner, owners=owners, path=f"{location}.")
        elif isinstance(current, list) and isinstance(value, list):
            current.extend(item for item in value if item not in current)
        elif current != value:
            raise PluginError(
                f"Plugins {owners.get(location, 'the template')!r} and {owner!r} set {location} to "
                f"different values ({current!r} and {value!r})."
            )
    return target


def _copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy(item) for item in value]
    return value


def _merge_privacy(manifest: Dict[str, Any], privacy: Mapping[str, Any]) -> None:
    types = manifest.setdefault("NSPrivacyAccessedAPITypes", [])
    for entry in privacy.get("accessed_api_types", ()):
        existing = next((item for item in types if item.get("NSPrivacyAccessedAPIType") == entry["type"]), None)
        if existing is None:
            existing = {"NSPrivacyAccessedAPIType": entry["type"], "NSPrivacyAccessedAPITypeReasons": []}
            types.append(existing)
        reasons = existing["NSPrivacyAccessedAPITypeReasons"]
        reasons.extend(reason for reason in entry["reasons"] if reason not in reasons)
    collected = manifest.setdefault("NSPrivacyCollectedDataTypes", [])
    collected.extend(item for item in privacy.get("collected_data_types", ()) if item not in collected)
    domains = list(privacy.get("tracking_domains", ()))
    if domains:
        tracking = manifest.setdefault("NSPrivacyTrackingDomains", [])
        tracking.extend(domain for domain in domains if domain not in tracking)
        manifest["NSPrivacyTracking"] = True


# ======================================================================
# iOS
# ======================================================================


def apply_ios(
    project_dir: Path,
    config: AppConfig,
    plugins: Sequence[NativePlugin],
    *,
    log: Optional[Callable[[str], None]] = None,
) -> List[ResolvedPlugin]:
    """Merge plugins' plist, entitlement, and privacy declarations into the staged project."""
    from . import ios as ios_config

    resolved = resolve_all([plugin for plugin in plugins if plugin.has_ios], config)
    project_dir = Path(project_dir)
    info_path = project_dir / "ios_template" / "Info.plist"
    with open(info_path, "rb") as handle:
        info = plistlib.load(handle)
    entitlements_path = project_dir / ios_config.ENTITLEMENTS_FILE
    entitlements: Dict[str, Any] = {}
    if entitlements_path.is_file():
        with open(entitlements_path, "rb") as handle:
            entitlements = plistlib.load(handle)
    privacy_path = project_dir / "ios_template" / "PrivacyInfo.xcprivacy"
    with open(privacy_path, "rb") as handle:
        privacy = plistlib.load(handle)

    info_owners: Dict[str, str] = {}
    entitlement_owners: Dict[str, str] = {}
    for item in resolved:
        merge(info, item.ios.get("info_plist", {}), owner=item.plugin.name, owners=info_owners)
        merge(entitlements, item.ios.get("entitlements", {}), owner=item.plugin.name, owners=entitlement_owners)
        _merge_privacy(privacy, item.ios.get("privacy", {}))
    # The app's own keys go last, whatever a plugin asked for.
    info.update(config.ios.extra_info_plist)

    with open(info_path, "wb") as handle:
        plistlib.dump(info, handle)
    if entitlements:
        entitlements_path.parent.mkdir(parents=True, exist_ok=True)
        with open(entitlements_path, "wb") as handle:
            plistlib.dump(entitlements, handle)
    with open(privacy_path, "wb") as handle:
        plistlib.dump(privacy, handle)
    if log is not None and resolved:
        log(f"Applied plugin configuration for iOS: {', '.join(item.plugin.name for item in resolved)}.")
    return resolved


# ======================================================================
# Android
# ======================================================================


def _read_fragment(item: ResolvedPlugin, relative: str) -> str:
    path = (item.plugin.root / relative).resolve()
    if not path.is_relative_to(item.plugin.root) or not path.is_file():
        raise PluginError(f"{item.plugin.name}: manifest fragment {relative!r} must be a file inside the plugin")
    text = _substitute(path.read_text(encoding="utf-8"), item.options, item.plugin)
    return text.rstrip("\n") + "\n"


def _apply_manifest(project_dir: Path, resolved: Sequence[ResolvedPlugin]) -> None:
    path = project_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    content = path.read_text(encoding="utf-8")
    root_lines: List[str] = []
    application_lines: List[str] = []
    for item in resolved:
        for name in item.android.get("permissions", ()):
            line = _PERMISSION_LINE.format(name=name)
            if f'android:name="{name}"' not in content and line not in root_lines:
                root_lines.append(line)
        fragments = item.android.get("manifest", {})
        if "root" in fragments:
            root_lines.append(_read_fragment(item, fragments["root"]))
        if "application" in fragments:
            application_lines.append(_read_fragment(item, fragments["application"]))
    if root_lines:
        content = content.replace("    <application", "".join(root_lines) + "\n    <application", 1)
    if application_lines:
        content = content.replace("    </application>", "".join(application_lines) + "    </application>", 1)
    path.write_text(content, encoding="utf-8")


def _apply_gradle_plugins(project_dir: Path, resolved: Sequence[ResolvedPlugin]) -> None:
    declared: Dict[str, str] = {}
    for item in resolved:
        for entry in item.android.get("gradle_plugins", ()):
            identifier, version = str(entry["id"]), str(entry["version"])
            if declared.setdefault(identifier, version) != version:
                raise PluginError(f"Conflicting versions of Gradle plugin {identifier}.")
    if not declared:
        return
    root = project_dir / "build.gradle"
    content = root.read_text(encoding="utf-8")
    lines = "".join(f"    id '{name}' version '{version}' apply false\n" for name, version in sorted(declared.items()))
    root.write_text(content.replace("plugins {\n", "plugins {\n" + lines, 1), encoding="utf-8")
    app = project_dir / "app" / "build.gradle"
    content = app.read_text(encoding="utf-8")
    lines = "".join(f"    id '{name}'\n" for name in sorted(declared))
    app.write_text(content.replace("plugins {\n", "plugins {\n" + lines, 1), encoding="utf-8")


def _apply_files(project_dir: Path, resolved: Sequence[ResolvedPlugin]) -> None:
    for item in resolved:
        for entry in item.android.get("files", ()):
            source = Path(entry["from"])
            source = source if source.is_absolute() else item.plugin.root / source
            target = (project_dir / entry["to"]).resolve()
            if not target.is_relative_to(project_dir.resolve()):
                raise PluginError(f"{item.plugin.name}: file target {entry['to']!r} escapes the project")
            if not source.is_file():
                raise PluginError(f"{item.plugin.name}: file {entry['from']!r} doesn't exist")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def apply_android(
    project_dir: Path,
    config: AppConfig,
    plugins: Sequence[NativePlugin],
    *,
    log: Optional[Callable[[str], None]] = None,
) -> List[ResolvedPlugin]:
    """Merge plugins' manifest, Gradle, and file declarations into the staged project."""
    resolved = resolve_all([plugin for plugin in plugins if plugin.has_android], config)
    project_dir = Path(project_dir)
    _apply_manifest(project_dir, resolved)
    _apply_gradle_plugins(project_dir, resolved)
    _apply_files(project_dir, resolved)
    if log is not None and resolved:
        log(f"Applied plugin configuration for Android: {', '.join(item.plugin.name for item in resolved)}.")
    return resolved
