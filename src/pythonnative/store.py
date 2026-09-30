"""Application state that lives outside the component tree.

A [`Store`][pythonnative.Store] holds one immutable value (typically a
frozen dataclass) and notifies subscribers when it's replaced.
Components read it with [`use_store`][pythonnative.use_store], optionally
through a selector, and re-render only when the selected value changes:

```python
from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True)
class Session:
    user: str | None = None
    unread: int = 0


session = pn.Store(Session())


def sign_in(user: str) -> None:
    session.update(lambda state: replace(state, user=user))


@pn.component
def UnreadBadge() -> pn.Node:
    unread = pn.use_store(session, lambda state: state.unread)
    return pn.Text(str(unread)) if unread else None
```

Stores are plain objects: define them at module level, pass them
through context, or own them in a service. Actions are ordinary
functions. Because the value is replaced rather than mutated, every
change is visible to the framework's equality rule, and tests can
drive a store without rendering anything.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Callable, Generic, Iterator, List, Optional, TypeVar, overload

from .equality import equal

__all__ = ["Store", "use_store"]

T = TypeVar("T")
S = TypeVar("S")


class Store(Generic[T]):
    """A replaceable value with change notifications.

    Writes apply immediately under a lock, so ``get()`` always returns
    the latest value on every thread. Listeners run synchronously on
    the writing thread after the value changes; components subscribed
    through [`use_store`][pythonnative.use_store] schedule their
    re-render on the application thread, like any state setter.

    Args:
        initial: The starting value.
        name: Optional label shown in ``repr`` and diagnostics.
    """

    __slots__ = ("_value", "_listeners", "_lock", "_batch_depth", "_dirty", "name")

    def __init__(self, initial: T, *, name: Optional[str] = None) -> None:
        self._value = initial
        self._listeners: List[Callable[[], None]] = []
        self._lock = threading.RLock()
        self._batch_depth = 0
        self._dirty = False
        self.name = name

    def get(self) -> T:
        """Return the current value."""
        return self._value

    def set(self, value: T) -> None:
        """Replace the value; subscribers are notified only when it changed."""
        with self._lock:
            notify = self._replace(value)
        if notify:
            self._notify()

    def update(self, fn: Callable[[T], T]) -> None:
        """Replace the value with ``fn(current)``, atomically with respect to other writers."""
        with self._lock:
            notify = self._replace(fn(self._value))
        if notify:
            self._notify()

    def _replace(self, value: T) -> bool:
        """Store ``value`` (lock held); return whether subscribers should hear about it now."""
        if equal(self._value, value):
            return False
        self._value = value
        if self._batch_depth:
            self._dirty = True
            return False
        return True

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call ``listener()`` after every change; returns a function that unsubscribes."""
        with self._lock:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock:
                try:
                    self._listeners.remove(listener)
                except ValueError:
                    pass

        return unsubscribe

    @contextmanager
    def batch(self) -> Iterator["Store[T]"]:
        """Coalesce the writes inside the block into at most one notification.

        ```python
        with store.batch():
            store.update(add_item)
            store.update(bump_revision)
        ```
        """
        with self._lock:
            self._batch_depth += 1
        try:
            yield self
        finally:
            with self._lock:
                self._batch_depth -= 1
                notify = self._batch_depth == 0 and self._dirty
                if notify:
                    self._dirty = False
            if notify:
                self._notify()

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            listener()

    def __repr__(self) -> str:
        label = f" {self.name}" if self.name else ""
        return f"<Store{label} {self._value!r}>"


@overload
def use_store(store: Store[T]) -> T: ...


@overload
def use_store(store: Store[T], selector: Callable[[T], S]) -> S: ...


def use_store(store: Store[T], selector: Optional[Callable[[T], S]] = None) -> T | S:
    """Read ``store`` (or ``selector(store.get())``) and re-render when it changes.

    The component subscribes on mount and unsubscribes on unmount. With
    a selector it re-renders only when the selected value changes under
    the framework's equality rule, so a component that shows a count
    doesn't re-render when an unrelated field changes. The selector may
    be a fresh lambda on every render.

    Args:
        store: The [`Store`][pythonnative.Store] to read.
        selector: Optional ``state -> value`` projection.

    Returns:
        The store's value, or the selected projection of it.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    from .hooks import use_subscription

    select: Callable[[T], Any] = selector if selector is not None else _identity
    return use_subscription(store.subscribe, lambda: select(store.get()))


def _identity(value: T) -> T:
    return value
