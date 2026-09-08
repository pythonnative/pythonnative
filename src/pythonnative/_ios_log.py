"""Route Python `sys.stdout`/`sys.stderr` through fd 2 on iOS.

When an app is launched via `xcrun simctl launch --console-pty`
(what `pn run ios` does), the simulator attaches the caller's
terminal to the app's stderr, which is the same channel `NSLog` and
`os_log` write to. Python `print()` calls, however, go to
`sys.stdout` (fd 1), and for reasons specific to how CPython's
embedded framework is started on the iOS Simulator that descriptor
does not reach the attached console. As a result, users see
Swift-side `NSLog` output but never their own `print()` output.

Redirecting `sys.stdout` and `sys.stderr` at a Python level to write
straight to fd 2 is a small, reliable fix: fd 2 *is* visible to
`simctl` (that is exactly how `NSLog` reaches the terminal), so
Python output lands next to the Swift logs with correct ordering.

This module is intentionally self-contained (no bridge or
platform-specific C bindings required), so it is safe to import
early during `pythonnative` package initialization.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable

_STDERR_FD = 2


class _StderrStream:
    """Minimal text-mode file-like that writes UTF-8 bytes to fd 2.

    Write-through (no buffering), so a `print()` call appears in the
    terminal immediately. That matches user expectations for an
    interactive "run on simulator" log stream.
    """

    encoding = "utf-8"
    errors = "replace"
    mode = "w"
    name = "<stderr>"

    def write(self, s: str) -> int:
        if not s:
            return 0
        data = s.encode(self.encoding, self.errors)
        try:
            return os.write(_STDERR_FD, data)
        except OSError:
            return 0

    def writelines(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        # os.write is unbuffered; nothing to flush.
        return None

    def isatty(self) -> bool:
        try:
            return os.isatty(_STDERR_FD)
        except OSError:
            return False

    def fileno(self) -> int:
        return _STDERR_FD

    def close(self) -> None:
        # Don't actually close fd 2.
        return None

    @property
    def closed(self) -> bool:
        return False


_installed = False


def install() -> None:
    """Swap `sys.stdout` and `sys.stderr` for fd-2 writers.

    Idempotent: only the first call has effect.
    """
    global _installed
    if _installed:
        return
    sys.stdout = _StderrStream()
    sys.stderr = _StderrStream()
    _installed = True
