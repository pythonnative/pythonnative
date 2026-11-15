"""Update scheduling primitives shared by hooks and the reconciler.

Three pieces live here:

- [`batch_updates`][pythonnative.scheduler.batch_updates], a context manager that
  coalesces the render triggers fired by several state setters into
  one, tracked per execution context (so it composes with ``async``
  code).
- [`TransitionQueue`][pythonnative.scheduler.TransitionQueue], the
  per-reconciler record of state updates marked as transitions (by
  [`start_transition`][pythonnative.scheduler.start_transition],
  [`use_transition`][pythonnative.use_transition], or
  [`use_deferred_value`][pythonnative.use_deferred_value]). Their
  render runs after urgent work and is abandoned when urgent input
  arrives.
- [`queue_urgent`][pythonnative.scheduler.queue_urgent], how input
  reaches the application loop. A render pass for a transition checks
  [`urgent_input_pending`][pythonnative.scheduler.urgent_input_pending]
  before each component body and yields to queued input.

Apart from the urgent-input counters, nothing here is global mutable
state beyond context variables, so several reconcilers (screens, list
rows, tests) never interfere.
"""

from __future__ import annotations

import contextvars
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, Generator, List, Optional

from .journal import JournalDict

if TYPE_CHECKING:
    from .hooks import HookState

__all__ = [
    "MAX_PREEMPTIONS",
    "STARVATION_SECONDS",
    "TransitionQueue",
    "batch_updates",
    "in_transition",
    "queue_urgent",
    "run_in_transition",
    "run_urgently",
    "schedule_trigger",
    "start_transition",
    "urgent_input_pending",
]

MAX_PREEMPTIONS = 3
"""How many times a transition may be abandoned for urgent input before it renders without checking."""

STARVATION_SECONDS = 0.25
"""How long a transition may stay pending before it renders without checking for urgent input."""

# Depth of nested ``batch_updates`` blocks plus the triggers deferred by
# the outermost block, per execution context.
_batch_depth: ContextVar[int] = ContextVar("pn_batch_depth", default=0)
_batch_pending: ContextVar[Optional[List[Callable[[], None]]]] = ContextVar("pn_batch_pending", default=None)

# Whether state updates in the current execution context are marked as
# transitions (see ``use_transition``).
_transition_var: ContextVar[bool] = ContextVar("pn_transition", default=False)

# Urgent input queued on the application loop and not yet run. Any thread
# increments ``_queued`` (under the lock); only the loop increments
# ``_handled``.
_queued = 0
_handled = 0
_input_lock = threading.Lock()


def queue_urgent(callback: Callable[..., Any], *args: Any) -> None:
    """Queue discrete input on the application loop, ahead of any transition render.

    The bridge queues presses, text changes, keys, back presses, and
    other discrete events this way. Work from other threads (a state
    setter called by a worker) isn't user input and doesn't come through
    here, so background updates never abandon a transition. A render pass for a transition
    that's in progress notices the queued input before its next
    component body, abandons its work, and runs again after the input
    has been handled and committed.

    Args:
        callback: Called on the application loop with ``args``.
        *args: Positional arguments for ``callback``.
    """
    global _queued
    from .runtime import get_loop

    with _input_lock:
        _queued += 1
    try:
        get_loop().call_soon_threadsafe(_run_urgent, callback, args, context=urgent_context())
    except RuntimeError:
        with _input_lock:
            _queued -= 1
        raise


def urgent_context() -> contextvars.Context:
    """A copy of the current context for work that must not inherit a transition, a batch, or a render.

    Flushes and urgent input are scheduled with it: the code that
    scheduled them may be inside ``start_transition`` or ``batch_updates``,
    but what they run is neither. Everything else, such as an active
    profiler, carries over.
    """
    from .journal import detached_context

    context = detached_context()
    context.run(_clear_scheduling)
    return context


def _clear_scheduling() -> None:
    _transition_var.set(False)
    _batch_depth.set(0)
    _batch_pending.set(None)


def _run_urgent(callback: Callable[..., Any], args: tuple[Any, ...]) -> None:
    global _handled
    _handled += 1
    callback(*args)


def urgent_input_pending() -> bool:
    """Whether input queued with [`queue_urgent`][pythonnative.scheduler.queue_urgent] hasn't run yet."""
    return _queued > _handled


