"""Native build fingerprints: know when ``pn run`` can skip the toolchain.

A debug build only has to be rebuilt when one of its *native inputs*
changes: ``pythonnative.toml``, the bundled native template, the
``pythonnative`` package itself, project-local native plugins, or the
build flavor (platform, SDK, release). Edits under ``app/`` don't count;
the dev server syncs those into the running app and Fast Refresh applies
them, exactly as Metro does for a React Native debug build.

[`compute`][pythonnative.project.fingerprint.compute] hashes those
inputs into one hex digest. ``pn run`` writes it next to the build
after a successful toolchain run (see
[`write_stamp`][pythonnative.project.fingerprint.write_stamp]) and, when
the digest is unchanged and a dev server is running to deliver the
latest sources, reinstalls the previous artifact instead of staging and
compiling again.

The hash covers file *contents*, not mtimes, so touching a file or
re-cloning the repository doesn't invalidate a build.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from .config import CONFIG_FILENAME, AppConfig

__all__ = ["STAMP_NAME", "compute", "hash_tree", "read_stamp", "write_stamp"]

STAMP_NAME = ".pn-native-fingerprint.json"
"""File written into ``build/<platform>/`` after a successful native build."""

_IGNORED_DIRS = {
    "__pycache__",
    ".git",
    ".gradle",
    ".build",
    ".swiftpm",
    "build",
    "DerivedData",
    "xcuserdata",
    "node_modules",
    ".venv",
}
_IGNORED_SUFFIXES = (".pyc", ".pyo", ".DS_Store")


def hash_tree(root: Path, *, into: Optional["hashlib._Hash"] = None) -> str:
    """Hash every file under ``root`` (relative path + contents), deterministically.

    Build outputs, caches, and bytecode are skipped so a checkout that
    has been built hashes the same as a fresh one.

    Args:
        root: Directory (or single file) to hash. A missing path hashes
            as the empty tree.
        into: An existing hasher to feed instead of creating one.

    Returns:
        The hex digest (of ``into`` when given).
    """
    hasher = into or hashlib.sha256()
    if root.is_file():
        _feed_file(hasher, root.name, root)
        return hasher.hexdigest()
    if not root.is_dir():
        return hasher.hexdigest()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORED_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(_IGNORED_SUFFIXES):
                continue
            path = Path(dirpath) / name
            if path.is_symlink() and not path.exists():
                continue
            _feed_file(hasher, str(path.relative_to(root)).replace(os.sep, "/"), path)
    return hasher.hexdigest()


def _feed_file(hasher: "hashlib._Hash", rel: str, path: Path) -> None:
    hasher.update(rel.encode("utf-8"))
    hasher.update(b"\0")
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 16), b""):
                hasher.update(chunk)
    except OSError:
        hasher.update(b"<unreadable>")
    hasher.update(b"\0")


def compute(
    config: AppConfig,
    platform: str,
    *,
    template_root: Path,
    lib_root: Path,
    release: bool = False,
    ios_sdks: Sequence[str] = (),
    extra: Optional[Dict[str, str]] = None,
) -> str:
    """Digest every native input of a build.

    Args:
        config: The loaded project configuration (its file is hashed).
        platform: ``"android"`` or ``"ios"``.
        template_root: The bundled native template directory.
        lib_root: The ``pythonnative`` package directory that gets bundled.
        release: Release builds are distinct from debug builds.
        ios_sdks: The iOS SDK slices being staged.
        extra: Additional key/value inputs (host arch, tool versions).

    Returns:
        A hex SHA-256 digest.
    """
    hasher = hashlib.sha256()
    header = {
        "platform": platform,
        "release": bool(release),
        "ios_sdks": sorted(ios_sdks),
        "python": f"{sys.version_info[0]}.{sys.version_info[1]}",
        "extra": dict(sorted((extra or {}).items())),
    }
    hasher.update(json.dumps(header, sort_keys=True).encode("utf-8"))
    hasher.update(b"\0config\0")
    hash_tree(config.project_root / CONFIG_FILENAME, into=hasher)
    hasher.update(b"\0template\0")
    hash_tree(template_root, into=hasher)
    hasher.update(b"\0lib\0")
    hash_tree(lib_root, into=hasher)
    for plugin_path in _plugin_paths(config):
        hasher.update(b"\0plugin:" + str(plugin_path).encode("utf-8") + b"\0")
        hash_tree(plugin_path, into=hasher)
    return hasher.hexdigest()


def _plugin_paths(config: AppConfig) -> Iterable[Path]:
    for raw in getattr(config, "plugin_paths", ()) or ():
        try:
            yield config.resolve_path(raw)
        except Exception:
            continue


def read_stamp(build_dir: Path) -> Optional[Dict[str, str]]:
    """Return the stamp written by the last successful build, or ``None``."""
    path = build_dir / STAMP_NAME
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "fingerprint" not in data:
        return None
    return {str(k): str(v) for k, v in data.items()}


def write_stamp(build_dir: Path, fingerprint: str, *, artifact: Optional[Path] = None) -> None:
    """Record ``fingerprint`` (and the artifact it produced) for the next ``pn run``."""
    build_dir.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, str] = {"fingerprint": fingerprint}
    if artifact is not None:
        payload["artifact"] = str(artifact)
    with open(build_dir / STAMP_NAME, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
