"""App-scoped file I/O.

[`FileSystem`][pythonnative.FileSystem] answers one question the
standard library can't, "where may this app write?", and then gets out
of the way: [`app_dir`][pythonnative.native_modules.file_system.FileSystem.app_dir]
comes from the native ``Device`` module, and
[`path`][pythonnative.native_modules.file_system.FileSystem.path] turns
an app-relative name into a ``pathlib.Path`` you use like any other.
The read/write helpers are thin conveniences over that path; they
raise the same ``OSError`` subclasses ``open`` and ``os`` do
(``FileNotFoundError``, ``PermissionError``, ...) rather than hiding
them behind ``None`` and ``False``.

Relative paths are resolved against ``app_dir``; absolute paths are used
as-is. Everything here is synchronous: it is local disk I/O on the
calling thread, exactly like the standard library.

Example:
    ```python
    from pythonnative import FileSystem

    FileSystem.write_text("notes/today.txt", "Hello, file system!")
    print(FileSystem.read_text("notes/today.txt"))

    # Or work with the Path directly:
    notes = FileSystem.path("notes")
    for entry in sorted(notes.iterdir()):
        print(entry.name)
    ```
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional, Union

from .registry import native_module

PathLike = Union[str, "os.PathLike[str]"]

_app_dir_cache: Optional[str] = None


class FileSystem:
    """App-scoped file I/O.

    Every helper accepts an absolute path or a path relative to
    [`app_dir`][pythonnative.native_modules.file_system.FileSystem.app_dir],
    and raises ``OSError`` (or a subclass) when the operation fails,
    like the standard library it wraps.
    """

    @staticmethod
    def app_dir() -> str:
        """Return the app's writable data directory.

        On Android the result is ``Context.getFilesDir()``. On iOS it is
        the app's Documents directory. Off device, without
        either runtime, a ``.pythonnative_data`` directory under the
        user's home folder is used. The value comes from the native
        ``Device`` module's ``info()`` and is cached after the first
        call.

        Returns:
            Absolute path to the app's data directory.
        """
        global _app_dir_cache
        if _app_dir_cache is None:
            info = native_module("Device").call("info")
            path = info.get("app_dir") if isinstance(info, dict) else None
            _app_dir_cache = str(path) if path else os.path.join(os.path.expanduser("~"), ".pythonnative_data")
        return _app_dir_cache

    @staticmethod
    def path(path: PathLike = "") -> Path:
        """Resolve ``path`` against ``app_dir`` and return it as a ``pathlib.Path``.

        Absolute paths are returned unchanged. With no argument, returns
        ``app_dir`` itself.
        """
        candidate = Path(path)
        return candidate if candidate.is_absolute() else Path(FileSystem.app_dir()) / candidate

    @staticmethod
    def read_text(path: PathLike, encoding: str = "utf-8") -> str:
        """Read a text file; raises ``FileNotFoundError`` and friends like ``open`` does."""
        return FileSystem.path(path).read_text(encoding=encoding)

    @staticmethod
    def write_text(path: PathLike, content: str, encoding: str = "utf-8") -> None:
        """Write a text file, creating parent directories as needed."""
        target = FileSystem.path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)

    @staticmethod
    def read_bytes(path: PathLike) -> bytes:
        """Read a binary file."""
        return FileSystem.path(path).read_bytes()

    @staticmethod
    def write_bytes(path: PathLike, data: bytes) -> None:
        """Write a binary file, creating parent directories as needed."""
        target = FileSystem.path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    @staticmethod
    def exists(path: PathLike) -> bool:
        """Return whether a file or directory exists."""
        return FileSystem.path(path).exists()

    @staticmethod
    def delete(path: PathLike, *, missing_ok: bool = False) -> None:
        """Delete a single file.

        Args:
            path: Absolute or ``app_dir``-relative path.
            missing_ok: Ignore a missing file instead of raising
                ``FileNotFoundError`` (same as ``Path.unlink``).
        """
        FileSystem.path(path).unlink(missing_ok=missing_ok)

    @staticmethod
    def list_dir(path: PathLike = "") -> List[str]:
        """Return the entry names in a directory (``app_dir`` by default), sorted."""
        return sorted(entry.name for entry in FileSystem.path(path).iterdir())

    @staticmethod
    def get_size(path: PathLike) -> int:
        """Return a file's size in bytes."""
        return FileSystem.path(path).stat().st_size

    @staticmethod
    def ensure_dir(path: PathLike) -> Path:
        """Create a directory (and any missing parents) if needed; returns its ``Path``."""
        target = FileSystem.path(path)
        target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def join(*parts: Any) -> str:
        """Join path components with the OS separator (``os.path.join`` over ``str(part)``)."""
        return os.path.join(*[str(p) for p in parts])
