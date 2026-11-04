"""Native plugin staging for ``pn build``.

A package can ship Swift and Kotlin next to its Python facade, in a
directory containing:

```text
my_blur/native/
    pn_plugin.json
    ios/BlurViewManager.swift
    android/com/example/myblur/BlurViewManager.kt
```

``pn_plugin.json`` names the plugin (``name`` is required) and its
registration entry on each platform:

```json
{
  "name": "my_blur",
  "ios": {"entry": "MyBlurPlugin"},
  "android": {"entry": "com.example.myblur.MyBlurPlugin"}
}
```

The manifest may also declare options, the permissions and plugins it
requires, and changes to the app's ``Info.plist``, entitlements, privacy
manifest, ``AndroidManifest.xml``, and Gradle plugins, plus C, C++, and
xcframework sources. [`plugin_config`][pythonnative.project.plugin_config]
applies those; RFC 0008 describes the format.

A mobile build gathers plugins from three places:

- ``[plugins].use`` names first-party capabilities, which live in
  ``pythonnative/<name>/native``. Only those it names are bundled.
- [`discover_target_plugins`][pythonnative.project.plugins.discover_target_plugins]
  scans the wheels resolved for each device target for ``pn_plugin.json``.
  Wheels are inspected as data and never imported.
- ``[plugins].paths`` lists project directories with the same layout.

The ``pythonnative.plugins`` entry point group doesn't drive mobile builds.
``pn start`` reads it to tell that a project's requirements carry native code,
and [`discover_plugins`][pythonnative.project.plugins.discover_plugins]
inspects it only when asked to.

At build time this module copies each plugin's sources into the staged
native project (``PythonNativeKit/Sources/PythonNativeKit/Plugins/<name>``
on iOS, where ``<name>`` is the manifest's ``name``, and
``pythonnative/src/main/java`` on Android) and regenerates the registration
file that calls every entry's ``register``. SwiftPM and Gradle compile
whatever lands under those roots, so no project-file surgery is needed.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

__all__ = [
    "ENTRY_POINT_GROUP",
    "FIRST_PARTY_PLUGINS",
    "MANIFEST_NAME",
    "NOT_IN_GO",
    "NativePlugin",
    "PluginError",
    "discover_plugins",
    "first_party_plugins",
    "load_plugin",
    "stage_android_plugins",
    "stage_ios_plugins",
]

ENTRY_POINT_GROUP = "pythonnative.plugins"
"""Entry-point group whose values name plugin directories (as packages)."""

MANIFEST_NAME = "pn_plugin.json"
"""File name of the per-plugin manifest."""

FIRST_PARTY_PLUGINS = (
    "audio",
    "background",
    "biometrics",
    "camera",
    "location",
    "maps",
    "notifications",
    "pickers",
    "purchases",
    "push",
    "sensors",
    "video",
)
"""Capabilities ``[plugins].use`` accepts: subpackages of ``pythonnative`` holding a ``native`` plugin."""

NOT_IN_GO = ("push",)
"""Capabilities PythonNative Go leaves out.

A device token belongs to the app's own bundle ID and Firebase project, so a token
issued to Go would be useless, and the push entitlement stops Go building for
free Apple accounts. Projects using these run in their own debug build.
"""

_OPTION_TYPES = ("string", "integer", "boolean", "path", "list")
_MANIFEST_KEYS = frozenset({"name", "contracts", "requires", "options", "ios", "android", "web"})
_IOS_KEYS = frozenset(
    {
        "entry",
        "resources",
        "dependencies",
        "info_plist",
        "entitlements",
        "privacy",
        "binary_targets",
        "c_target",
        "when",
    }
)
_ANDROID_KEYS = frozenset(
    {
        "entry",
        "resources",
        "assets",
        "dependencies",
        "permissions",
        "manifest",
        "cmake",
        "gradle_plugins",
        "files",
        "when",
    }
)

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
        name: Stable identifier, from the manifest's ``name``. Used for
            the iOS subfolder.
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
    ios_resources: Sequence[Path] = field(default_factory=tuple)
    android_resources: Sequence[Path] = field(default_factory=tuple)
    android_assets: Sequence[Path] = field(default_factory=tuple)
    contracts: Optional[Path] = None
    swift_dependencies: tuple[SwiftDependency, ...] = ()
    maven_dependencies: tuple[str, ...] = ()
    manifest: Dict[str, Any] = field(default_factory=dict)

    @property
    def requires_plugins(self) -> tuple[str, ...]:
        """Plugins that must also be in this app's build."""
        return tuple((self.manifest.get("requires") or {}).get("plugins", ()))

    @property
    def requires_permissions(self) -> tuple[str, ...]:
        """``[permissions]`` entries this plugin needs the app to declare."""
        return tuple((self.manifest.get("requires") or {}).get("permissions", ()))

    @property
    def web_entry(self) -> Optional[str]:
        """The browser preview's ES module, relative to the plugin root."""
        web = self.manifest.get("web")
        return str(web["entry"]) if isinstance(web, dict) else None

    @property
    def has_ios(self) -> bool:
        """Whether this plugin contributes Swift code."""
        return self.ios_entry is not None

    @property
    def has_android(self) -> bool:
        """Whether this plugin contributes Kotlin code."""
        return self.android_entry is not None


