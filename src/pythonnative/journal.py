"""Undo only bookkeeping touched by an uncommitted render.

Application objects aren't copied. The journal owns framework containers and
attribute assignments; native mutation and effect publication are separate.

The reconciler installs a [`Journal`][pythonnative.journal.Journal] for the
duration of one render pass and raises the module-level ``journal_active``
flag. [`VNode`][pythonnative.reconciler.VNode] and
[`Ref`][pythonnative.Ref] consult that flag in ``__setattr__`` so attribute
writes outside a pass cost one global lookup and no call. Inside a pass the
journal records only the node fields listed in ``STRUCTURAL_FIELDS`` (plus
``Ref.current``): the tree structure and native identity, the element and
clean props the next diff compares against, and hook and boundary state.
The per-pass layout caches (``measure_cache``, ``last_frame``,
``layout_node``, ``layout_dirty``) are skipped; they are rebuilt by the
next layout pass and never observed by application code.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

__all__ = ["Journal", "JournalDict", "STRUCTURAL_FIELDS", "journal_active", "record_attribute"]

_current: ContextVar[Journal | None] = ContextVar("pn_render_journal", default=None)
_missing = object()

journal_active: bool = False
"""Whether a render journal is recording. Read by ``VNode`` and ``Ref`` before recording."""

STRUCTURAL_FIELDS = frozenset(
    {
        "root",
        "children",
        "parent",
        "tag",
        "native_view",
        "element",
        "clean_props",
        "hook_state",
        "mounted",
        "rendered",
        "hidden_by_suspense",
        "error",
        "suspense_showing_fallback",
        "suspense_hidden",
        "suspense_hydration",
        "suspense_waits",
    }
)
"""The ``VNode`` (and reconciler) fields a rollback restores; layout caches are not among them."""


class Journal:
    """Record inverse mutations for one uncommitted render pass."""

    def __init__(self) -> None:
        self.undo: list[Callable[[], Any]] = []
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


def install(journal: Journal) -> Any:
    """Make ``journal`` the recording journal; returns the token for ``uninstall``."""
    global journal_active
    token = _current.set(journal)
    journal_active = True
    return token


def uninstall(token: Any) -> None:
    """Stop recording and restore the previously installed journal, if any."""
    global journal_active
    _current.reset(token)
    journal_active = _current.get() is not None


def current() -> Journal | None:
    """Return the journal recording the in-flight render pass, or ``None``."""
    return _current.get()


def record_attribute(obj: Any, name: str) -> None:
    """Record a framework attribute in the active render journal, if any.

    Callers check ``journal_active`` first so the common case (no pass in
    flight) never reaches this function.
    """
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
