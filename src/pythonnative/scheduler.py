"""Update scheduling primitives shared by hooks and the reconciler.

Two pieces live here:

- [`batch_updates`][pythonnative.scheduler.batch_updates], a context manager that
  coalesces the render triggers fired by several state setters into
  one, tracked per execution context (so it composes with ``async``
  code).
- [`TransitionQueue`][pythonnative.scheduler.TransitionQueue], the
  per-reconciler queue behind
  [`use_transition`][pythonnative.use_transition]: renders marked as
  transitions are deferred to a later turn of the framework loop so
  urgent updates (typing, presses) stay responsive.

Nothing here is global mutable state beyond context variables, so
several reconcilers (screens, list rows, tests) never interfere.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Generator, List, Optional

from . import diagnostics

__all__ = ["TransitionQueue", "batch_updates", "in_transition", "run_in_transition", "schedule_trigger"]

# Depth of nested ``batch_updates`` blocks plus the triggers deferred by
# the outermost block, per execution context.
_batch_depth: ContextVar[int] = ContextVar("pn_batch_depth", default=0)
_batch_pending: ContextVar[Optional[List[Callable[[], None]]]] = ContextVar("pn_batch_pending", default=None)

# Whether state updates in the current execution context are marked as
# transitions (see ``use_transition``).
_transition_var: ContextVar[bool] = ContextVar("pn_transition", default=False)


def schedule_trigger(trigger: Callable[[], None]) -> None:
    """Run ``trigger`` now, or defer it to the end of the enclosing ``batch_updates`` block."""
    pending = _batch_pending.get()
    if _batch_depth.get() > 0 and pending is not None:
        if trigger not in pending:
            pending.append(trigger)
    else:
        trigger()


@contextmanager
def batch_updates() -> Generator[None, None, None]:
    """Coalesce multiple state updates into a single re-render.

    State setters called inside the ``with`` block defer their
    re-render trigger until the block exits, so any number of
    ``set_*`` calls produce at most one render pass.

    Example:
        ```python
        import pythonnative as pn

        with pn.batch_updates():
            set_count(1)
            set_name("hello")
        ```
    """
    depth = _batch_depth.get()
    depth_token = _batch_depth.set(depth + 1)
    pending_token = None
    if depth == 0:
        pending_token = _batch_pending.set([])
    try:
        yield
    finally:
        _batch_depth.reset(depth_token)
        if pending_token is not None:
            triggers = _batch_pending.get() or []
            _batch_pending.reset(pending_token)
            for trigger in triggers:
                trigger()


def in_transition() -> bool:
    """Whether state updates in the current context are transitions."""
    return _transition_var.get()


def run_in_transition(fn: Callable[[], None]) -> None:
    """Run ``fn`` with its state updates marked as transitions."""
    token = _transition_var.set(True)
    try:
        fn()
    finally:
        _transition_var.reset(token)


class TransitionQueue:
    """Deferred render triggers and completion callbacks for one reconciler.

    Triggers added via [`defer`][pythonnative.scheduler.TransitionQueue.defer]
    run together on a later loop turn; callbacks added via
    [`on_complete`][pythonnative.scheduler.TransitionQueue.on_complete]
    run right after them (this is how ``use_transition`` flips its
    ``is_pending`` flag back off once the deferred render committed).
    """

    __slots__ = ("_triggers", "_callbacks", "_scheduled")

    def __init__(self) -> None:
        self._triggers: List[Callable[[], None]] = []
        self._callbacks: List[Callable[[], None]] = []
        self._scheduled = False

    def defer(self, trigger: Callable[[], None]) -> None:
        """Queue ``trigger`` for the next flush."""
        if trigger not in self._triggers:
            self._triggers.append(trigger)
        self._ensure_scheduled()

    def on_complete(self, callback: Callable[[], None]) -> None:
        """Queue ``callback`` to run after the next flush's triggers."""
        self._callbacks.append(callback)
        self._ensure_scheduled()

    @property
    def pending(self) -> bool:
        """Whether a flush is scheduled or work is queued."""
        return self._scheduled or bool(self._triggers) or bool(self._callbacks)

    def flush(self) -> None:
        """Run every deferred trigger, then the completion callbacks."""
        self._scheduled = False
        triggers = self._triggers
        callbacks = self._callbacks
        self._triggers = []
        self._callbacks = []
        for fn in triggers + callbacks:
            try:
                fn()
            except Exception as exc:
                if not diagnostics.report_error(exc, phase="transition"):
                    raise

    def clear(self) -> None:
        """Drop queued work (used on unmount)."""
        self._triggers = []
        self._callbacks = []
        self._scheduled = False

    def _ensure_scheduled(self) -> None:
        if self._scheduled:
            return
        self._scheduled = True
        from .runtime import get_loop

        get_loop().call_soon(self._flush_if_scheduled)

    def _flush_if_scheduled(self) -> None:
        if self._scheduled:
            self.flush()
