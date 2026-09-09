"""Undo only bookkeeping touched by an uncommitted render.

Application objects aren't copied. The journal owns framework containers and
attribute assignments; native mutation and effect publication are separate.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

_current: ContextVar[Journal | None] = ContextVar("pn_render_journal", default=None)
_missing = object()


class Journal:
    """Record inverse mutations for one uncommitted render pass."""

    def __init__(self) -> None:
        self.undo: list[Callable[[], None]] = []
        self.seen: set[tuple[int, Any]] = set()
        self.active = True

    def attribute(self, obj: Any, name: str) -> None:
        """Capture an attribute before its first mutation in this pass."""
        key = (id(obj), name)
        if not self.active or key in self.seen or not hasattr(obj, name):
            return
        self.seen.add(key)
        value = getattr(obj, name)
        if isinstance(value, (list, dict, set)):
            value = value.copy()
        self.undo.append(lambda: object.__setattr__(obj, name, value))

    def mapping(self, mapping: dict, key: Any) -> None:
        """Capture one mapping entry without copying unrelated entries."""
        identity = (id(mapping), key)
        if not self.active or identity in self.seen:
            return
        self.seen.add(identity)
        value = mapping.get(key, _missing)

        def restore() -> None:
            if value is _missing:
                dict.pop(mapping, key, None)
            else:
                dict.__setitem__(mapping, key, value)

        self.undo.append(restore)

    def accept(self) -> None:
        """Release inverse operations after successful native application."""
        self.undo.clear()
        self.seen.clear()

    def rollback(self) -> None:
        """Restore bookkeeping in reverse mutation order."""
        self.active = False
        for restore in reversed(self.undo):
            restore()
        self.accept()


def record_attribute(obj: Any, name: str) -> None:
    """Record a framework attribute in the active render journal, if any."""
    journal = _current.get()
    if journal is not None:
        journal.attribute(obj, name)


class JournalDict(dict):
    """A dictionary whose changed keys participate in the current render."""

    def __setitem__(self, key: Any, value: Any) -> None:
        journal = _current.get()
        if journal is not None:
            journal.mapping(self, key)
        super().__setitem__(key, value)

    def pop(self, key: Any, default: Any = _missing) -> Any:
        """Remove an entry while recording its previous value."""
        journal = _current.get()
        if journal is not None:
            journal.mapping(self, key)
        if default is _missing:
            return super().pop(key)
        return super().pop(key, default)

    def clear(self) -> None:
        """Remove entries through the journal."""
        for key in tuple(self):
            self.pop(key)
