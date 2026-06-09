"""App project model and build system for PythonNative.

This package turns a declarative ``pythonnative.toml`` into real,
branded, installable native apps. It is the engine behind the ``pn``
CLI's ``run``, ``build``, and ``doctor`` commands, split into focused,
independently-testable modules:

- [`config`][pythonnative.project.config]: parse/validate the TOML into a
  typed [`AppConfig`][pythonnative.project.config.AppConfig].
- [`permissions`][pythonnative.project.permissions]: map declarative
  capabilities to native permission artifacts.
- [`android`][pythonnative.project.android] /
  [`ios`][pythonnative.project.ios]: configure the staged native
  templates for a specific app (identity, permissions, branding).
- [`icons`][pythonnative.project.icons]: generate icons and splash
  assets.
- [`runtime_assets`][pythonnative.project.runtime_assets]: acquire the
  embedded iOS CPython runtime.
- [`builder`][pythonnative.project.builder]: orchestrate staging,
  configuration, and the native toolchains.
- [`doctor`][pythonnative.project.doctor]: diagnose the local toolchain.

Most users interact with this package only through the ``pn`` CLI, but
the API is public and stable enough to script against.
"""

from .builder import (
    BuildArtifacts,
    Builder,
    BuildError,
    CommandResult,
    CommandRunner,
    PreparedProject,
    SubprocessRunner,
)
from .config import (
    AndroidConfig,
    AndroidSigning,
    AppConfig,
    ConfigError,
    IOSConfig,
    IOSSigning,
    entrypoint_to_module,
    render_default_toml,
)
from .permissions import CAPABILITIES, Capability, ResolvedPermissions, resolve_permissions

__all__ = [
    "AppConfig",
    "ConfigError",
    "IOSConfig",
    "IOSSigning",
    "AndroidConfig",
    "AndroidSigning",
    "entrypoint_to_module",
    "render_default_toml",
    "Capability",
    "CAPABILITIES",
    "ResolvedPermissions",
    "resolve_permissions",
    "Builder",
    "BuildError",
    "BuildArtifacts",
    "PreparedProject",
    "CommandRunner",
    "SubprocessRunner",
    "CommandResult",
]
