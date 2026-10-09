"""Sync pure-Python packages from the developer's environment to dev clients.

PythonNative Go bundles no third-party packages, and a project's own
debug build bundles the wheels its ``[requirements]`` named when it was
built. The dev server fills the gap from the environment ``pn start`` runs
in, which the browser preview already needs: it resolves ``[requirements]``
(and their dependencies) against the installed distributions and sends a
client every pure-Python distribution its bundle lacks. The client writes
them into its overlay's ``site-packages``.

A distribution with compiled extension modules can't be synced: Go can't
run that project, and a debug build must be rebuilt to include it.
``debugpy`` is the exception: its compiled modules are optional speedups,
so the debugger syncs its Python sources alone.
"""

from __future__ import annotations

import importlib.metadata as metadata
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

__all__ = [
    "BINARY_SUFFIXES",
    "HostDistribution",
    "distribution_files",
    "find_distribution",
    "requirement_name",
    "resolve",
]

BINARY_SUFFIXES = (".so", ".pyd", ".dylib", ".dll", ".exe")
"""File suffixes that make a distribution native-only."""

_SKIPPED_DIRS = {"__pycache__"}
_SKIPPED_SUFFIXES = (".pyc", ".pyo")
_METADATA_FILES = {"METADATA", "top_level.txt", "entry_points.txt", "WHEEL"}
_OPTIONAL_NATIVE = {
    # debugpy falls back to pure-Python tracing; its attach helpers inject
    # into other processes, which a dev client never does.
    "debugpy": ("pydevd_attach_to_process",),
}
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name: str) -> str:
    """PEP 503 normalization: ``Foo_Bar.baz`` becomes ``foo-bar-baz``."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str:
    """The distribution a ``[requirements]`` entry or ``Requires-Dist`` line names."""
    text = requirement.strip()
    if text.endswith(".whl"):
        return Path(text).name.split("-", 1)[0]
    match = _NAME_RE.match(text)
    return match.group(1) if match else ""


@dataclass
class HostDistribution:
    """One installed distribution, as the dev server would sync it.

    Attributes:
        name: The distribution's name.
        version: Its installed version.
        files: ``(path relative to site-packages, absolute path)`` pairs.
        binary: Compiled files that make it native-only.
        site: The ``site-packages`` directory it's installed in.
    """

    name: str
    version: str
    files: List[Tuple[str, Path]] = field(default_factory=list)
    binary: List[str] = field(default_factory=list)
    site: Optional[Path] = None

    @property
    def pure(self) -> bool:
        """Whether every module is Python source."""
        return not self.binary

    def size(self) -> int:
        """Total bytes the sync would send."""
        total = 0
        for _rel, path in self.files:
            try:
                total += path.stat().st_size
            except OSError:
                pass
        return total


def find_distribution(name: str) -> Optional[metadata.Distribution]:
    """The installed distribution called ``name`` (any normalization), or ``None``."""
    try:
        return metadata.distribution(name)
    except metadata.PackageNotFoundError:
        pass
    wanted = normalize(name)
    for dist in metadata.distributions():
        dist_name = dist.metadata.get("Name") if dist.metadata is not None else None
        if dist_name and normalize(str(dist_name)) == wanted:
            return dist
    return None


def distribution_files(dist: metadata.Distribution, *, sources_only: bool = False) -> HostDistribution:
    """Classify a distribution's files for syncing.

    Args:
        dist: An installed distribution.
        sources_only: Drop compiled files instead of reporting them
            (``debugpy``).
    """
    name = str(dist.metadata.get("Name") or "") if dist.metadata is not None else ""
    result = HostDistribution(name=name, version=str(dist.version))
    skipped_dirs = set(_OPTIONAL_NATIVE.get(normalize(name), ()))
    for entry in dist.files or []:
        rel = str(entry).replace(os.sep, "/")
        parts = rel.split("/")
        if rel.startswith("../") or any(part in _SKIPPED_DIRS for part in parts):
            continue
        if any(part in skipped_dirs for part in parts):
            continue
        if rel.endswith(_SKIPPED_SUFFIXES):
            continue
        if parts[0].endswith(".dist-info"):
            if parts[-1] not in _METADATA_FILES:
                continue
        path = Path(str(dist.locate_file(entry)))
        if result.site is None and not parts[0].endswith(".dist-info"):
            # ``locate_file`` joins the entry to the site directory.
            site = path
            for _ in parts:
                site = site.parent
            result.site = site
        if rel.lower().endswith(BINARY_SUFFIXES):
            if sources_only:
                continue
            result.binary.append(rel)
            continue
        if path.is_file():
            result.files.append((rel, path))
    return result


def _dependencies(dist: metadata.Distribution) -> List[str]:
    names: List[str] = []
    for line in dist.requires or []:
        requirement, _, marker = line.partition(";")
        # Extras-only dependencies aren't part of the base install.
        if "extra" in marker:
            continue
        name = requirement_name(requirement)
        if name:
            names.append(name)
    return names


def resolve(requirements: Sequence[str], *, skip: Iterable[str] = ()) -> Tuple[List[HostDistribution], List[str]]:
    """Resolve ``requirements`` and their dependencies in this environment.

    Dependencies that aren't installed are assumed to be excluded by an
    environment marker and are skipped.

    Args:
        requirements: ``[requirements].packages`` entries.
        skip: Distribution names the client already bundles, and
            ``pythonnative`` itself.

    Returns:
        ``(distributions, missing)``: the installed closure (excluding
        ``skip``), and requirement names that aren't installed at all.
    """
    skipped: Set[str] = {normalize(name) for name in skip} | {"pythonnative"}
    found: Dict[str, HostDistribution] = {}
    missing: List[str] = []
    queue: List[Tuple[str, bool]] = [(requirement_name(req), True) for req in requirements if requirement_name(req)]
    seen: Set[str] = set()
    while queue:
        name, explicit = queue.pop(0)
        key = normalize(name)
        if key in seen:
            continue
        seen.add(key)
        dist = find_distribution(name)
        if dist is None:
            if explicit:
                missing.append(name)
            continue
        if key not in skipped:
            found[key] = distribution_files(dist)
        queue.extend((dep, False) for dep in _dependencies(dist))
    return list(found.values()), missing
