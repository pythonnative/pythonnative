"""Typed model and loader for ``pythonnative.toml``.

Every PythonNative project is described by a single ``pythonnative.toml``
at its root. This module parses and validates that file into a typed
[`AppConfig`][pythonnative.project.config.AppConfig] tree that the rest
of the build system consumes. Keeping all parsing/validation here means
the configurators ([`ios`][pythonnative.project.ios],
[`android`][pythonnative.project.android]) and the
[`builder`][pythonnative.project.builder] can assume a fully-validated,
defaulted config object.

The canonical schema:

```toml
[app]
id = "com.example.myapp"      # reverse-DNS app/bundle id (required)
name = "myapp"                # short project name (required)
display_name = "My App"       # home-screen label (defaults to name)
version = "1.0.0"             # marketing version
build = 1                     # integer build number
python_version = "3.11"      # embedded CPython version
orientation = "portrait"     # portrait | landscape | all
entry_point = "app/main.py"  # module whose `App` is mounted

[permissions]                 # see pythonnative.project.permissions
camera = "Scan receipts."
notifications = true

[assets]
icon = "assets/icon.png"      # 1024x1024 source icon
splash = "assets/splash.png"  # splash/launch image

[requirements]
packages = ["humanize", "httpx"]

[ios]
deployment_target = "13.0"
development_team = "ABCDE12345"
bundle_id = "com.example.myapp"   # optional override of app.id

[ios.signing]
export_method = "app-store"       # development | ad-hoc | app-store | enterprise
provisioning_profile = "My App Distribution"

[android]
min_sdk = 24
target_sdk = 34
abi_filters = ["arm64-v8a", "x86_64"]

[android.signing]
keystore = "release.keystore"
key_alias = "myapp"
```
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from . import permissions as _permissions

try:  # Python 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # Python 3.10
    import tomli as _toml


CONFIG_FILENAME = "pythonnative.toml"
"""The fixed config filename looked up at the project root."""

SUPPORTED_PYTHON_VERSIONS = ("3.10", "3.11", "3.12")
"""CPython versions accepted in ``app.python_version``."""

IOS_SUPPORTED_PYTHON_VERSION = "3.11"
"""The CPython version with a pinned, verified iOS support build."""

VALID_ORIENTATIONS = ("portrait", "landscape", "all")
"""Accepted values for ``app.orientation``."""

VALID_IOS_EXPORT_METHODS = ("development", "ad-hoc", "app-store", "enterprise")
"""Accepted values for ``[ios.signing].export_method``."""

# Reserved Java keywords can't appear as Android package segments.
_JAVA_KEYWORDS = frozenset("""
    abstract assert boolean break byte case catch char class const continue default do double else enum
    extends final finally float for goto if implements import instanceof int interface long native new
    package private protected public return short static strictfp super switch synchronized this throw
    throws transient try void volatile while true false null
    """.split())

_APP_ID_SEGMENT = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}$")


class ConfigError(Exception):
    """Raised when ``pythonnative.toml`` is missing, malformed, or invalid.

    The message is intended to be shown directly to the user by the CLI,
    so it should be specific and actionable.
    """


# ======================================================================
# Sub-models
# ======================================================================


@dataclass
class IOSSigning:
    """iOS code-signing / export configuration (``[ios.signing]``).

    Attributes:
        export_method: How the archive is exported, one of
            ``development``, ``ad-hoc``, ``app-store``, ``enterprise``.
        provisioning_profile: Optional provisioning profile name or UUID
            for manual signing.
    """

    export_method: str = "development"
    provisioning_profile: Optional[str] = None


@dataclass
class IOSConfig:
    """iOS-specific settings (``[ios]``).

    Attributes:
        deployment_target: Minimum iOS version (e.g., ``"13.0"``).
        development_team: Apple Developer Team ID used for signing.
        bundle_id: Optional override of ``app.id`` for the iOS bundle
            identifier.
        extra_info_plist: Arbitrary additional ``Info.plist`` key/values
            merged verbatim into the generated plist.
        signing: Nested [`IOSSigning`][pythonnative.project.config.IOSSigning].
    """

    deployment_target: str = "13.0"
    development_team: Optional[str] = None
    bundle_id: Optional[str] = None
    extra_info_plist: Dict[str, Any] = field(default_factory=dict)
    signing: IOSSigning = field(default_factory=IOSSigning)


@dataclass
class AndroidSigning:
    """Android release signing configuration (``[android.signing]``).

    Passwords are never stored in the config; they're read from the
    environment at build time (see ``store_password_env`` /
    ``key_password_env``).

    Attributes:
        keystore: Path to the release keystore, relative to the project
            root.
        key_alias: Key alias within the keystore.
        store_password_env: Environment variable holding the keystore
            password.
        key_password_env: Environment variable holding the key password.
    """

    keystore: Optional[str] = None
    key_alias: Optional[str] = None
    store_password_env: str = "PN_ANDROID_KEYSTORE_PASSWORD"
    key_password_env: str = "PN_ANDROID_KEY_PASSWORD"

    @property
    def is_configured(self) -> bool:
        """Whether both a keystore path and key alias are present."""
        return bool(self.keystore and self.key_alias)


@dataclass
class AndroidConfig:
    """Android-specific settings (``[android]``).

    Attributes:
        min_sdk: Minimum supported Android API level.
        target_sdk: Target Android API level.
        compile_sdk: SDK level the project compiles against.
        application_id: Optional override of ``app.id`` for the Android
            application id (and package).
        abi_filters: Native ABIs to include (e.g., ``"arm64-v8a"``).
        permissions: Extra raw Android permission strings appended to the
            ones derived from ``[permissions]``.
        signing: Nested
            [`AndroidSigning`][pythonnative.project.config.AndroidSigning].
    """

    min_sdk: int = 24
    target_sdk: int = 34
    compile_sdk: int = 34
    application_id: Optional[str] = None
    abi_filters: List[str] = field(default_factory=lambda: ["armeabi-v7a", "arm64-v8a", "x86", "x86_64"])
    permissions: List[str] = field(default_factory=list)
    signing: AndroidSigning = field(default_factory=AndroidSigning)


# ======================================================================
# Root model
# ======================================================================


@dataclass
class AppConfig:
    """A fully-parsed, validated ``pythonnative.toml``.

    Use [`load`][pythonnative.project.config.AppConfig.load] to read it
    from a project directory, or
    [`from_dict`][pythonnative.project.config.AppConfig.from_dict] to
    build one from an already-parsed mapping (e.g., in tests).

    Attributes:
        app_id: Reverse-DNS identifier (``app.id``); the default bundle
            id / application id for both platforms.
        name: Short project name (``app.name``).
        display_name: Home-screen label (``app.display_name``).
        version: Marketing version string (``app.version``).
        build: Integer build number (``app.build``).
        python_version: Embedded CPython version (``app.python_version``).
        orientation: ``"portrait"``, ``"landscape"``, or ``"all"``.
        entry_point: Path to the entry module (``app.entry_point``).
        permissions: The declared capability map (``[permissions]``).
        icon: Optional source icon path (``[assets].icon``).
        splash: Optional splash image path (``[assets].splash``).
        requirements: Third-party pip packages (``[requirements].packages``).
        ios: Nested [`IOSConfig`][pythonnative.project.config.IOSConfig].
        android: Nested
            [`AndroidConfig`][pythonnative.project.config.AndroidConfig].
        project_root: Absolute path to the directory containing the config.
    """

    app_id: str
    name: str
    display_name: str
    version: str = "1.0.0"
    build: int = 1
    python_version: str = "3.11"
    orientation: str = "portrait"
    entry_point: str = "app/main.py"
    permissions: Dict[str, _permissions.PermissionValue] = field(default_factory=dict)
    icon: Optional[str] = None
    splash: Optional[str] = None
    requirements: List[str] = field(default_factory=list)
    ios: IOSConfig = field(default_factory=IOSConfig)
    android: AndroidConfig = field(default_factory=AndroidConfig)
    project_root: Path = field(default_factory=Path.cwd)

    # -- Derived values -------------------------------------------------

    @property
    def application_id(self) -> str:
        """The Android application id (``[android].application_id`` or ``app.id``)."""
        return self.android.application_id or self.app_id

    @property
    def bundle_id(self) -> str:
        """The iOS bundle identifier (``[ios].bundle_id`` or ``app.id``)."""
        return self.ios.bundle_id or self.app_id

    @property
    def entry_module(self) -> str:
        """The dotted import path for ``entry_point`` (e.g., ``"app.main"``)."""
        return entrypoint_to_module(self.entry_point)

    @property
    def android_package_path(self) -> str:
        """The Android source directory path for ``application_id``.

        ``"com.example.myapp"`` → ``"com/example/myapp"``.
        """
        return self.application_id.replace(".", "/")

    def resolve_path(self, relative: str) -> Path:
        """Resolve a config-relative path against the project root.

        Args:
            relative: A path string from the config (e.g., an icon path).

        Returns:
            An absolute [`Path`][pathlib.Path].
        """
        candidate = Path(relative)
        if candidate.is_absolute():
            return candidate
        return (self.project_root / candidate).resolve()

    def resolved_permissions(self) -> _permissions.ResolvedPermissions:
        """Resolve declared capabilities into native permission artifacts.

        Returns:
            A
            [`ResolvedPermissions`][pythonnative.project.permissions.ResolvedPermissions]
            combining ``[permissions]`` with any extra
            ``[android].permissions``.
        """
        return _permissions.resolve_permissions(
            self.permissions,
            extra_android_permissions=self.android.permissions,
        )

    # -- Construction ---------------------------------------------------

    @classmethod
    def load(cls, project_root: Optional[Path] = None) -> "AppConfig":
        """Load and validate ``pythonnative.toml`` from a project directory.

        Args:
            project_root: Directory containing the config. Defaults to the
                current working directory.

        Returns:
            A validated [`AppConfig`][pythonnative.project.config.AppConfig].

        Raises:
            ConfigError: If the file is missing, isn't valid TOML, or
                fails validation.
        """
        root = Path(project_root) if project_root is not None else Path.cwd()
        config_path = root / CONFIG_FILENAME
        if not config_path.is_file():
            legacy = root / "pythonnative.json"
            hint = ""
            if legacy.is_file():
                hint = (
                    "\nFound a legacy 'pythonnative.json'. PythonNative now uses "
                    "'pythonnative.toml'.\nRun 'pn init --force' to scaffold one, then "
                    "port your settings over."
                )
            raise ConfigError(f"No {CONFIG_FILENAME} found in {root}.{hint}")
        try:
            with open(config_path, "rb") as handle:
                data = _toml.load(handle)
        except _toml.TOMLDecodeError as exc:
            raise ConfigError(f"Could not parse {CONFIG_FILENAME}: {exc}") from exc
        return cls.from_dict(data, project_root=root)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, project_root: Optional[Path] = None) -> "AppConfig":
        """Build an [`AppConfig`][pythonnative.project.config.AppConfig] from a mapping.

        Args:
            data: A parsed TOML mapping (top-level tables: ``app``,
                ``permissions``, ``assets``, ``requirements``, ``ios``,
                ``android``).
            project_root: Directory the config came from, used to resolve
                relative paths.

        Returns:
            A validated config.

        Raises:
            ConfigError: On any structural or value validation failure.
        """
        root = Path(project_root) if project_root is not None else Path.cwd()
        app = _expect_table(data, "app")

        config = cls(
            app_id=_require_str(app, "id", "app"),
            name=_require_str(app, "name", "app"),
            display_name=_opt_str(app, "display_name") or _require_str(app, "name", "app"),
            version=_opt_str(app, "version") or "1.0.0",
            build=_opt_int(app, "build", default=1),
            python_version=_opt_str(app, "python_version") or "3.11",
            orientation=(_opt_str(app, "orientation") or "portrait").lower(),
            entry_point=_opt_str(app, "entry_point") or "app/main.py",
            permissions=dict(_expect_table(data, "permissions", optional=True)),
            ios=_parse_ios(_expect_table(data, "ios", optional=True)),
            android=_parse_android(_expect_table(data, "android", optional=True)),
            project_root=root,
        )

        assets = _expect_table(data, "assets", optional=True)
        config.icon = _opt_str(assets, "icon")
        config.splash = _opt_str(assets, "splash")

        requirements = _expect_table(data, "requirements", optional=True)
        config.requirements = _opt_str_list(requirements, "packages")

        config.validate()
        return config

    # -- Validation -----------------------------------------------------

    def validate(self) -> None:
        """Validate all fields, raising [`ConfigError`][pythonnative.project.config.ConfigError] on first problem."""
        _validate_app_id(self.app_id)
        if self.android.application_id:
            _validate_app_id(self.android.application_id)
        if self.ios.bundle_id:
            _validate_app_id(self.ios.bundle_id, allow_hyphen=True)

        if not self.name.strip():
            raise ConfigError("app.name must not be empty.")

        if not _VERSION_RE.match(self.version):
            raise ConfigError(f"app.version {self.version!r} must be a dotted number like '1.0.0'.")

        if self.build < 1:
            raise ConfigError("app.build must be a positive integer.")

        if self.python_version not in SUPPORTED_PYTHON_VERSIONS:
            supported = ", ".join(SUPPORTED_PYTHON_VERSIONS)
            raise ConfigError(
                f"app.python_version {self.python_version!r} is unsupported (choose one of: {supported})."
            )

        if self.orientation not in VALID_ORIENTATIONS:
            valid = ", ".join(VALID_ORIENTATIONS)
            raise ConfigError(f"app.orientation {self.orientation!r} is invalid (choose one of: {valid}).")

        if not self.entry_point.strip():
            raise ConfigError("app.entry_point must not be empty.")

        unknown = _permissions.unknown_capabilities(self.permissions.keys())
        if unknown:
            known = ", ".join(sorted(_permissions.CAPABILITIES))
            raise ConfigError("Unknown permission(s): " + ", ".join(unknown) + f".\nValid capabilities: {known}")

        _validate_requirements(self.requirements)

        if self.ios.signing.export_method not in VALID_IOS_EXPORT_METHODS:
            valid = ", ".join(VALID_IOS_EXPORT_METHODS)
            raise ConfigError(
                f"[ios.signing].export_method {self.ios.signing.export_method!r} is invalid (choose one of: {valid})."
            )

        if self.android.min_sdk < 21:
            raise ConfigError("[android].min_sdk must be at least 21 (Chaquopy requirement).")
        if self.android.target_sdk < self.android.min_sdk:
            raise ConfigError("[android].target_sdk must be >= min_sdk.")


# ======================================================================
# Parsing helpers
# ======================================================================


def _parse_ios(table: Mapping[str, Any]) -> IOSConfig:
    signing_table = _expect_table(table, "signing", optional=True, parent="ios")
    extra = table.get("extra_info_plist") or {}
    if extra and not isinstance(extra, dict):
        raise ConfigError("[ios].extra_info_plist must be a table.")
    return IOSConfig(
        deployment_target=_opt_str(table, "deployment_target") or "13.0",
        development_team=_opt_str(table, "development_team"),
        bundle_id=_opt_str(table, "bundle_id"),
        extra_info_plist=dict(extra),
        signing=IOSSigning(
            export_method=(_opt_str(signing_table, "export_method") or "development").lower(),
            provisioning_profile=_opt_str(signing_table, "provisioning_profile"),
        ),
    )


def _parse_android(table: Mapping[str, Any]) -> AndroidConfig:
    signing_table = _expect_table(table, "signing", optional=True, parent="android")
    cfg = AndroidConfig(
        min_sdk=_opt_int(table, "min_sdk", default=24),
        target_sdk=_opt_int(table, "target_sdk", default=34),
        compile_sdk=_opt_int(table, "compile_sdk", default=34),
        application_id=_opt_str(table, "application_id"),
        permissions=_opt_str_list(table, "permissions"),
        signing=AndroidSigning(
            keystore=_opt_str(signing_table, "keystore"),
            key_alias=_opt_str(signing_table, "key_alias"),
            store_password_env=_opt_str(signing_table, "store_password_env") or "PN_ANDROID_KEYSTORE_PASSWORD",
            key_password_env=_opt_str(signing_table, "key_password_env") or "PN_ANDROID_KEY_PASSWORD",
        ),
    )
    abis = _opt_str_list(table, "abi_filters")
    if abis:
        cfg.abi_filters = abis
    return cfg


def _expect_table(
    data: Mapping[str, Any], key: str, *, optional: bool = False, parent: Optional[str] = None
) -> Mapping[str, Any]:
    label = f"[{parent}.{key}]" if parent else f"[{key}]"
    if key not in data:
        if optional:
            return {}
        raise ConfigError(f"Missing required {label} table in {CONFIG_FILENAME}.")
    value = data[key]
    if not isinstance(value, Mapping):
        raise ConfigError(f"{label} must be a table.")
    return value


def _require_str(table: Mapping[str, Any], key: str, parent: str) -> str:
    if key not in table:
        raise ConfigError(f"Missing required '{key}' in [{parent}] ({CONFIG_FILENAME}).")
    value = table[key]
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"[{parent}].{key} must be a non-empty string.")
    return value.strip()


def _opt_str(table: Mapping[str, Any], key: str) -> Optional[str]:
    if key not in table:
        return None
    value = table[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"'{key}' must be a string (got {type(value).__name__}).")
    return value.strip() or None


def _opt_int(table: Mapping[str, Any], key: str, *, default: int) -> int:
    if key not in table:
        return default
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"'{key}' must be an integer (got {type(value).__name__}).")
    return value


def _opt_str_list(table: Mapping[str, Any], key: str) -> List[str]:
    if key not in table:
        return []
    value = table[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"'{key}' must be a list of strings.")
    return [item.strip() for item in value if item.strip()]


def _validate_app_id(app_id: str, *, allow_hyphen: bool = False) -> None:
    segments = app_id.split(".")
    if len(segments) < 2:
        raise ConfigError(f"app id {app_id!r} must be reverse-DNS with at least two segments (e.g. 'com.example.app').")
    for segment in segments:
        normalized = segment.replace("-", "_") if allow_hyphen else segment
        if not _APP_ID_SEGMENT.match(normalized):
            raise ConfigError(
                f"app id segment {segment!r} is invalid; use lowercase letters, digits and underscores, "
                "and start each segment with a letter."
            )
        if normalized in _JAVA_KEYWORDS:
            raise ConfigError(f"app id segment {segment!r} is a reserved word and cannot be used.")


def _validate_requirements(requirements: List[str]) -> None:
    for spec in requirements:
        pkg = re.split(r"[\[><=!;~ ]", spec, maxsplit=1)[0].strip()
        if pkg.lower().replace("-", "_") == "pythonnative":
            raise ConfigError(
                "Do not list 'pythonnative' in [requirements].packages; the pn CLI bundles it automatically."
            )


# ======================================================================
# Misc utilities
# ======================================================================


def entrypoint_to_module(entry_point: str) -> str:
    """Convert an ``entry_point`` path into an importable module path.

    ``"app/main.py"`` → ``"app.main"``. Returns ``"app.main"`` for empty
    or unusable input so callers always have a sane default.

    Args:
        entry_point: A path like ``"app/main.py"``.

    Returns:
        A dotted module path.
    """
    normalized = (entry_point or "").strip().replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    normalized = normalized.strip("/").replace("/", ".")
    return normalized or "app.main"


def render_default_toml(*, name: str, app_id: str, python_version: str = "3.11") -> str:
    """Render a starter ``pythonnative.toml`` for ``pn init``.

    Args:
        name: Project name.
        app_id: Reverse-DNS app identifier.
        python_version: Embedded CPython version.

    Returns:
        The TOML file contents as a string, with commented-out examples
        for the optional tables.
    """
    display = name.replace("_", " ").replace("-", " ").strip().title() or name
    return f"""# PythonNative project configuration.
