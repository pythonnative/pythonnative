"""Decide whether a dev client can run the project ``pn start`` serves.

A dev client syncs Python sources, never native code, so the code it was
built with has to match the project's:

- **PythonNative Go** carries the framework and every built-in native
  module, nothing else. It runs a project when its framework version
  equals the host's (the bundled ``pythonnative`` package can't be
  replaced while it runs), the project adds no native plugins, and every
  package the project needs is pure Python.
- **A project's debug build** carries the framework and plugins it was
  built with. The framework version and the plugin set must still match;
  otherwise ``pn run`` must rebuild it.

[`check`][pythonnative.devserver.compat.check] returns an
[`Incompatibility`][pythonnative.devserver.compat.Incompatibility] with a
reason and the command that fixes it, which the server sends instead of a
sync and the device shows.
"""

from __future__ import annotations

import importlib.metadata as metadata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from . import packages as packages_mod

__all__ = ["Incompatibility", "ProjectRuntime", "check", "project_runtime"]

SESSION_PROTOCOL = 2


@dataclass(frozen=True)
class Incompatibility:
    """Why a client can't run the project, and how to fix it."""

    reason: str
    fix: str

    def to_message(self) -> Dict[str, Any]:
        """The ``incompatible`` message sent to the client."""
        return {"type": "incompatible", "reason": self.reason, "fix": self.fix}


@dataclass
class ProjectRuntime:
    """What the project needs from a dev client.

    Attributes:
        pythonnative: The host's framework version.
        protocol: The host's bridge protocol version.
        plugins: Native plugin names the project uses.
        requirements: ``[requirements].packages``.
        native_packages: Required distributions with compiled code.
        missing_packages: Requirements that aren't installed on the host.
    """

    pythonnative: str
    protocol: int
    plugins: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    native_packages: List[str] = field(default_factory=list)
    missing_packages: List[str] = field(default_factory=list)

    @property
    def go_compatible(self) -> bool:
        """Whether PythonNative Go can run this project."""
        return not self.plugins and not self.native_packages


def _framework_version() -> str:
    try:
        return metadata.version("pythonnative")
    except metadata.PackageNotFoundError:
        from .. import __version__

        return __version__


def _plugin_names(requirements: Sequence[str], plugin_paths: Sequence[Any]) -> List[str]:
    """Plugins from ``[plugins].paths`` and from required distributions' entry points."""
    names: List[str] = []
    wanted = {packages_mod.normalize(packages_mod.requirement_name(req)) for req in requirements}
    try:
        for entry in metadata.entry_points(group="pythonnative.plugins"):
            dist = getattr(entry, "dist", None)
            dist_name = getattr(dist, "name", None) if dist is not None else None
            if dist_name and packages_mod.normalize(str(dist_name)) in wanted:
                names.append(entry.name)
    except Exception:
        pass
    for path in plugin_paths:
        try:
            from ..project.plugins import load_plugin

            names.append(load_plugin(path).name)
        except Exception:
            names.append(str(path))
    return sorted(set(names))


def project_runtime(config: Any = None) -> ProjectRuntime:
    """Describe what the project at ``config`` (an ``AppConfig``, or ``None``) needs."""
    from ..bridge.commits import PROTOCOL_VERSION

    requirements = list(getattr(config, "requirements", ()) or ())
    plugin_paths = [config.resolve_path(p) for p in getattr(config, "plugin_paths", ()) or ()] if config else []
    distributions, missing = packages_mod.resolve(requirements)
    return ProjectRuntime(
        pythonnative=_framework_version(),
        protocol=PROTOCOL_VERSION,
        plugins=_plugin_names(requirements, plugin_paths),
        requirements=requirements,
        native_packages=sorted(dist.name for dist in distributions if not dist.pure),
        missing_packages=missing,
    )


def _platform_word(platform: str) -> str:
    return platform if platform in ("ios", "android") else "<platform>"


def check(hello: Dict[str, Any], project: ProjectRuntime) -> Optional[Incompatibility]:
    """Return why the client that sent ``hello`` can't run ``project``, or ``None``."""
    kind = str(hello.get("client") or "app")
    platform = _platform_word(str(hello.get("platform") or ""))
    rebuild = f"Rebuild it with `pn run {platform} --rebuild`."
    reinstall = f"Install the matching version with `pn go {platform}`."
    if hello.get("session") != SESSION_PROTOCOL:
        return Incompatibility(
            "This dev client was built for an older version of PythonNative's dev server.",
            reinstall if kind == "go" else rebuild,
        )
    runtime = hello.get("runtime") if isinstance(hello.get("runtime"), dict) else {}
    assert isinstance(runtime, dict)
    client_version = str(runtime.get("pythonnative") or "")
    if runtime.get("protocol") != project.protocol or (client_version and client_version != project.pythonnative):
        if kind == "go":
            return Incompatibility(
                f"PythonNative Go {client_version or '(unknown version)'} can't run a project that uses "
                f"PythonNative {project.pythonnative}.",
                reinstall,
            )
        return Incompatibility(
            f"This development build contains PythonNative {client_version or '(unknown version)'}, but the "
            f"project uses {project.pythonnative}.",
            rebuild,
        )
    if kind == "go":
        if project.plugins:
            return Incompatibility(
                f"This project adds native code ({', '.join(project.plugins)}), which PythonNative Go doesn't "
                "include.",
                f"Build its development app with `pn run {platform}`.",
            )
        if project.native_packages:
            return Incompatibility(
                f"This project needs {', '.join(project.native_packages)}, which contain compiled code that "
                "PythonNative Go doesn't include.",
                f"Build its development app with `pn run {platform}`.",
            )
        return None
    built_with = sorted(str(name) for name in runtime.get("plugins") or [])
    if built_with != sorted(project.plugins):
        added = sorted(set(project.plugins) - set(built_with))
        removed = sorted(set(built_with) - set(project.plugins))
        changes = []
        if added:
            changes.append(f"added {', '.join(added)}")
        if removed:
            changes.append(f"removed {', '.join(removed)}")
        return Incompatibility(
            f"The project's native plugins changed since this build ({'; '.join(changes)}).", rebuild
        )
    return None
