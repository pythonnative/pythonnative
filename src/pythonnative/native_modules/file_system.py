"""Cross-platform app-scoped file I/O.

Provides static helpers for reading, writing, and deleting files in the
app's sandboxed storage area. Relative paths are resolved against
[`FileSystem.app_dir`][pythonnative.native_modules.file_system.FileSystem.app_dir];
absolute paths are used as-is.

Example:
    ```python
    from pythonnative import FileSystem

    FileSystem.write_text("notes/today.txt", "Hello, file system!")
    print(FileSystem.read_text("notes/today.txt"))
    ```
"""

import os
from typing import Any, Optional

from ..utils import IS_ANDROID


class FileSystem:
    """App-scoped file I/O.

    Every instance method operates on either an absolute path or a path
    relative to
    [`app_dir`][pythonnative.native_modules.file_system.FileSystem.app_dir].
    Errors are swallowed and reported as falsy return values (`None`
    for readers, `False` for writers) so callers can treat the API as
    best-effort.
    """

    @staticmethod
    def app_dir() -> str:
        """Return the app's writable data directory.

        On Android the result is `Context.getFilesDir()`. On iOS it is
        the user's Documents directory. On a desktop machine without
        either runtime, a `.pythonnative_data` directory is created
        under the user's home folder.

        Returns:
            Absolute path to the app's data directory.
        """
        if IS_ANDROID:
            try:
                from ..utils import get_android_context

                return str(get_android_context().getFilesDir().getAbsolutePath())
            except Exception:
                pass
        else:
            try:
                from rubicon.objc import ObjCClass

                NSSearchPathForDirectoriesInDomains = ObjCClass(
                    "NSFileManager"
                ).defaultManager.URLsForDirectory_inDomains_
                docs = NSSearchPathForDirectoriesInDomains(9, 1)  # NSDocumentDirectory, NSUserDomainMask
                if docs and docs.count > 0:
                    return str(docs.objectAtIndex_(0).path)
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), ".pythonnative_data")

    @staticmethod
    def read_text(path: str, encoding: str = "utf-8") -> Optional[str]:
        """Read a text file.

        Args:
            path: Absolute path or path relative to
                [`app_dir`][pythonnative.native_modules.file_system.FileSystem.app_dir].
            encoding: Text encoding (default `"utf-8"`).

        Returns:
            File contents as a `str`, or `None` if the file cannot be
            read.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            with open(full, encoding=encoding) as f:
                return f.read()
        except OSError:
            return None

    @staticmethod
    def write_text(path: str, content: str, encoding: str = "utf-8") -> bool:
        """Write a text file, creating parent directories as needed.

        Args:
            path: Absolute or `app_dir`-relative path.
            content: String to write.
            encoding: Text encoding (default `"utf-8"`).

        Returns:
            `True` on success, `False` on `OSError`.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding=encoding) as f:
                f.write(content)
            return True
        except OSError:
            return False

    @staticmethod
    def exists(path: str) -> bool:
        """Return whether a file or directory exists.

        Args:
            path: Absolute or `app_dir`-relative path.

        Returns:
            `True` if the path exists.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        return os.path.exists(full)

    @staticmethod
    def delete(path: str) -> bool:
        """Delete a single file.

        Args:
            path: Absolute or `app_dir`-relative path.

        Returns:
            `True` on success, `False` on `OSError`.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            os.remove(full)
            return True
        except OSError:
            return False

    @staticmethod
    def list_dir(path: str = "") -> list:
        """List the entries in a directory.

        Args:
            path: Absolute or `app_dir`-relative path. Defaults to the
                app data directory itself.

        Returns:
            A list of entry names, or an empty list on error.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            return os.listdir(full)
        except OSError:
            return []

    @staticmethod
    def read_bytes(path: str) -> Optional[bytes]:
        """Read a binary file.

        Args:
            path: Absolute or `app_dir`-relative path.

        Returns:
            File contents as `bytes`, or `None` if the file cannot be
            read.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            with open(full, "rb") as f:
                return f.read()
        except OSError:
            return None

    @staticmethod
    def write_bytes(path: str, data: bytes) -> bool:
        """Write a binary file, creating parent directories as needed.

        Args:
            path: Absolute or `app_dir`-relative path.
            data: Bytes to write.

        Returns:
            `True` on success, `False` on `OSError`.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(data)
            return True
        except OSError:
            return False

    @staticmethod
    def get_size(path: str) -> Optional[int]:
        """Return file size in bytes.

        Args:
            path: Absolute or `app_dir`-relative path.

        Returns:
            File size in bytes, or `None` if the file is missing or
            unreadable.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            return os.path.getsize(full)
        except OSError:
            return None

    @staticmethod
    def ensure_dir(path: str) -> bool:
        """Create a directory (and any missing parents) idempotently.

        Args:
            path: Absolute or `app_dir`-relative path.

        Returns:
            `True` on success or if the directory already exists.
        """
        full = path if os.path.isabs(path) else os.path.join(FileSystem.app_dir(), path)
        try:
            os.makedirs(full, exist_ok=True)
            return True
        except OSError:
            return False

    @staticmethod
    def join(*parts: Any) -> str:
        """Join path components using the OS separator.

        Equivalent to `os.path.join(*map(str, parts))`. Provided as a
        convenience so callers do not need to import `os.path`
        directly.

        Args:
            *parts: Path components (each coerced to `str`).

        Returns:
            The joined path string.
        """
        return os.path.join(*[str(p) for p in parts])
