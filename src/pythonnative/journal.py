"""Undo only bookkeeping touched by an uncommitted render.

Application objects aren't copied. The journal owns framework containers and
attribute assignments; native mutation and effect publication are separate.

The reconciler installs a [`Journal`][pythonnative.journal.Journal] for the
duration of one render pass and raises the module-level ``journal_active``
flag. [`VNode`][pythonnative.reconciler.VNode] and
[`Ref`][pythonnative.Ref] consult that flag in ``__setattr__`` so attribute
writes outside a pass cost one global lookup and no call.

Inside a pass, an object is captured once, on its first write: the
journal takes a [`snapshot`][pythonnative.journal.Journal.snapshot] of
every journaled field and stamps the object with the journal's identity,
so later writes in the same pass compare one attribute. Objects created
during the pass are stamped at construction and never captured, because a
rollback discards them. For a node, the journaled fields are
``STRUCTURAL_FIELDS``: the tree structure and native identity, the element
and clean props the next diff compares against, and hook and boundary
state. The per-pass layout caches (``measure_cache``, ``last_frame``,
``layout_node``, ``layout_dirty``) are skipped; they are rebuilt by the
next layout pass and never observed by application code.
"""

from __future__ import annotations

import functools
import operator
from contextvars import Context, ContextVar, copy_context
from typing import Any, Callable

__all__ = [
    "Journal",
    "JournalDict",
    "STRUCTURAL_FIELDS",
    "active",
    "journal_active",
    "record_attribute",
]

_current: ContextVar[Journal | None] = ContextVar("pn_render_journal", default=None)
_missing = object()
_CONTAINERS = frozenset({list, dict, set})

journal_active: bool = False
"""Whether a render journal is recording. Read by ``VNode`` and ``Ref`` before recording."""

active: Journal | None = None
"""The journal recording the synchronous render pass in progress, or ``None``."""

FRESH = 0
"""Stamp of an object no journal needs to capture (created before any pass)."""

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


_next_identity = 0


@functools.cache
def _capture(fields: tuple[str, ...]) -> Callable[[Any], tuple[Any, ...]]:
    """Compile a reader that returns ``fields`` of an object, copying containers.

    The tuple is built inline (no generator per value), because every
    object a render pass changes is captured once.
    """
    names = [f"v{index}" for index in range(len(fields))]
    copies = ", ".join(f"{name}.copy() if type({name}) in containers else {name}" for name in names)
    source = "def capture(obj):\n" f"    {', '.join(names)}, = getter(obj)\n" f"    return ({copies},)\n"
    namespace: dict[str, Any] = {
        "getter": (
            operator.attrgetter(*fields)
            if len(fields) > 1
            else (lambda obj, read=operator.attrgetter(fields[0]): (read(obj),))
        ),
        "containers": _CONTAINERS,
    }
    exec(source, namespace)
    capture: Callable[[Any], tuple[Any, ...]] = namespace["capture"]
    return capture


def _new_identity() -> int:
    global _next_identity
    _next_identity += 1
    return _next_identity


class Journal:
    """Record inverse mutations for one uncommitted render pass.

    Attributes:
        identity: A positive number unique to this journal; objects
            captured by it carry it as their ``_journal_stamp``.
    """

    def __init__(self) -> None:
        self.identity = _new_identity()
        self.undo: list[Callable[[], Any]] = []
        self.seen: set[tuple[int, Any]] = set()
        self.active = True

    def snapshot(self, obj: Any, fields: tuple[str, ...]) -> None:
        """Capture ``fields`` of ``obj`` in one undo entry and stamp ``obj``.

        Containers are copied shallowly; a missing slot is deleted again on
        rollback.
        """
        object.__setattr__(obj, "_journal_stamp", self.identity)
        if not self.active:
            return
        try:
            values = _capture(fields)(obj)
        except AttributeError:
            values = tuple(getattr(obj, name, _missing) for name in fields)
            values = tuple(value.copy() if type(value) in _CONTAINERS else value for value in values)

        def restore() -> None:
            for name, value in zip(fields, values):
                if value is _missing:
                    try:
                        object.__delattr__(obj, name)
                    except AttributeError:
                        pass
                else:
                    object.__setattr__(obj, name, value)

        self.undo.append(restore)

    def attribute(self, obj: Any, name: str) -> None:
        """Capture an attribute before its first mutation in this pass."""
        key = (id(obj), name)
        if not self.active or key in self.seen or not hasattr(obj, name):
            return
        self.seen.add(key)
        value = getattr(obj, name)
        if type(value) in _CONTAINERS:
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
        """Release inverse operations after successful native application.

        Accepted state is the new baseline: a fresh identity makes every
        object this journal stamped eligible for capture again.
        """
        self.undo.clear()
        self.seen.clear()
        self.identity = _new_identity()

    def rollback(self) -> None:
        """Restore bookkeeping in reverse mutation order."""
        self.active = False
        for restore in reversed(self.undo):
            restore()
        self.accept()


def install(journal: Journal) -> Any:
    """Make ``journal`` the recording journal; returns the token for ``uninstall``."""
    global journal_active, active
    token = (_current.set(journal), active)
    active = journal
    journal_active = True
    return token


def uninstall(token: Any) -> None:
    """Stop recording and restore the previously installed journal, if any."""
    global journal_active, active
    context_token, previous = token
    _current.reset(context_token)
    active = previous
    journal_active = previous is not None


def stamp() -> int:
    """The stamp for an object created now: it needs no capture in this pass."""
    return active.identity if active is not None else FRESH


def current() -> Journal | None:
    """Return the journal recording the in-flight render pass, or ``None``."""
    return _current.get()


def record_attribute(obj: Any, name: str) -> None:
    """Record a framework attribute in the active render journal, if any.

    Callers check ``journal_active`` first so the common case (no pass in
    flight) never reaches this function.
    """
    if active is not None:
        active.attribute(obj, name)


class JournalDict(dict):
    """A dictionary whose changed keys participate in the current render."""

    def __setitem__(self, key: Any, value: Any) -> None:
        journal = active
        if journal is not None:
            journal.mapping(self, key)
        super().__setitem__(key, value)

    def pop(self, key: Any, default: Any = _missing) -> Any:
        """Remove an entry while recording its previous value."""
        journal = active
        if journal is not None:
            journal.mapping(self, key)
        if default is _missing:
            return super().pop(key)
        return super().pop(key, default)

    def clear(self) -> None:
        """Remove entries through the journal."""
        for key in tuple(self):
            self.pop(key)


def detached_context() -> Context:
    """Capture task context without inheriting a render's mutable undo journal."""
    context = copy_context()
    context.run(_current.set, None)
    return context