@dataclass(frozen=True)
class SwiftDependency:
    """An exact Swift package release and the products linked into the runtime."""

    url: str
    version: str
    products: tuple[str, ...]

    @property
    def identity(self) -> str:
        """SwiftPM's identity for this Git repository."""
        return self.url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git").lower()


def _native_dependencies(manifest: dict[str, Any]) -> tuple[tuple[SwiftDependency, ...], tuple[str, ...]]:
    from urllib.parse import urlsplit

    swift = (manifest.get("ios") or {}).get("dependencies", [])
    maven = (manifest.get("android") or {}).get("dependencies", [])
    if not isinstance(swift, list) or not isinstance(maven, list):
        raise PluginError("Native dependencies must be arrays")
    packages = []
    for item in swift:
        if not isinstance(item, dict) or set(item) != {"url", "version", "products"}:
            raise PluginError("Swift dependencies require url, version, and products")
        url, version, products = item["url"], item["version"], item["products"]
        if not isinstance(url, str) or not isinstance(version, str):
            raise PluginError("Swift dependency URLs and versions must be strings")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise PluginError("Swift dependencies require an HTTPS repository URL without credentials")
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", version):
            raise PluginError("Swift dependencies require an exact semantic version")
        if (
            not isinstance(products, list)
            or not products
            or not all(isinstance(product, str) and _SWIFT_IDENT.fullmatch(product) for product in products)
        ):
            raise PluginError("Swift dependencies require a nonempty array of product identifiers")
        package = SwiftDependency(url, version, tuple(sorted(set(products))))
        if not re.fullmatch(r"[a-z0-9_.-]+", package.identity):
            raise PluginError("Invalid Swift package repository identity")
        packages.append(package)
    for coordinate in maven:
        if (
            not isinstance(coordinate, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:\d[0-9A-Za-z_.-]*", coordinate)
            or "SNAPSHOT" in coordinate.upper()
        ):
            raise PluginError("Android dependencies require exact group:artifact:version coordinates")
    return tuple(packages), tuple(sorted(set(maven)))


def _dependency_block(content: str, name: str, lines: Sequence[str]) -> str:
    marker = f"// pn:{name}"
    end = f"// pn:end-{name}"
    pattern = re.escape(marker) + r".*?" + re.escape(end)
    if not re.search(pattern, content, re.DOTALL):
        if lines:
            raise PluginError(f"Native template is missing its {name} dependency block")
        return content
    return re.sub(pattern, lambda _: marker + "\n" + "\n".join(lines) + "\n    " + end, content, flags=re.DOTALL)


def _has_local_targets(plugin: NativePlugin) -> bool:
    section = plugin.manifest.get("ios") or {}
    return bool(section.get("binary_targets") or section.get("c_target"))


def _ios_local_targets(plugin: NativePlugin, project_dir: Path) -> tuple[List[str], List[str]]:
    """Copy a plugin's xcframeworks and C sources, returning its target names and declarations."""
    section = plugin.manifest.get("ios") or {}
    package_root = project_dir / "PythonNativeKit"
    names: List[str] = []
    lines: List[str] = []
    for relative in section.get("binary_targets", ()):
        source = (plugin.root / relative).resolve()
        if not source.is_relative_to(plugin.root) or not source.is_dir() or source.suffix != ".xcframework":
            raise PluginError(f"{plugin.name}: binary target {relative!r} must be an .xcframework inside the plugin")
        destination = package_root / "PluginBinaries" / plugin.name / source.name
        shutil.copytree(source, destination, dirs_exist_ok=True)
        names.append(source.stem)
        lines.append(
            f"        .binaryTarget(name: {json.dumps(source.stem)}, "
            f"path: {json.dumps(str(destination.relative_to(package_root)))}),"
        )
    c_target = section.get("c_target")
    if c_target is not None:
        if not isinstance(c_target, dict) or not {"sources", "public_headers"} <= set(c_target):
            raise PluginError(f"{plugin.name}: ios.c_target needs 'sources' and 'public_headers'")
        source = (plugin.root / c_target["sources"]).resolve()
        if not source.is_relative_to(plugin.root) or not source.is_dir():
            raise PluginError(f"{plugin.name}: ios.c_target.sources must be a directory inside the plugin")
        destination = package_root / "PluginC" / plugin.name
        shutil.copytree(source, destination, dirs_exist_ok=True)
        headers = (plugin.root / c_target["public_headers"]).resolve().relative_to(source)
        target = f"PNC_{plugin.name}"
        names.append(target)
        lines.append(
            f"        .target(name: {json.dumps(target)}, "
            f"path: {json.dumps(str(destination.relative_to(package_root)))}, "
            f"publicHeadersPath: {json.dumps(str(headers))}),"
        )
    return names, lines


def _stage_dependencies(project_dir: Path, plugins: Sequence[NativePlugin], platform: str) -> None:
    """Resolve declarations deterministically and reject cross-plugin conflicts."""
    if platform == "ios":
        packages: dict[str, SwiftDependency] = {}
        for plugin in plugins:
            for item in plugin.swift_dependencies:
                old = packages.get(item.identity)
                if old is not None and (old.url, old.version) != (item.url, item.version):
                    raise PluginError(f"Conflicting Swift package dependency: {item.identity}")
                products = tuple(sorted(set(item.products) | set(old.products if old else ())))
                packages[item.identity] = SwiftDependency(item.url, item.version, products)
        path = project_dir / "PythonNativeKit/Package.swift"
        if not path.exists():
            if packages or any(_has_local_targets(plugin) for plugin in plugins):
                raise PluginError("PythonNativeKit/Package.swift is missing")
            return
        for leftover in ("PluginBinaries", "PluginC"):
            shutil.rmtree(project_dir / "PythonNativeKit" / leftover, ignore_errors=True)
        content = path.read_text(encoding="utf-8")
        ordered = [packages[name] for name in sorted(packages)]
        content = _dependency_block(
            content,
            "packages",
            [f"        .package(url: {json.dumps(item.url)}, exact: {json.dumps(item.version)})," for item in ordered],
        )
        local_targets = [_ios_local_targets(plugin, project_dir) for plugin in plugins]
        content = _dependency_block(
            content,
            "products",
            [
                *(
                    f"                .product(name: {json.dumps(product)}, package: {json.dumps(item.identity)}),"
                    for item in ordered
                    for product in item.products
                ),
                *(f"                {json.dumps(name)}," for names, _ in local_targets for name in names),
            ],
        )
        content = _dependency_block(content, "targets", [line for _, lines in local_targets for line in lines])
    else:
        modules: dict[str, str] = {}
        for plugin in plugins:
            for coordinate in plugin.maven_dependencies:
                name, version = coordinate.rsplit(":", 1)
                if name in modules and modules[name] != version:
                    raise PluginError(f"Conflicting Android dependency: {name}")
                modules[name] = version
        path = project_dir / "pythonnative/build.gradle"
        if not path.exists():
            if modules:
                raise PluginError("pythonnative/build.gradle is missing")
            return
        content = _dependency_block(
            path.read_text(encoding="utf-8"),
            "dependencies",
            [f"    implementation '{name}:{version}'" for name, version in sorted(modules.items())],
        )
    path.write_text(content, encoding="utf-8")


# ======================================================================
# Discovery
# ======================================================================


def load_plugin(root: Path, *, name: Optional[str] = None) -> NativePlugin:
    """Read ``pn_plugin.json`` under ``root`` and collect its sources.

    Args:
        root: Directory containing the manifest.
        name: Identifier override (defaults to the manifest's ``name``,
            which is required when this isn't given).

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
    _validate_manifest(manifest, manifest_path)

    plugin_name = name or manifest.get("name")
    if not plugin_name:
        raise PluginError(f"{manifest_path} must declare a 'name'.")
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
        vendored = tuple(root / item for item in (manifest.get("ios") or {}).get("binary_targets", ()))
        ios_sources = sorted(
            p.relative_to(root)
            for p in (root / "ios").rglob("*.swift")
            if p.is_file() and not any(p.is_relative_to(target) for target in vendored)
        )
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

    def resources(platform: str, key: str) -> tuple[Path, ...]:
        section = manifest.get(platform, {})
        patterns = section.get(key, []) if isinstance(section, dict) else []
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise PluginError(f"{manifest_path}: {platform}.{key} must be a list of relative globs")
        selected: set[Path] = set()
        for pattern in patterns:
            if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                raise PluginError(f"Resource pattern escapes the plugin: {pattern}")
            for resource in root.glob(pattern):
                if resource.is_file():
                    if not resource.resolve().is_relative_to(root):
                        raise PluginError(f"Resource symlink escapes the plugin: {resource}")
                    selected.add(resource.relative_to(root))
        return tuple(sorted(selected))

    contract_path = Path(manifest["contracts"]) if "contracts" in manifest else None
    if contract_path is not None and (
        not (root / contract_path).is_file() or not (root / contract_path).resolve().is_relative_to(root)
    ):
        raise PluginError(f"{manifest_path}: contracts must name a file inside the plugin")
    swift_dependencies, maven_dependencies = _native_dependencies(manifest)
    return NativePlugin(
        name=plugin_name,
        root=root,
        ios_entry=ios_entry,
        android_entry=android_entry,
        ios_sources=tuple(ios_sources),
        android_sources=tuple(android_sources),
        ios_resources=resources("ios", "resources"),
        android_resources=resources("android", "resources"),
        android_assets=resources("android", "assets"),
        contracts=contract_path,
        swift_dependencies=swift_dependencies,
        maven_dependencies=maven_dependencies,
        manifest=manifest,
    )


def _validate_manifest(manifest: Dict[str, Any], path: Path) -> None:
    """Reject unknown keys and malformed declarations before anything is staged."""

    def unknown(section: Dict[str, Any], allowed: frozenset[str], label: str) -> None:
        extra = sorted(set(section) - allowed)
        if extra:
            raise PluginError(f"{path}: unknown {label} key(s): {', '.join(extra)}")

    unknown(manifest, _MANIFEST_KEYS, "manifest")
    requires = manifest.get("requires", {})
    if not isinstance(requires, dict) or set(requires) - {"plugins", "permissions"}:
        raise PluginError(f"{path}: 'requires' may only name 'plugins' and 'permissions'")
    for key, value in requires.items():
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise PluginError(f"{path}: requires.{key} must be a list of strings")
    options = manifest.get("options", {})
    if not isinstance(options, dict):
        raise PluginError(f"{path}: 'options' must be an object")
    for option, spec in options.items():
        if not isinstance(spec, dict) or spec.get("type") not in _OPTION_TYPES:
            raise PluginError(f"{path}: option {option!r} needs a type, one of {', '.join(_OPTION_TYPES)}")
        if set(spec) - {"type", "default", "required", "env"}:
            raise PluginError(f"{path}: option {option!r} has unknown keys")
    for platform, allowed in (("ios", _IOS_KEYS), ("android", _ANDROID_KEYS)):
        section = manifest.get(platform)
        if section is None:
            continue
        if not isinstance(section, dict):
            raise PluginError(f"{path}: '{platform}' must be an object")
        unknown(section, allowed, f"{platform}")
        when = section.get("when", {})
        if not isinstance(when, dict):
            raise PluginError(f"{path}: {platform}.when must be an object")
        for option, nested in when.items():
            if option not in options:
                raise PluginError(f"{path}: {platform}.when names unknown option {option!r}")
            if not isinstance(nested, dict):
                raise PluginError(f"{path}: {platform}.when.{option} must be an object")
            unknown(nested, allowed - {"entry", "when"}, f"{platform}.when.{option}")
    web = manifest.get("web")
    if web is not None and (not isinstance(web, dict) or not isinstance(web.get("entry"), str)):
        raise PluginError(f"{path}: 'web' must be an object with a string 'entry'")


def first_party_plugins(names: Iterable[str]) -> List[NativePlugin]:
    """Load the first-party capabilities listed in ``[plugins].use``.

    Raises:
        PluginError: If a name isn't a first-party capability.
    """
    package_root = Path(__file__).resolve().parents[1]
    plugins = []
    for name in names:
        if name not in FIRST_PARTY_PLUGINS:
            raise PluginError(
                f"Unknown capability {name!r} in [plugins].use. Available: {', '.join(FIRST_PARTY_PLUGINS)}. "
                "Third-party plugins are found through requirements and [plugins].paths."
            )
        plugins.append(load_plugin(package_root / name / "native"))
    return plugins


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
    include_environment: bool = True,
    log: Optional[Logger] = None,
) -> List[NativePlugin]:
    """Find every plugin visible to this interpreter.

    Args:
        extra_paths: Plugin directories to include in addition to the
            ``pythonnative.plugins`` entry points (from
            ``[plugins].paths`` in the project config).
        include_environment: Inspect this interpreter's installed entry points.
            Mobile builds pass ``False`` and inspect the target wheels instead,
            with [`discover_target_plugins`][pythonnative.project.plugins.discover_target_plugins].
        log: Optional progress logger; broken entry points are reported
            here and skipped rather than failing the build.

    Returns:
        Plugins in a stable order (entry points sorted by name, then
        explicit paths in the order given).
    """
    emit: Logger = log or (lambda _message: None)
    plugins: List[NativePlugin] = []
    seen: set = set()

    for ep_name, target in sorted(_entry_points().items() if include_environment else []):
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
    from importlib.metadata import entry_points

    return {ep.name: ep.value for ep in entry_points(group=ENTRY_POINT_GROUP)}


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
    resource_root = Path(project_dir) / "PythonNativeKit/Sources/PythonNativeKit/PluginResources"
    if resource_root.exists():
        shutil.rmtree(resource_root)
    for plugin in bundled:
        for rel in plugin.ios_resources:
            target = resource_root / plugin.name / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plugin.root / rel, target)
    package = Path(project_dir) / "PythonNativeKit/Package.swift"
    if package.exists():
        contents = package.read_text(encoding="utf-8")
        contents = contents.replace(', .copy("PluginResources")', "")
        if resource_root.exists():
            contents = contents.replace('.process("Resources")', '.process("Resources"), .copy("PluginResources")')
        package.write_text(contents, encoding="utf-8")
    _stage_dependencies(Path(project_dir), bundled, "ios")
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
    managed_manifest = Path(project_dir) / ".pn-plugin-files.json"
    if managed_manifest.exists():
        for relative in json.loads(managed_manifest.read_text(encoding="utf-8")):
            old = Path(project_dir) / relative
            if old.resolve().is_relative_to(Path(project_dir).resolve()) and old.is_file():
                old.unlink()
    managed = []

    bundled = [p for p in plugins if p.has_android]
    for plugin in bundled:
        for rel in plugin.android_sources:
            dest = source_root / Path(*rel.parts[1:])  # strip the leading "android/"
            if dest.exists() and dest.read_bytes() != (plugin.root / rel).read_bytes():
                raise PluginError(f"Conflicting plugin source: {dest}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plugin.root / rel, dest)
            managed.append(str(dest.relative_to(project_dir)))
    native_root = Path(project_dir) / "pythonnative/src/main"
    for plugin in bundled:
        for kind, resources in (("res", plugin.android_resources), ("assets", plugin.android_assets)):
            for rel in resources:
                parts = rel.parts
                # Android resource type directories (drawable, values, and so on) stay intact.
                index = parts.index(kind) + 1 if kind in parts else max(0, len(parts) - 2)
                target = native_root / kind / Path(*parts[index:])
                if kind == "assets":
                    target = native_root / kind / plugin.name / Path(*parts[index:])
                if target.exists() and target.read_bytes() != (plugin.root / rel).read_bytes():
                    raise PluginError(f"Conflicting plugin resource: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(plugin.root / rel, target)
                managed.append(str(target.relative_to(project_dir)))
    cpp_root = native_root / "cpp"
    shutil.rmtree(cpp_root / "plugins", ignore_errors=True)
    includes = []
    for plugin in bundled:
        cmake = (plugin.manifest.get("android") or {}).get("cmake")
        if cmake is None:
            continue
        source = (plugin.root / cmake).resolve()
        if not source.is_relative_to(plugin.root) or source.name != "CMakeLists.txt" or not source.is_file():
            raise PluginError(f"{plugin.name}: android.cmake must name a CMakeLists.txt inside the plugin")
        shutil.copytree(source.parent, cpp_root / "plugins" / plugin.name, dirs_exist_ok=True)
        includes.append(
            f"add_subdirectory(plugins/{plugin.name} ${{CMAKE_CURRENT_BINARY_DIR}}/plugins/{plugin.name})\n"
        )
    if cpp_root.is_dir():
        (cpp_root / "plugins.cmake").write_text(
            "# Generated by `pn build`: one add_subdirectory per plugin with native C or C++ sources.\n"
            + "".join(includes),
            encoding="utf-8",
        )
    registration.parent.mkdir(parents=True, exist_ok=True)
    _stage_dependencies(Path(project_dir), bundled, "android")
    registration.write_text(_render_kotlin_registration(bundled), encoding="utf-8")
    managed_manifest.write_text(json.dumps(sorted(managed)) + "\n", encoding="utf-8")
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


def discover_target_plugins(config: Any, targets: Sequence[Any], runner: Any) -> List[NativePlugin]:
    """Discover native source manifests from the wheels selected for each device.

    Target wheels are inspected as data. Their Python code isn't imported into
    the build interpreter, so binary extensions and host-only installations
    don't affect native plugin discovery.
    """
    import hashlib
    import zipfile

    from . import deps
    from .lockfile import read, target_key

    if not config.requirements:
        return []
    selected: Dict[str, NativePlugin] = {}
    fingerprints: Dict[str, str] = {}
    lock = read(config)
    for target in targets:
        cache = config.project_root / "build" / "plugin_wheels" / target_key(target).replace(":", "_")
        cache.mkdir(parents=True, exist_ok=True)
        if lock is not None:
            entry = lock["targets"].get(target_key(target))
            if entry is None:
                raise PluginError(f"pn.lock has no {target.label}; run 'pn deps --lock'.")
            urls = [package["url"] + "#sha256=" + package["sha256"] for package in entry["packages"]]
        else:
            resolution = deps.resolve(config, target, runner=runner)
            if not resolution.ok:
                raise PluginError(f"Cannot resolve plugins for {target.label}: {resolution.error}")
            urls = [
                package.url + ("#sha256=" + package.sha256 if package.sha256 else "") for package in resolution.packages
            ]
        if urls:
            from urllib.parse import unquote, urlparse

            for url in urls:
                parsed = urlparse(url)
                cached = cache / Path(unquote(parsed.path)).name
                digest = parsed.fragment.removeprefix("sha256=") if parsed.fragment.startswith("sha256=") else None
                if cached.is_file() and (not digest or hashlib.sha256(cached.read_bytes()).hexdigest() != digest):
                    cached.unlink()
            command = deps.pip_base_args(config, target)
            command[3] = "download"
            result = runner.run([*command, "--no-deps", "--dest", str(cache), *urls], capture=True)
            if not result.ok:
                raise PluginError(f"Could not download plugin metadata for {target.label}: {result.stderr}")
        # Only inspect wheels in this resolution, excluding removed cached packages.
        names = {Path(unquote(urlparse(url).path)).name for url in urls}
        for wheel in sorted(cache.glob("*.whl")):
            if wheel.name not in names:
                continue
            with zipfile.ZipFile(wheel) as archive:
                manifests = [name for name in archive.namelist() if name.endswith("/" + MANIFEST_NAME)]
                if not manifests:
                    continue
                digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
                destination = cache / "extracted" / digest
                if not destination.exists():
                    for info in archive.infolist():
                        if Path(info.filename).is_absolute() or ".." in Path(info.filename).parts:
                            raise PluginError(f"Unsafe wheel path: {info.filename}")
                    destination.mkdir(parents=True)
                    archive.extractall(destination)
                for manifest_path in manifests:
                    plugin = load_plugin((destination / manifest_path).parent)
                    fingerprint = hashlib.sha256()
                    fingerprint.update((plugin.root / MANIFEST_NAME).read_bytes())
                    if plugin.contracts is not None:
                        fingerprint.update((plugin.root / plugin.contracts).read_bytes())
                    for rel in [
                        *plugin.ios_sources,
                        *plugin.android_sources,
                        *plugin.ios_resources,
                        *plugin.android_resources,
                        *plugin.android_assets,
                    ]:
                        fingerprint.update(str(rel).encode())
                        fingerprint.update((plugin.root / rel).read_bytes())
                    value = fingerprint.hexdigest()
                    if plugin.name in fingerprints and fingerprints[plugin.name] != value:
                        raise PluginError(f"Plugin {plugin.name} has different native source across target wheels")
                    fingerprints[plugin.name] = value
                    selected[plugin.name] = plugin
    return [selected[name] for name in sorted(selected)]
