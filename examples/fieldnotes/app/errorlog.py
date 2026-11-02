"""The on-disk error log behind ``pn.set_error_handler``.

Nobody reads a phone's console. When an app in the field misbehaves, this file is
the only record there is, so it's written as each error happens, on the
application thread, in one small append. One JSON object per line means that a
crash halfway through a write costs at most the line it was writing.
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

MAX_RECORDS = 200
"""Older errors drop off, so a loop that fails on every frame can't fill the disk."""


@dataclass(frozen=True)
class ErrorRecord:
    """One logged error.

    Attributes:
        at: When it happened.
        phase: Where the framework caught it, such as ``render`` or ``event``.
        kind: The exception's type.
        message: The exception's message.
        trace: The formatted traceback.
    """

    at: float
    phase: str
    kind: str
    message: str
    trace: str


class ErrorLog:
    """An append-mostly file of errors.

    Args:
        path: The file, or a function returning it. A function delays asking the
            platform for the app's directory until the first error.
        on_change: Called after each change with how many records there are.
    """

    def __init__(self, path: Callable[[], Path], on_change: Optional[Callable[[int], None]] = None) -> None:
        self._path = path
        self.on_change = on_change
        self._count: Optional[int] = None

    def record(self, error: BaseException, phase: str) -> None:
        """Append an error. This is the handler given to ``pn.set_error_handler``.

        Args:
            error: What was raised.
            phase: Where the framework caught it.
        """
        line = json.dumps(
            {
                "at": time.time(),
                "phase": phase,
                "kind": type(error).__name__,
                "message": str(error),
                "trace": "".join(traceback.format_exception(error)),
            }
        )
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
        count = self.count() + 1
        if count > MAX_RECORDS * 2:
            self._trim(path)
            count = MAX_RECORDS
        self._count = count
        self._changed()

    def read(self) -> tuple[ErrorRecord, ...]:
        """Return the logged errors, newest first, skipping any line a crash cut short."""
        try:
            lines = self._path().read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return ()
        records = []
        for line in reversed(lines[-MAX_RECORDS:]):
            try:
                records.append(ErrorRecord(**json.loads(line)))
            except (TypeError, ValueError):
                continue
        return tuple(records)

    def count(self) -> int:
        """Return how many errors are logged."""
        if self._count is None:
            self._count = len(self.read())
        return self._count

    def clear(self) -> None:
        """Delete the log."""
        self._path().unlink(missing_ok=True)
        self._count = 0
        self._changed()

    def _trim(self, path: Path) -> None:
        lines = path.read_text(encoding="utf-8").splitlines()[-MAX_RECORDS:]
        path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change(self.count())
