"""Which parts of the ``pythonnative`` package an app bundle carries.

Every build copies the running ``pythonnative`` package into the native
project (Chaquopy's source root on Android, one ``app_packages`` slice
per SDK on iOS). Native sources, templates, host-only extension modules,
and caches never ship. Debug builds keep everything else, because they
are dev clients: they need the dev client, the WebSocket code it uses,
and Fast Refresh.

Release builds also drop the development-only modules listed in
[`DEV_ONLY_PATHS`][pythonnative.project.bundle.DEV_ONLY_PATHS]: the
``pn`` CLI and build tooling, the dev server and browser preview, the dev
client and Fast Refresh, the test helpers, and the SDK code generators.
``tests/test_release_packaging.py`` checks that nothing left in a release
bundle imports them.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, List, Set

__all__ = ["DEV_ONLY_PATHS", "copy_library", "library_ignore"]

_ALWAYS_IGNORED = ("templates", "native", "*.so", "__pycache__", "*.pyc", "*.pyo")

DEV_ONLY_PATHS = (
    "cli",
    "project",
    "devserver",
    "testing",
    "devclient.py",
    "hot_reload.py",
    "refresh.py",
    "preview.py",
    "bridge/web.py",
    "sdk/codegen.py",
    "sdk/contract_codegen.py",
    "sdk/module_codegen.py",
    "sdk/templates",
)
"""Package-relative paths (POSIX separators) that release bundles omit."""


def library_ignore(lib_root: Path, *, release: bool) -> Callable[[str, List[str]], Set[str]]:
    """A ``shutil.copytree`` ignore hook for copying the package at ``lib_root``.

    Args:
        lib_root: The ``pythonnative`` package directory being copied.
        release: Also skip [`DEV_ONLY_PATHS`][pythonnative.project.bundle.DEV_ONLY_PATHS].
    """
    base = shutil.ignore_patterns(*_ALWAYS_IGNORED)
    root = os.path.abspath(lib_root)
    dev_only = set(DEV_ONLY_PATHS)

    def ignore(directory: str, names: List[str]) -> Set[str]:
        ignored = set(base(directory, names))
        if release:
            rel = os.path.relpath(os.path.abspath(directory), root).replace(os.sep, "/")
            prefix = "" if rel == "." else rel + "/"
            ignored.update(name for name in names if prefix + name in dev_only)
        return ignored

    return ignore


def copy_library(lib_root: Path, destination: Path, *, release: bool) -> None:
    """Replace ``destination`` with a copy of the package at ``lib_root``.

    The destination is removed first, so modules a previous debug build
    staged can't linger in a release bundle.
    """
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(lib_root, destination, ignore=library_ignore(lib_root, release=release))