def _reset_urgent_input() -> None:
    """Forget queued input (when the application loop is replaced, as in tests)."""
    global _queued, _handled
    with _input_lock:
        _queued = _handled = 0


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
    """Coalesce state updates that span ``await`` boundaries into a single re-render.

    Setters already batch automatically: every call made within one
    callback, effect, or task step lands in the same render pass, which
    the reconciler schedules on the next turn of the application loop.
    Use this block when a sequence of updates is interrupted by an
    ``await`` (a fetch between two setters, say) and should still
    commit as one pass: triggers fired inside the ``with`` block are
    deferred until it exits.

    Example:
        ```python
        import pythonnative as pn

        async def load():
            with pn.batch_updates():
                set_loading(False)
                set_items(await api.list_items())
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


def run_urgently(fn: Callable[[], None]) -> None:
    """Run ``fn`` with its state updates marked urgent, even inside a transition.

    External stores change the moment they're written, so a component
    that reads one during render can't keep showing the old value the
    way a transition keeps component state. Their re-render is urgent
    (as with React's ``useSyncExternalStore``), so every subscriber
    shows the same value.
    """
    token = _transition_var.set(False)
    try:
        fn()
    finally:
        _transition_var.reset(token)


def start_transition(fn: Callable[[], None]) -> None:
    """Mark the state updates ``fn`` makes as a transition.

    Use it where no [`use_transition`][pythonnative.use_transition] is
    at hand, such as a helper that receives a component's state setter.
    The updates render after urgent work, and the render is abandoned
    and run again if the user taps or types while it's in progress.
    Inside a component, prefer ``use_transition``, whose ``is_pending``
    flag shows that the transition hasn't committed yet.

    Only component state waits for the transition. A
    [`Store`][pythonnative.Store] or other external store changes as
    soon as it's written, so its subscribers re-render urgently.

    Example:
        ```python
        import pythonnative as pn

        def show_results(set_query, query: str) -> None:
            pn.start_transition(lambda: set_query(query))
        ```
    """
    run_in_transition(fn)


class TransitionQueue:
    """The components with state updates waiting for one reconciler's transition render.

    A state setter called in a transition doesn't change the state it
    reads during render: the update is queued on the component's hook
    state (urgent renders keep the old value), and the component is
    added here. The reconciler's transition pass applies every queued
    update in order, renders, and commits. If urgent input arrives
    before the pass flushed any native mutation, the pass is rolled
    back, which restores the queues, and it runs again after the input
    commits.

    Attributes:
        preemptions: How many times the pending transition was abandoned.
        started: Loop time when the pending transition was queued, or
            ``None`` with nothing pending.
    """

    __slots__ = ("_states", "preemptions", "started")

    def __init__(self) -> None:
        self._states: JournalDict = JournalDict()
        self.preemptions = 0
        self.started: Optional[float] = None

    def add(self, hook_state: "HookState") -> None:
        """Record that ``hook_state`` has transition updates queued."""
        if id(hook_state) not in self._states:
            self._states[id(hook_state)] = hook_state
        if self.started is None:
            from .runtime import get_loop

            self.started = get_loop().time()

    @property
    def pending(self) -> bool:
        """Whether any transition update is waiting to render."""
        return bool(self._states)

    def take(self) -> List["HookState"]:
        """Remove and return the waiting hook states (journaled, so a rollback restores them)."""
        states = list(self._states.values())
        self._states.clear()
        return states

    def must_finish(self, now: float) -> bool:
        """Whether the pending transition has been starved long enough to render without yielding."""
        return self.preemptions >= MAX_PREEMPTIONS or (
            self.started is not None and now - self.started >= STARVATION_SECONDS
        )

    def preempted(self) -> None:
        """Count one abandoned transition render."""
        self.preemptions += 1

    def committed(self) -> None:
        """Reset the starvation counters after a transition commits.

        Updates already waiting again (an effect of the commit started
        another transition) are a new transition: their clock starts now,
        so they can still yield to input.
        """
        self.preemptions = 0
        if self._states:
            from .runtime import get_loop

            self.started = get_loop().time()
        else:
            self.started = None

    def clear(self) -> None:
        """Drop waiting work (used on unmount)."""
        dict.clear(self._states)
        self.preemptions = 0
        self.started = None
