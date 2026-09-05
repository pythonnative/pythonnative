"""Source snapshots and change detection for the dev server.

The dev server treats the project's ``app/`` directory as a content-
addressed tree: every dev client gets the same manifest (relative path
to SHA-256), so a client can tell exactly which files it is missing
after a reconnect, and a change notification can carry the new bytes.

[`FileWatcher`][pythonnative.devserver.watcher.FileWatcher] polls the
tree with ``os.stat`` rather than a native file-system event API so it
behaves identically on every host OS without a dependency; the poll
interval is short enough that saves feel instant.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

__all__ = ["FileWatcher", "SourceSnapshot", "SourceChange", "is_synced_file", "snapshot_sources"]

MAX_SYNC_FILE_BYTES = 8 * 1024 * 1024
"""Files larger than this are left out of the sync set (they belong in a real build)."""

_IGNORED_DIRS = {"__pycache__", ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
_IGNORED_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo", ".tmp", "~")
_IGNORED_NAMES = {".DS_Store", "Thumbs.db"}


def is_synced_file(rel_path: str) -> bool:
    """Whether a file under ``app/`` takes part in dev sync.

    Editor swap files, byte-code caches, and VCS metadata are skipped;
    everything else (Python modules and data files an app reads at
    runtime) is synced so the on-device overlay mirrors the source tree.
    """
    parts = rel_path.replace("\\", "/").split("/")
    if any(part in _IGNORED_DIRS for part in parts[:-1]):
        return False
    name = parts[-1]
    if not name or name in _IGNORED_NAMES:
        return False
    if name.startswith(".#"):
        return False
    return not name.endswith(_IGNORED_SUFFIXES)


@dataclass(frozen=True)
class SourceSnapshot:
    """The state of a source tree at one instant.

    Attributes:
        root: Absolute directory the relative paths are resolved against
            (the project root; paths start with ``app/``).
        files: ``relative_path -> sha256`` for every synced file.
        mtimes: ``relative_path -> (mtime_ns, size)`` used to skip
            re-hashing unchanged files between polls.
        version: A digest of the whole tree, stable across processes
            for identical contents.
    """

    root: str
    files: Dict[str, str] = field(default_factory=dict)
    mtimes: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    version: str = ""

    def read(self, rel_path: str) -> Optional[bytes]:
        """Return the current bytes of ``rel_path`` (``None`` if it is gone)."""
        try:
            with open(os.path.join(self.root, rel_path), "rb") as handle:
                return handle.read()
        except OSError:
            return None

    def diff(self, other: "SourceSnapshot") -> "SourceChange":
        """Describe how to get from ``self`` to ``other``."""
        changed = sorted(path for path, digest in other.files.items() if self.files.get(path) != digest)
        removed = sorted(path for path in self.files if path not in other.files)
        return SourceChange(changed=changed, removed=removed, version=other.version)


@dataclass(frozen=True)
class SourceChange:
    """Paths that changed (added or modified) and paths that disappeared."""

    changed: List[str]
    removed: List[str]
    version: str

    def __bool__(self) -> bool:
        return bool(self.changed or self.removed)


def _tree_version(files: Dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[path].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]


def snapshot_sources(
    root: str,
    subdirs: Sequence[str] = ("app",),
    *,
    previous: Optional[SourceSnapshot] = None,
) -> SourceSnapshot:
    """Hash every synced file under ``root/<subdir>`` for each of ``subdirs``.

    Args:
        root: Project root.
        subdirs: Directories (relative to ``root``) to include.
        previous: An earlier snapshot; files whose ``(mtime, size)`` are
            unchanged reuse their digest instead of being re-read.
    """
    files: Dict[str, str] = {}
    mtimes: Dict[str, Tuple[int, int]] = {}
    prev_mtimes = previous.mtimes if previous is not None else {}
    prev_files = previous.files if previous is not None else {}
    for subdir in subdirs:
        base = os.path.join(root, subdir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in _IGNORED_DIRS)
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                if not is_synced_file(rel):
                    continue
                try:
                    stat = os.stat(full)
                except OSError:
                    continue
                if stat.st_size > MAX_SYNC_FILE_BYTES:
                    continue
                key = (stat.st_mtime_ns, stat.st_size)
                if prev_mtimes.get(rel) == key and rel in prev_files:
                    files[rel] = prev_files[rel]
                    mtimes[rel] = key
                    continue
                try:
                    with open(full, "rb") as handle:
                        data = handle.read()
                except OSError:
                    continue
                files[rel] = hashlib.sha256(data).hexdigest()
                mtimes[rel] = key
    return SourceSnapshot(root=os.path.abspath(root), files=files, mtimes=mtimes, version=_tree_version(files))


class FileWatcher:
    """Poll a source tree and report changes on a background thread.

    Args:
        root: Project root.
        on_change: Called with a
            [`SourceChange`][pythonnative.devserver.watcher.SourceChange]
            and the new snapshot after every poll that found changes.
        subdirs: Directories under ``root`` to watch.
        interval: Seconds between polls.
        settle: Seconds a change must be stable before it is reported,
            so an editor's write-then-rename or a multi-file save lands
            as one reload instead of several.
    """

    def __init__(
        self,
        root: str,
        on_change: Callable[[SourceChange, SourceSnapshot], None],
        *,
        subdirs: Sequence[str] = ("app",),
        interval: float = 0.25,
        settle: float = 0.08,
    ) -> None:
        self.root = os.path.abspath(root)
        self.on_change = on_change
        self.subdirs = tuple(subdirs)
        self.interval = interval
        self.settle = settle
        self._snapshot = snapshot_sources(self.root, self.subdirs)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    @property
    def snapshot(self) -> SourceSnapshot:
        """The most recent snapshot."""
        with self._lock:
            return self._snapshot

    def start(self) -> None:
        """Start polling on a daemon thread (idempotent)."""
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="pn-file-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop polling and join the thread."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=max(1.0, self.interval * 4))

    def poll(self) -> Optional[SourceChange]:
        """Scan once and return the change since the last scan (or ``None``)."""
        with self._lock:
            previous = self._snapshot
        current = snapshot_sources(self.root, self.subdirs, previous=previous)
        change = previous.diff(current)
        if not change:
            return None
        if self.settle > 0:
            # Wait for the tree to stop changing so partial writes never ship.
            deadline = time.monotonic() + max(self.settle * 20, 2.0)
            while time.monotonic() < deadline:
                time.sleep(self.settle)
                settled = snapshot_sources(self.root, self.subdirs, previous=current)
                if settled.version == current.version:
                    break
                current = settled
            change = previous.diff(current)
            if not change:
                return None
        with self._lock:
            self._snapshot = current
        return change

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                change = self.poll()
            except Exception:
                continue
            if change is None:
                continue
            try:
                self.on_change(change, self.snapshot)
            except Exception:
                pass


def modules_for_paths(paths: Sequence[str]) -> List[str]:
    """Map synced ``.py`` paths (``app/screens/home.py``) to dotted modules."""
    modules: List[str] = []
    seen: Set[str] = set()
    for path in paths:
        norm = path.replace("\\", "/")
        if not norm.endswith(".py"):
            continue
        parts = norm[:-3].split("/")
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts or not all(part.isidentifier() for part in parts):
            continue
        dotted = ".".join(parts)
        if dotted not in seen:
            seen.add(dotted)
            modules.append(dotted)
    return modules
