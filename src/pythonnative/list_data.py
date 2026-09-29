"""Typed, keyed list data with explicit mutations and bounded change history."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generic, TypeVar, overload

T = TypeVar("T")


@dataclass(frozen=True)
class Section(Generic[T]):
    """A section whose identity survives insertion, removal, and reordering."""

    key: str
    data: Sequence[T]
    title: str = ""


@dataclass(frozen=True)
class ViewableItem(Generic[T]):
    """An item currently visible in the native viewport."""

    key: str
    index: int
    item: T


@dataclass(frozen=True)
class _Entry(Generic[T]):
    key: str
    item: T
    revision: int


class ListData(Sequence[T]):
    """A keyed collection that publishes explicit edits to virtualized lists.

    Call mutations on the thread that created the collection, normally the
    application thread. Items are application values: replace an item with
    ``update`` after editing it instead of mutating it silently. Keys must be
    unique, nonempty strings and can't change in an update.

    ``update`` and key lookup take constant time. Insertion, removal, and moves
    shift an indexed Python list, but don't re-render or serialize unaffected
    items. ``batch`` coalesces notifications; it isn't a rollback transaction.
    Successful edits remain applied if the body raises. A bounded journal lets
    multiple mounted lists catch up independently; a lagging list receives a
    fresh snapshot after its history has expired.
    """

    def __init__(self, items: Iterable[T] = (), *, key: Callable[[T], str], history_limit: int = 1024) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be positive")
        self._owner = threading.get_ident()
        self._key = key
        self._keys: list[str] = []
        self._entries: dict[str, _Entry[T]] = {}
        self._history: deque[tuple[int, tuple[object, ...]]] = deque(maxlen=history_limit)
        self._revision = 0
        self._batch_depth = 0
        self._notified = 0
        self._listeners: set[Callable[[], None]] = set()
        for item in items:
            name = self._name(item)
            if name in self._entries:
                raise ValueError("List keys must be unique")
            self._keys.append(name)
            self._entries[name] = _Entry(name, item, 1)

    def _name(self, item: T) -> str:
        name = self._key(item)
        if not isinstance(name, str) or not name:
            raise ValueError("List keys must be nonempty strings")
        return name

    def _check_thread(self) -> None:
        if threading.get_ident() != self._owner:
            raise RuntimeError("Mutate ListData on its owning application thread")

    def __len__(self) -> int:
        return len(self._keys)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> list[T]: ...

    def __getitem__(self, index: int | slice) -> T | list[T]:
        if isinstance(index, slice):
            return [self._entries[key].item for key in self._keys[index]]
        return self._entries[self._keys[index]].item

    def get(self, key: str) -> T:
        """Return an item by its stable key, raising ``KeyError`` if absent."""
        return self._entries[key].item

    @property
    def revision(self) -> int:
        """Monotonically increasing mutation version for subscriptions."""
        return self._revision

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to changes and return an idempotent unsubscribe function."""
        self._check_thread()
        self._listeners.add(callback)
        return lambda: self._listeners.discard(callback)

    def _record(self, change: tuple[object, ...]) -> None:
        self._revision += 1
        self._history.append((self._revision, change))
        self._notify()

    def _notify(self) -> None:
        if self._batch_depth or self._notified == self._revision:
            return
        self._notified = self._revision
        for callback in tuple(self._listeners):
            callback()

    @contextmanager
    def batch(self) -> Iterator[ListData[T]]:
        """Coalesce subscriber notifications, including nested batches."""
        self._check_thread()
        self._batch_depth += 1
        try:
            yield self
        finally:
            self._batch_depth -= 1
            self._notify()

    def insert(self, index: int, item: T) -> None:
        """Insert an item at an index between zero and ``len(self)``."""
        self._check_thread()
        if not 0 <= index <= len(self):
            raise IndexError("List insertion index out of range")
        name = self._name(item)
        if name in self._entries:
            raise ValueError("List keys must be unique")
        entry = _Entry(name, item, 1)
        self._entries[name] = entry
        self._keys.insert(index, name)
        self._record(("i", index, entry))

    def append(self, item: T) -> None:
        """Append a new keyed item."""
        self.insert(len(self), item)

    def update(self, key: str, item: T) -> None:
        """Replace an item while preserving its key and mounted component state."""
        self._check_thread()
        old = self._entries[key]
        if self._name(item) != key:
            raise ValueError("An update must preserve the item's key")
        entry = _Entry(key, item, old.revision + 1)
        self._entries[key] = entry
        self._record(("u", entry))

    def remove(self, key: str) -> T:
        """Remove and return the item with ``key``."""
        self._check_thread()
        entry = self._entries.pop(key)
        self._keys.remove(key)
        self._record(("d", key))
        return entry.item

    def move(self, key: str, index: int) -> None:
        """Move an item to its final zero-based index, preserving its identity."""
        self._check_thread()
        if not 0 <= index < len(self):
            raise IndexError("List move index out of range")
        if key not in self._entries:
            raise KeyError(key)
        before = self._keys.index(key)
        if before != index:
            self._keys.pop(before)
            self._keys.insert(index, key)
            self._record(("m", key, index))

    def clear(self) -> None:
        """Remove every item with one snapshot invalidation."""
        self._check_thread()
        if self._keys:
            self._keys.clear()
            self._entries.clear()
            self._record(("reset",))

    def _changes_since(self, revision: int) -> list[tuple[object, ...]] | None:
        if revision == self._revision:
            return []
        if not self._history or revision < self._history[0][0] - 1 or revision > self._revision:
            return None
        changes = [change for version, change in self._history if version > revision]
        return None if any(change[0] == "reset" for change in changes) else changes