# Docs: https://docs.pythonnative.com/guide/configuration/

[app]
id = "{app_id}"
name = "{name}"
display_name = "{display}"
version = "1.0.0"
build = 1
python_version = "{python_version}"
orientation = "portrait"        # portrait | landscape | all
entry_point = "app/main.py"

# Declare the device capabilities your app needs. A string becomes the
# iOS permission prompt text; `true` uses a sensible default.
# See: https://docs.pythonnative.com/guide/permissions/
[permissions]
# camera = "Scan receipts with your camera."
# location_when_in_use = "Show nearby stores."
# notifications = true
# face_id = "Unlock the app with Face ID."

# App icon and splash. Provide a 1024x1024 PNG icon; it is resized for
# every density/idiom automatically.
[assets]
# icon = "assets/icon.png"
# splash = "assets/splash.png"

# Third-party pip packages bundled into the app (pure-Python or, on
# Android, anything Chaquopy can build). Do NOT list "pythonnative".
[requirements]
packages = []

[ios]
deployment_target = "13.0"
# development_team = "ABCDE12345"
# bundle_id = "{app_id}"

[ios.signing]
export_method = "development"   # development | ad-hoc | app-store | enterprise
# provisioning_profile = "My App Distribution"

[android]
min_sdk = 24
target_sdk = 34
abi_filters = ["armeabi-v7a", "arm64-v8a", "x86", "x86_64"]

[android.signing]
# keystore = "release.keystore"
# key_alias = "{name}"
"""
