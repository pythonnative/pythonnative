"""Shared async query cache with deduplication and explicit invalidation."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Hashable

from .runtime import TaskScope


@dataclass(frozen=True)
class QuerySnapshot:
    """Immutable state shared by every subscriber to a query key."""

    data: Any = None
    loading: bool = False
    error: BaseException | None = None
    revision: int = 0


class _Entry:
    def __init__(self, initial: Any) -> None:
        self.snapshot = QuerySnapshot(data=initial, loading=True)
        self.listeners: set[Callable[[], None]] = set()
        self.fetcher: Callable[[], Awaitable[Any]] | None = None
        self.task: Any = None
        self.expires = 0.0
        self.generation = 0

    def publish(self, *, data: Any, loading: bool, error: BaseException | None = None) -> None:
        self.snapshot = QuerySnapshot(data, loading, error, self.snapshot.revision + 1)
        for listener in tuple(self.listeners):
            listener()


class QueryClient:
    """Own shared requests and cached immutable results for one application.

    A final unsubscribe cancels pending work. Cached values remain bounded by
    capacity. Invalidation cancels older requests before starting replacements.
    """

    def __init__(self, *, capacity: int = 128, stale_time: float = 30) -> None:
        if capacity < 1 or stale_time < 0:
            raise ValueError("Invalid query cache limits")
        self.capacity = capacity
        self.stale_time = stale_time
        self._entries: OrderedDict[Hashable, _Entry] = OrderedDict()
        self._scope = TaskScope("queries")

    def _entry(self, key: Hashable, initial: Any = None) -> _Entry:
        hash(key)
        if key not in self._entries:
            self._entries[key] = _Entry(initial)
        self._entries.move_to_end(key)
        for old_key, old in tuple(self._entries.items()):
            if len(self._entries) <= self.capacity:
                break
            if old_key != key and not old.listeners and (old.task is None or old.task.done()):
                del self._entries[old_key]
        return self._entries[key]

    def snapshot(self, key: Hashable, initial: Any = None) -> QuerySnapshot:
        """Read a stable snapshot without starting network work."""
        return self._entry(key, initial).snapshot

    def subscribe(
        self, key: Hashable, fetcher: Callable[[], Awaitable[Any]], listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Subscribe and start one shared request when cached data is stale."""
        entry = self._entry(key)
        entry.fetcher = fetcher
        entry.listeners.add(listener)
        if entry.expires <= time.monotonic():
            self._fetch(entry)

        def remove() -> None:
            entry.listeners.discard(listener)
            if not entry.listeners and entry.task is not None and not entry.task.done():
                entry.generation += 1
                entry.task.cancel()
                entry.task = None
                entry.publish(data=entry.snapshot.data, loading=False)

        return remove

    def _fetch(self, entry: _Entry) -> None:
        if entry.fetcher is None or entry.task is not None and not entry.task.done():
            return
        generation = entry.generation
        fetcher = entry.fetcher
        entry.publish(data=entry.snapshot.data, loading=True)

        async def run() -> None:
            try:
                result = await fetcher()
                if generation == entry.generation:
                    entry.expires = time.monotonic() + self.stale_time
                    entry.publish(data=result, loading=False)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if generation == entry.generation:
                    entry.publish(data=entry.snapshot.data, loading=False, error=error)

        entry.task = self._scope.create_task(run())

    def invalidate(self, key: Hashable | None = None) -> None:
        """Invalidate one key or every query and refresh active subscribers."""
        for entry in [self._entry(key)] if key is not None else list(self._entries.values()):
            entry.generation += 1
            entry.expires = 0
            if entry.task is not None:
                entry.task.cancel()
                entry.task = None
            if entry.listeners:
                self._fetch(entry)

    def set_data(self, key: Hashable, value: Any) -> None:
        """Publish an immutable optimistic result and supersede older requests."""
        entry = self._entry(key)
        entry.generation += 1
        if entry.task is not None:
            entry.task.cancel()
            entry.task = None
        entry.expires = time.monotonic() + self.stale_time
        entry.publish(data=value, loading=False)

    def close(self) -> None:
        """Cancel shared tasks and release all cached data and listeners."""
        self._scope.close()
        self._entries.clear()


_default: QueryClient | None = None


def default_client() -> QueryClient:
    """Return the application's default query cache."""
    global _default
    if _default is None or _default._scope.closed:
        _default = QueryClient()
    return _default


def _reset_for_tests() -> None:
    global _default
    if _default is not None:
        _default.close()
    _default = None
