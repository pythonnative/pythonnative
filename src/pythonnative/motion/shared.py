"""Shared values: state both the Python thread and the UI thread read and write (RFC 0009)."""

from __future__ import annotations

import itertools
import json
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")

_ids = itertools.count(1)


class SharedValue(Generic[T]):
    """A value the UI thread owns and Python can read, write, and animate.

    Create one with [`use_shared_value`][pythonnative.use_shared_value].
    In a worklet, ``.value`` reads and writes the UI thread's copy directly.
    In Python:

    - Reading ``.value`` returns the latest value the UI thread published
      (it publishes after each frame and event, never waiting for a reader).
      A read right after a write from Python returns the written value until
      the UI thread has applied it.
    - Writing ``.value`` queues the write behind pending mounts. Writing an
      animation (``value = pn.with_spring(0)``) starts it; writing a plain
      value cancels a running animation.
    - ``await shared.animate(animation)`` starts an animation and returns
      ``True`` once it finishes, or ``False`` if something interrupted it.
      Canceling the awaiting task cancels the animation.

    Reading ``.value`` during a render doesn't re-render when it changes;
    drive the view with [`use_animated_style`][pythonnative.use_animated_style]
    instead.
    """

    __slots__ = ("id", "_value", "_readonly", "_target", "_overlay", "_published_at_write", "__weakref__")

    def __init__(self, initial: T, *, readonly: bool = False) -> None:
        self.id = next(_ids)
        self._value: Any = initial
        self._readonly = readonly
        self._target: Any = None
        self._overlay = False
        self._published_at_write: Optional[str] = None

    @property
    def value(self) -> T:
        """The latest value: the UI thread's, or a write from Python it hasn't applied yet."""
        from .runtime import runtime

        published = runtime.read(self)
        if published is None:
            return self._value
        if self._overlay:
            if published == self._published_at_write:
                return self._value
            self._overlay = False
        self._value = json.loads(published)
        return self._value

    @value.setter
    def value(self, value: T) -> None:
        if self._readonly:
            raise AttributeError("a derived value is read-only; change what it derives from instead")
        from .animations import Animation
        from .runtime import runtime

        if isinstance(value, Animation):
            runtime.animate(self, value, None)
            return
        self._published_at_write = runtime.read(self)
        self._overlay = self._published_at_write is not None
        self._value = value
        runtime.set(self, value)

    async def animate(self, animation: Any) -> bool:
        """Run ``animation`` on this value and return whether it finished."""
        from .animations import Animation
        from .runtime import runtime

        if self._readonly:
            raise AttributeError("a derived value is read-only")
        if not isinstance(animation, Animation):
            raise TypeError("animate() takes with_timing(), with_spring(), with_decay(), or a composition of them")
        return await runtime.animate_awaitable(self, animation)

    def cancel(self) -> None:
        """Stop a running animation where it is."""
        from .runtime import runtime

        runtime.cancel(self)

    def __repr__(self) -> str:
        return f"SharedValue({self._value!r})"
