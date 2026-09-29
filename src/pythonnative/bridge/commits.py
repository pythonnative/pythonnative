"""Versioned commit validation and surface ownership.

A commit is validated in full before it changes a native tree. Revisions are
strictly consecutive within an application and surface. A failed native mount
poisons that surface until the host explicitly resets and remounts it.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import Any, Callable

from ..profiling import count, profiled
from .list_store import ListStore

PROTOCOL_VERSION = 4


class CommitError(RuntimeError):
    """A malformed, stale, or failed native transaction."""


@dataclass
class ViewState:
    """Wire-visible view state used to validate a whole transaction."""

    type_name: str
    props: dict[str, Any]
    parent: int | None = None
    children: list[int] = field(default_factory=list)
    list_store: ListStore | None = None


class ViewOverlay(MutableMapping[int, ViewState]):
    """Copy only records written by a candidate commit.

    Publishing consumes the candidate and updates its owned base in place. A
    rejected candidate is simply discarded. There is no chain of old revisions.
    """

    def __init__(self, base: MutableMapping[int, ViewState]) -> None:
        self.base = base
        self.changed: dict[int, ViewState] = {}
        self.deleted: set[int] = set()

    def __getitem__(self, tag: int) -> ViewState:
        if tag in self.deleted:
            raise KeyError(tag)
        return self.changed[tag] if tag in self.changed else self.base[tag]

    def __setitem__(self, tag: int, value: ViewState) -> None:
        self.deleted.discard(tag)
        self.changed[tag] = value

    def __delitem__(self, tag: int) -> None:
        self[tag]
        self.changed.pop(tag, None)
        self.deleted.add(tag)

    def __iter__(self) -> Iterator[int]:
        yield from (tag for tag in self.base if tag not in self.deleted and tag not in self.changed)
        yield from self.changed

    def __len__(self) -> int:
        return (
            len(self.base)
            - sum(tag in self.base for tag in self.deleted)
            + sum(tag not in self.base for tag in self.changed)
        )

    def edit(self, tag: int) -> ViewState:
        """Return a writable copy of this record, copying it at most once."""
        if tag not in self.changed:
            view = self[tag]
            self.changed[tag] = ViewState(
                view.type_name, dict(view.props), view.parent, list(view.children), view.list_store
            )
            count("commit.records_copied")
        return self.changed[tag]

    def publish(self) -> MutableMapping[int, ViewState]:
        """Apply accepted records to the owned base without a revision chain."""
        for tag in self.deleted:
            del self.base[tag]
        self.base.update(self.changed)
        return self.base


@dataclass
class CommitState:
    """Committed revision and structural state for one native surface."""

    application: str = ""
    surface: int = 0
    revision: int = 0
    views: MutableMapping[int, ViewState] = field(default_factory=dict)

    _list_publications: dict[int, Callable[[], None]] = field(default_factory=dict)

    @profiled("validation")
    def prepare(self, envelope: Any) -> CommitState:
        """Validate without mutating this state and return the candidate state."""
        if not isinstance(envelope, dict) or envelope.get("version") != PROTOCOL_VERSION:
            raise CommitError("Expected a protocol v4 commit envelope; rebuild the native client")
        application, surface, revision = (envelope.get(k) for k in ("application", "surface", "revision"))
        if not isinstance(application, str) or not application or type(surface) is not int or surface <= 0:
            raise CommitError("Invalid application or surface identity")
        if self.application and (application, surface) != (self.application, self.surface):
            raise CommitError("Commit belongs to another application or surface")
        if type(revision) is not int or revision != self.revision + 1:
            raise CommitError(f"Expected revision {self.revision + 1}, received {revision!r}")
        ops = envelope.get("ops")
        if not isinstance(ops, list):
            raise CommitError("Commit ops must be a list")
        if isinstance(self.views, ViewOverlay):
            raise CommitError("Publish the previous candidate before preparing another commit")
        result = CommitState(application, surface, revision, ViewOverlay(self.views))
        for index, op in enumerate(ops):
            try:
                result._validate_op(op)
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                raise CommitError(f"Invalid op {index}: {exc}") from exc
        return result

    def publish(self) -> CommitState:
        """Accept a successfully mounted candidate; the prior state is consumed."""
        for publish in self._list_publications.values():
            publish()
        self._list_publications.clear()
        if isinstance(self.views, ViewOverlay):
            self.views = self.views.publish()
        return self

    def _edit(self, tag: int) -> ViewState:
        assert isinstance(self.views, ViewOverlay)
        return self.views.edit(tag)

    def _validate_op(self, op: Any) -> None:
        if not isinstance(op, list) or len(op) < 2:
            raise ValueError("Expected an operation array")
        code, tag = op[:2]
        lengths = {"c": 4, "u": 4, "i": 4, "d": 2, "f": 6}
        if code not in lengths or len(op) != lengths[code] or type(tag) is not int or tag <= 0:
            raise ValueError("Invalid opcode, arity, or tag")
        if code == "c":
            if tag in self.views or not isinstance(op[2], str) or not op[2] or not isinstance(op[3], dict):
                raise ValueError("Invalid or duplicate create")
            self._validate_props(op[2], op[3], False)
            view = ViewState(op[2], dict(op[3]))
            self.views[tag] = view
            if op[2] == "VirtualList":
                view.list_store = ListStore()
                self._prepare_list(tag, view, op[3])
            return
        view = self.views[tag] if code == "f" else self._edit(tag)
        if code == "u":
            if not isinstance(op[2], dict):
                raise ValueError("Update requires a property mapping")
            self._validate_props(view.type_name, op[2], True)
            removed = op[3]
            if not isinstance(removed, list) or any(not isinstance(name, str) for name in removed):
                raise ValueError("Removed properties must be a list of names")
            if len(set(removed)) != len(removed) or set(removed) & op[2].keys():
                raise ValueError("A property can't be both set and removed")
            from ..mutations import UNSET

            self._validate_props(view.type_name, {name: UNSET for name in removed}, True)
            if view.list_store is not None:
                self._prepare_list(tag, view, op[2])
            view.props.update(op[2])
            for name in removed:
                view.props.pop(name, None)
        elif code == "i":
            child_tag, index = op[2:]
            if type(child_tag) is not int or type(index) is not int or index < 0:
                raise ValueError("Invalid child or insertion index")
            child = self._edit(child_tag)
            ancestor: int | None = tag
            while ancestor is not None:
                if ancestor == child_tag:
                    raise ValueError("Insertion creates a cycle")
                ancestor = self.views[ancestor].parent
            if child.parent is not None:
                self._edit(child.parent).children.remove(child_tag)
            if index > len(view.children):
                raise ValueError("Insertion index exceeds child count")
            view.children.insert(index, child_tag)
            child.parent = tag
        elif code == "d":
            if view.children:
                raise ValueError("Destroy children before their parent")
            if view.parent is not None:
                self._edit(view.parent).children.remove(tag)
            del self.views[tag]
        elif code == "f":
            if any(type(n) not in (float, int) or not math.isfinite(n) for n in op[2:]):
                raise ValueError("Frame values must be finite numbers")
            if op[4] < 0 or op[5] < 0:
                raise ValueError("Frame sizes must be nonnegative")

    def _prepare_list(self, tag: int, view: ViewState, props: dict[str, Any]) -> None:
        if "dataset" in props:
            if tag in self._list_publications:
                raise ValueError("A list may receive only one dataset patch per commit")
            assert view.list_store is not None
            self._list_publications[tag] = view.list_store.prepare(props["dataset"])

    @staticmethod
    def _validate_props(name: str, props: dict[str, Any], partial: bool) -> None:
        from ..sdk.schema import COMPONENTS

        schema = COMPONENTS.get(name)
        if schema is not None:
            schema.validate(props, partial=partial)

    def acknowledgement(self) -> dict[str, Any]:
        """Identify the exact revision native successfully mounted."""
        return {"ok": True, "application": self.application, "surface": self.surface, "revision": self.revision}
