"""Hook primitives for function components.

Provides React-like hooks for managing state, effects, memoization, and
context within components decorated with
[`component`][pythonnative.component.component]. Hooks must be called at the top
level of a component (not inside conditionals or loops) so they map to
the same slot across renders. In dev mode the framework verifies this
and raises [`HookOrderError`][pythonnative.diagnostics.HookOrderError]
on a violation instead of silently cross-wiring state.

Two effect phases exist, mirroring React:

- [`use_layout_effect`][pythonnative.use_layout_effect] callbacks run
  synchronously inside the commit, after native mutations and the
  layout pass have been applied. They can measure committed frames and
  issue imperative view commands before the user sees the new frame.
- [`use_effect`][pythonnative.use_effect] callbacks (passive effects)
  run after the layout effects, at the end of the same commit. An
  effect may be an ``async def``; it runs as a task on the framework
  loop and is cancelled when its dependencies change or the component
  unmounts.

The current hook state travels in a :mod:`contextvars` context rather
than a plain global, so ``async def`` component bodies keep their hook
identity across ``await`` boundaries even when several coroutine
renders interleave on the event loop.

Hooks talk to the reconciler through the small
[`RenderOwner`][pythonnative.hooks.RenderOwner] protocol (mark a
component dirty, request a render, defer a transition, register a back
handler). That is the whole contract between the two modules.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Counter(initial: int = 0):
        count, set_count = pn.use_state(initial)
        return pn.Column(
            pn.Text(f"Count: {count}"),
            pn.Button("+", on_press=lambda: set_count(count + 1)),
        )
    ```
"""

from __future__ import annotations

import asyncio
import inspect
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from . import diagnostics
from .element import Element, Node
from .platform_metrics import SafeAreaInsets, WindowDimensions
from .scheduler import TransitionQueue, in_transition, run_in_transition, schedule_trigger
from .suspense import CoroDriver, Resource

T = TypeVar("T")

StateSetter = Callable[[Union[T, Callable[[T], T]]], None]
"""Setter returned by [`use_state`][pythonnative.use_state]: accepts a value or ``current -> new``."""

_SENTINEL = object()

# The component whose body is currently executing. A ContextVar (not a
# global or thread-local) so coroutine component bodies resume with the
# right hook state after every ``await``, no matter how renders
# interleave on the loop.
_hook_context: ContextVar[Optional["HookState"]] = ContextVar("pn_hook_state", default=None)


# ======================================================================
# Reconciler contract
# ======================================================================


class RenderOwner(Protocol):
    """What a hook needs from the object that renders its component.

    The reconciler implements this; tests may substitute a stub.
    """

    transitions: TransitionQueue

    def mark_dirty(self, vnode: Any) -> None:
        """Queue ``vnode``'s component for a local re-render."""

    def request_render(self) -> None:
        """Ask the host to flush dirty components (may be deferred)."""

    def register_back_handler(self, handler: Callable[[], bool]) -> Callable[[], None]:
        """Register a system back-press handler; returns an unregister callable."""


# ======================================================================
# Ref
# ======================================================================


class Ref(Generic[T]):
    """Mutable container returned by [`use_ref`][pythonnative.use_ref].

    A ``Ref`` holds one value on its ``current`` attribute. Mutating
    ``current`` never triggers a re-render, which makes refs the right
    place for timers, last-seen values, and imperative handles.

    When a ``Ref`` is passed to a built-in element via the ``ref=``
    prop, the reconciler populates ``current`` with the underlying
    native view (``UIView`` on iOS, ``android.view.View`` on Android,
    a Tk widget on desktop) after commit, and clears it back to
    ``None`` on unmount. Composite components (e.g.
    [`FlatList`][pythonnative.FlatList]) instead publish a typed
    controller object on ``current`` via
    [`use_imperative_handle`][pythonnative.use_imperative_handle].

    Attributes:
        current: The referenced value. ``None`` until populated.
    """

    __slots__ = ("current", "_pn_tag", "_pn_frame")

    def __init__(self, initial: Optional[T] = None) -> None:
        self.current: Optional[T] = initial
        # Internal: the native view tag, populated by the reconciler
        # when the ref is attached to a built-in element.
        self._pn_tag: Optional[int] = None
        # Internal: the last committed frame ``(x, y, w, h)``, mirrored
        # by the layout pass so Python code can read measured geometry
        # without a native round-trip.
        self._pn_frame: Optional[Tuple[float, float, float, float]] = None

    def __repr__(self) -> str:
        return f"Ref({self.current!r})"


# ======================================================================
# Hook state container
# ======================================================================


class HookState:
    """Per-instance storage for one component's hooks.

    Each component instance owns one ``HookState``. Hooks are matched
    to slots by call order, so they must always be called in the same
    order across renders. Effects scheduled during render are deferred
    (layout effects into ``_pending_layout_effects``, passive effects
    into ``_pending_effects``) and flushed by the reconciler in two
    phases after native mutations commit.

    Attributes:
        states: One entry per ``use_state`` / ``use_reducer`` call.
        effects: One ``(deps, cleanup)`` tuple per ``use_effect`` call.
        layout_effects: One ``(deps, cleanup)`` tuple per
            ``use_layout_effect`` call.
        memos: One ``(deps, value)`` tuple per ``use_memo`` / ``use_callback``.
        refs: One [`Ref`][pythonnative.Ref] per ``use_ref`` call.
        owner: The [`RenderOwner`][pythonnative.hooks.RenderOwner]
            (reconciler) this component is mounted in, or ``None``.
        vnode: The reconciler's node for this component, or ``None``.
    """

    __slots__ = (
        "states",
        "effects",
        "layout_effects",
        "memos",
        "refs",
        "resources",
        "state_index",
        "effect_index",
        "layout_effect_index",
        "memo_index",
        "ref_index",
        "resource_index",
        "context_deps",
        "owner",
        "vnode",
        "_pending_effects",
        "_pending_layout_effects",
        "_pending_effects_mark",
        "_pending_layout_effects_mark",
        "_dirty",
        "_hook_log",
        "_hook_signature",
        "_component_name",
        "_async_driver",
    )

    def __init__(self) -> None:
        self.states: List[Any] = []
        self.effects: List[Tuple[Any, Any]] = []
        self.layout_effects: List[Tuple[Any, Any]] = []
        self.memos: List[Tuple[Any, Any]] = []
        self.refs: List[Ref] = []
        # One ``(deps, Resource)`` per ``use_resource`` call.
        self.resources: List[Tuple[Any, Resource]] = []
        self.state_index: int = 0
        self.effect_index: int = 0
        self.layout_effect_index: int = 0
        self.memo_index: int = 0
        self.ref_index: int = 0
        self.resource_index: int = 0
        # Contexts read during the last completed render, keyed by
        # ``id(context)``. The reconciler consults this when a
        # Provider's value changes so consumers re-render even when a
        # memoized ancestor skipped (reactive context).
        self.context_deps: Dict[int, Any] = {}
        self.owner: Optional[RenderOwner] = None
        self.vnode: Any = None
        self._pending_effects: List[Tuple[int, Callable, Any]] = []
        self._pending_layout_effects: List[Tuple[int, Callable, Any]] = []
        # Cleared by the reconciler after each successful render.
        # ``use_state`` / ``use_reducer`` setters flip it to ``True``
        # whenever they actually mutate state, so a memoized component
        # still re-renders even when its props didn't change.
        self._dirty: bool = False
        # Dev-mode hook-order guard: the sequence of hook kinds called
        # during the in-flight render, and the signature captured from
        # the first successful render.
        self._hook_log: Optional[List[str]] = None
        self._hook_signature: Optional[List[str]] = None
        self._component_name: str = ""
        # For ``async def`` components: the CoroDriver running the
        # in-flight body, cancelled when a newer render supersedes it.
        self._async_driver: Optional[CoroDriver] = None
        # Effect-queue lengths at ``begin_render``, so a suspended
        # render can be rolled back without double-queueing effects.
        self._pending_effects_mark: int = 0
        self._pending_layout_effects_mark: int = 0

    # ------------------------------------------------------------------
    # Render lifecycle
    # ------------------------------------------------------------------

    def begin_render(self, component_name: str = "") -> None:
        """Prepare for a render pass: reset cursors and the dev-mode hook log."""
        self.state_index = 0
        self.effect_index = 0
        self.layout_effect_index = 0
        self.memo_index = 0
        self.ref_index = 0
        self.resource_index = 0
        self.context_deps = {}
        if component_name:
            self._component_name = component_name
        self._hook_log = [] if diagnostics.is_dev() else None
        self._pending_effects_mark = len(self._pending_effects)
        self._pending_layout_effects_mark = len(self._pending_layout_effects)

    def abort_render(self) -> None:
        """Roll back a suspended render's effect queue.

        A suspended body re-runs from the top on retry, so any effects
        it queued before suspending would otherwise be queued twice.
        """
        del self._pending_effects[self._pending_effects_mark :]
        del self._pending_layout_effects[self._pending_layout_effects_mark :]
        self._hook_log = None

    def finish_render(self) -> None:
        """Finalize a successful render: lock in / verify the hook signature.

        Raises:
            HookOrderError: In dev mode, when this render called fewer
                hooks than the previous one.
        """
        log = self._hook_log
        self._hook_log = None
        if log is None:
            return
        if self._hook_signature is None:
            self._hook_signature = log
            return
        if len(log) < len(self._hook_signature):
            missing = self._hook_signature[len(log)]
            raise diagnostics.HookOrderError(
                f"{self._component_name or 'Component'} rendered fewer hooks than the previous "
                f"render (expected {missing!r} at position {len(log) + 1}). Hooks must be called "
                "unconditionally, in the same order, on every render."
            )

    def record_hook(self, kind: str) -> None:
        """Record a hook call for the dev-mode order guard.

        Raises:
            HookOrderError: In dev mode, when the hook at this position
                differs from (or extends past) the previous render.
        """
        log = self._hook_log
        if log is None:
            return
        position = len(log)
        log.append(kind)
        signature = self._hook_signature
        if signature is None:
            return
        if position >= len(signature):
            raise diagnostics.HookOrderError(
                f"{self._component_name or 'Component'} rendered more hooks than the previous "
                f"render ({kind!r} at position {position + 1}). Hooks must be called "
                "unconditionally, in the same order, on every render."
            )
        if signature[position] != kind:
            raise diagnostics.HookOrderError(
                f"{self._component_name or 'Component'} called {kind!r} at position "
                f"{position + 1}, but the previous render called {signature[position]!r} there. "
                "Hooks must be called unconditionally, in the same order, on every render."
            )

    def reset_hook_signature(self) -> None:
        """Forget the recorded hook signature (used by Fast Refresh)."""
        self._hook_signature = None

    # ------------------------------------------------------------------
    # Effects
    # ------------------------------------------------------------------

    def flush_layout_effects(self) -> None:
        """Run layout effects queued during render (commit phase, pre-paint)."""
        pending = self._pending_layout_effects
        self._pending_layout_effects = []
        self._pending_layout_effects_mark = 0
        for idx, effect_fn, deps in pending:
            _, prev_cleanup = self.layout_effects[idx]
            _run_cleanup(prev_cleanup)
            cleanup = _activate_effect(effect_fn)
            self.layout_effects[idx] = (list(deps) if deps is not None else None, cleanup)

    def flush_pending_effects(self) -> None:
        """Run passive effects queued during render, after native commit.

        For each pending effect, the previous cleanup is invoked first
        (if any), then the new effect callback. The new return value
        becomes the next cleanup. Effects that are ``async def`` (or
        that return an awaitable) run as tasks on the framework loop;
        their cleanup cancels the task, and a callable returned by the
        coroutine runs as an additional cleanup once it completed.
        """
        pending = self._pending_effects
        self._pending_effects = []
        self._pending_effects_mark = 0
        for idx, effect_fn, deps in pending:
            _, prev_cleanup = self.effects[idx]
            _run_cleanup(prev_cleanup)
            cleanup = _activate_effect(effect_fn)
            self.effects[idx] = (list(deps) if deps is not None else None, cleanup)

    def cleanup_all_effects(self) -> None:
        """Run every outstanding cleanup function, then clear state.

        Layout-effect cleanups run before passive-effect cleanups,
        matching the mount order in reverse. Also cancels in-flight
        resources and any pending ``async def`` body. Called when the
        component instance is unmounted by the reconciler.
        """
        for i, (_deps, cleanup) in enumerate(self.layout_effects):
            _run_cleanup(cleanup)
            self.layout_effects[i] = (_SENTINEL, None)
        for i, (_deps, cleanup) in enumerate(self.effects):
            _run_cleanup(cleanup)
            self.effects[i] = (_SENTINEL, None)
        self._pending_effects = []
        self._pending_layout_effects = []
        self._pending_effects_mark = 0
        self._pending_layout_effects_mark = 0
        for _deps, resource in self.resources:
            try:
                resource.cancel()
            except Exception:
                pass
        self.resources = []
        driver = self._async_driver
        self._async_driver = None
        if driver is not None:
            driver.cancel()

    def detach(self) -> None:
        """Break the back-references to the reconciler (on unmount).

        Lets the unmounted component's hook state (and the closures it
        captured) be freed by plain refcounting, which matters on iOS
        where the cyclic GC is disabled.
        """
        self.owner = None
        self.vnode = None


# ======================================================================
# Context helpers (framework-internal)
# ======================================================================


def current_hook_state() -> Optional[HookState]:
    """Return the active ``HookState``, or ``None`` if no render is in flight."""
    return _hook_context.get()


def install_hook_state(state: Optional[HookState]) -> Token[Optional[HookState]]:
    """Install ``state`` as the active ``HookState``; returns the reset token."""
    return _hook_context.set(state)


def restore_hook_state(token: Token[Optional[HookState]]) -> None:
    """Restore the hook state that was active before ``install_hook_state``."""
    _hook_context.reset(token)


def _require_hook_state(hook_name: str) -> HookState:
    ctx = _hook_context.get()
    if ctx is None:
        raise RuntimeError(f"{hook_name} must be called inside a @component function")
    return ctx


def _deps_changed(prev: Any, current: Any) -> bool:
    """Return whether the dependency arrays differ enough to re-run an effect."""
    if prev is _SENTINEL:
        return True
    if prev is None or current is None:
        return True
    if len(prev) != len(current):
        return True
    return any(p is not c and p != c for p, c in zip(prev, current))


def _run_cleanup(cleanup: Any) -> None:
    if callable(cleanup):
        try:
            cleanup()
        except Exception as exc:
            # Never let a failing cleanup abort an unmount; surface it
            # through the RedBox in dev mode, a warning otherwise.
            if not diagnostics.report_error(exc, phase="effect cleanup"):
                diagnostics.warn(f"Effect cleanup raised {exc!r}")


def _activate_effect(effect_fn: Callable) -> Any:
    """Invoke an effect callback, running coroutine effects as tasks.

    Synchronous effects return their cleanup directly. When the effect
    is an ``async def`` (or returns an awaitable), the coroutine runs
    as a task on the framework loop and the returned cleanup cancels
    it; if the coroutine already finished and returned a callable, that
    callable runs as the cleanup instead.
    """
    result = effect_fn()
    if not inspect.isawaitable(result):
        return result

    from .runtime import run_async

    future = run_async(result)

    def _observe(fut: Any) -> None:
        # Surface unhandled async-effect crashes instead of letting the
        # future's exception vanish unobserved: RedBox in dev mode,
        # traceback in production.
        if fut.cancelled():
            return
        exc = fut.exception()
        if exc is None or isinstance(exc, asyncio.CancelledError):
            return
        if not diagnostics.report_error(exc, phase="async effect"):
            import traceback

            traceback.print_exception(type(exc), exc, exc.__traceback__)

    future.add_done_callback(_observe)

    def _cleanup() -> None:
        if future.cancelled():
            return
        if future.done():
            if future.exception() is None:
                returned = future.result()
                if callable(returned):
                    try:
                        returned()
                    except Exception:
                        pass
            return
        future.cancel()

    return _cleanup


def _notify_state_changed(ctx: HookState) -> None:
    """Mark ``ctx``'s component dirty and schedule a render after a state change.

    Enqueuing the owning node in the reconciler's dirty set is what
    makes the subsequent render *local*: the host's trigger flushes
    only the components marked here rather than the whole app. The
    dirty mark is eager (so several setters coalesce), while the render
    request respects [`batch_updates`][pythonnative.scheduler.batch_updates] and
    defers to a later loop turn inside a transition (see
    [`use_transition`][pythonnative.use_transition]).
    """
    ctx._dirty = True
    owner = ctx.owner
    if owner is None:
        return
    if ctx.vnode is not None:
        owner.mark_dirty(ctx.vnode)
    if in_transition():
        owner.transitions.defer(owner.request_render)
    else:
        schedule_trigger(owner.request_render)


# ======================================================================
# State hooks
# ======================================================================


@overload
def use_state() -> Tuple[Optional[Any], StateSetter[Any]]: ...


@overload
def use_state(initial: Callable[[], T]) -> Tuple[T, StateSetter[T]]: ...


@overload
def use_state(initial: T) -> Tuple[T, StateSetter[T]]: ...


def use_state(initial: Any = None) -> Tuple[Any, StateSetter[Any]]:
    """Return ``(value, setter)`` for component-local state.

    State persists across re-renders of the same component instance.
    The setter accepts a value or a ``current -> new`` callable; calling
    it with an unchanged value is a no-op (no re-render).

    Args:
        initial: Initial state value. If callable, it is invoked once on
            the first render (lazy initialization).

    Returns:
        A 2-tuple ``(value, setter)`` where ``value`` is the current
        state and ``setter`` updates it (and triggers a re-render).

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Counter():
            count, set_count = pn.use_state(0)
            return pn.Button(
                f"Count: {count}",
                on_press=lambda: set_count(count + 1),
            )
        ```
    """
    ctx = _require_hook_state("use_state")
    ctx.record_hook("use_state")

    idx = ctx.state_index
    ctx.state_index += 1

    if idx >= len(ctx.states):
        val = initial() if callable(initial) else initial
        ctx.states.append(val)

    current = ctx.states[idx]

    def setter(new_value: Any) -> None:
        if callable(new_value):
            new_value = new_value(ctx.states[idx])
        if ctx.states[idx] is not new_value and ctx.states[idx] != new_value:
            ctx.states[idx] = new_value
            _notify_state_changed(ctx)

    return current, setter


def use_reducer(
    reducer: Callable[[T, Any], T], initial_state: Union[T, Callable[[], T]]
) -> Tuple[T, Callable[[Any], None]]:
    """Return ``(state, dispatch)`` for reducer-based state management.

    A reducer is a pure function that takes the current state and an
    action and returns the next state. Use it instead of
    [`use_state`][pythonnative.use_state] when state transitions are
    complex enough that centralizing them in one function aids
    readability and testing.

    Args:
        reducer: ``reducer(current_state, action) -> new_state``.
            The component re-renders only when ``reducer`` returns a
            value different from the current state.
        initial_state: Initial state value, or a callable invoked once
            on the first render.

    Returns:
        A 2-tuple ``(state, dispatch)`` where ``dispatch`` runs the
        reducer with the supplied action.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    ctx = _require_hook_state("use_reducer")
    ctx.record_hook("use_reducer")

    idx = ctx.state_index
    ctx.state_index += 1

    if idx >= len(ctx.states):
        val = initial_state() if callable(initial_state) else initial_state
        ctx.states.append(val)

    current = ctx.states[idx]

    def dispatch(action: Any) -> None:
        new_state = reducer(ctx.states[idx], action)
        if ctx.states[idx] is not new_state and ctx.states[idx] != new_state:
            ctx.states[idx] = new_state
            _notify_state_changed(ctx)

    return current, dispatch


# ======================================================================
# Effect hooks
# ======================================================================


def use_effect(effect: Callable[[], Any], deps: Optional[list] = None) -> None:
    """Schedule a side effect to run after the native commit.

    Effects are queued during the render pass and flushed once the
    reconciler has finished applying all native-view mutations, which
    means effect callbacks can safely measure layout or interact with
    committed native views.

    The ``deps`` argument controls when the effect re-runs:

    - ``None``: every render.
    - ``[]``: mount only.
    - ``[a, b]``: when ``a`` or ``b`` change (compared by identity, then ``==``).

    A synchronous ``effect`` may return a cleanup callable; the previous
    cleanup runs before the next effect (and on unmount).

    An **async** ``effect`` (an ``async def``) runs as a task on the
    framework loop. When ``deps`` change or the component unmounts, the
    in-flight task is cancelled (:class:`asyncio.CancelledError` is
    raised at its current ``await``), giving async effects structured
    cancellation for free. If the coroutine finishes and returns a
    callable, that callable runs as the cleanup instead.

    Args:
        effect: A zero-arg callable invoked after commit: either a
            synchronous function (optionally returning a cleanup
            callable) or an ``async def``.
        deps: Dependency list, or ``None`` to run on every render.

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        import asyncio
        import time

        import pythonnative as pn

        @pn.component
        def Clock():
            now, set_now = pn.use_state("")

            async def tick():
                while True:
                    set_now(time.strftime("%H:%M:%S"))
                    await asyncio.sleep(1)

            pn.use_effect(tick, [])
            return pn.Text(now)
        ```
    """
    ctx = _require_hook_state("use_effect")
    ctx.record_hook("use_effect")

    idx = ctx.effect_index
    ctx.effect_index += 1

    if idx >= len(ctx.effects):
        ctx.effects.append((_SENTINEL, None))
        ctx._pending_effects.append((idx, effect, deps))
        return

    prev_deps, _prev_cleanup = ctx.effects[idx]
    if _deps_changed(prev_deps, deps):
        ctx._pending_effects.append((idx, effect, deps))


def use_layout_effect(effect: Callable[[], Any], deps: Optional[list] = None) -> None:
    """Schedule a side effect that runs synchronously inside the commit.

    Like [`use_effect`][pythonnative.use_effect], but the callback
    fires *before* passive effects, immediately after native mutations
    and the layout pass are applied. Use it when you need to measure a
    committed frame (via a [`Ref`][pythonnative.Ref]) or issue an
    imperative view command before the user sees the new frame, for
    example scrolling a list into position on mount.

    Prefer ``use_effect`` for everything else; layout effects block the
    commit, so heavy work here delays the frame.

    Args:
        effect: A zero-arg callable invoked during commit. Optionally
            returns a cleanup callable.
        deps: Dependency list, or ``None`` to run on every render.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    ctx = _require_hook_state("use_layout_effect")
    ctx.record_hook("use_layout_effect")

    idx = ctx.layout_effect_index
    ctx.layout_effect_index += 1

    if idx >= len(ctx.layout_effects):
        ctx.layout_effects.append((_SENTINEL, None))
        ctx._pending_layout_effects.append((idx, effect, deps))
        return

    prev_deps, _prev_cleanup = ctx.layout_effects[idx]
    if _deps_changed(prev_deps, deps):
        ctx._pending_layout_effects.append((idx, effect, deps))


# ======================================================================
# Memoization hooks
# ======================================================================


def use_memo(factory: Callable[[], T], deps: list) -> T:
    """Return a memoized value that is recomputed only when ``deps`` change.

    Use this for expensive computations whose inputs change rarely. For
    cheap computations, plain inline code is faster (memoization itself
    has overhead).

    Args:
        factory: Zero-arg callable returning the value.
        deps: Dependency list. The value is recomputed when any element
            differs from the previous render.

    Returns:
        The cached or freshly computed value.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    ctx = _require_hook_state("use_memo")
    ctx.record_hook("use_memo")

    idx = ctx.memo_index
    ctx.memo_index += 1

    if idx >= len(ctx.memos):
        value = factory()
        ctx.memos.append((list(deps), value))
        return value

    prev_deps, prev_value = ctx.memos[idx]
    if not _deps_changed(prev_deps, deps):
        return prev_value

    value = factory()
    ctx.memos[idx] = (list(deps), value)
    return value


F = TypeVar("F", bound=Callable[..., Any])


def use_callback(callback: F, deps: list) -> F:
    """Return a stable reference to ``callback``, refreshed when ``deps`` change.

    Equivalent to ``use_memo(lambda: callback, deps)``. Useful when
    passing a function as a prop to a memoized child component, so the
    child doesn't see a fresh function identity on every render.

    Args:
        callback: The callable to memoize.
        deps: Dependency list controlling when the reference refreshes.

    Returns:
        A callable with stable identity across renders (until ``deps`` change).
    """
    return use_memo(lambda: callback, deps)


def use_ref(initial: Optional[T] = None) -> Ref[T]:
    """Return a [`Ref`][pythonnative.Ref] that persists across renders.

    Refs are useful for storing values that must survive renders without
    triggering them: timers, last-seen values, native handles, and so on.

    ``ref.current`` is also populated by the reconciler with the
    underlying native view when the ref is passed via the ``ref=`` prop
    on a built-in element, and cleared to ``None`` when that element
    unmounts. Composite components such as
    [`FlatList`][pythonnative.FlatList] publish a typed controller
    object instead (see
    [`use_imperative_handle`][pythonnative.use_imperative_handle]).

    Args:
        initial: Value placed at ``ref.current`` on first render.

    Returns:
        A [`Ref`][pythonnative.Ref]. Mutations to ``ref.current`` do
        *not* trigger re-renders.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    ctx = _require_hook_state("use_ref")
    ctx.record_hook("use_ref")

    idx = ctx.ref_index
    ctx.ref_index += 1

    if idx >= len(ctx.refs):
        ref: Ref[T] = Ref(initial)
        ctx.refs.append(ref)
        return ref

    return ctx.refs[idx]


def use_imperative_handle(
    ref: Optional[Ref[Any]],
    factory: Callable[[], Any],
    deps: Optional[list] = None,
) -> None:
    """Publish a controller object on ``ref.current``.

    The composite-component counterpart to passing ``ref=`` to a
    built-in element. Call it inside a component that accepts a
    ``ref`` prop to expose a curated imperative API (rather than the
    raw native view) to the parent. The handle is installed during the
    commit's layout-effect phase and cleared back to ``None`` on
    unmount.

    Args:
        ref: The [`Ref`][pythonnative.Ref] received via the component's
            ``ref`` prop. ``None`` is allowed (the parent didn't
            request a handle), in which case this is a no-op.
        factory: Zero-arg callable returning the handle object.
        deps: Dependency list controlling when the handle is rebuilt.
            ``None`` rebuilds on every render, matching effects.

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        @pn.component
        def VideoPlayer(source: str, ref: pn.Ref | None = None):
            pn.use_imperative_handle(ref, lambda: PlayerController(...), [source])
            return pn.View(...)
        ```
    """

    def _install() -> Optional[Callable[[], None]]:
        if ref is None:
            return None
        ref.current = factory()

        def _clear() -> None:
            ref.current = None

        return _clear

    use_layout_effect(_install, deps)


# ======================================================================
# Async hooks
# ======================================================================


def use_resource(fetcher: Callable[[], Any], deps: Optional[list] = None) -> Resource[Any]:
    """Start an async fetch and cache it across renders.

    The fetch starts immediately (during render, not after commit) and
    the resulting [`Resource`][pythonnative.Resource] is cached until
    ``deps`` change, at which point the old fetch is cancelled and a
    new one starts. Because results are cached, re-renders resolve
    instantly; only genuinely new data suspends.

    Consume the resource with ``resource.read()`` (suspends the render
    while pending; pair with a [`Suspense`][pythonnative.Suspense]
    boundary) or ``await resource`` inside an ``async def`` component.
    Errors raised by the fetcher re-raise at the read site, so an
    enclosing [`ErrorBoundary`][pythonnative.ErrorBoundary] catches
    failures declaratively.

    Args:
        fetcher: Zero-arg ``async def`` (or plain callable) producing
            the value. Synchronous fetchers resolve immediately and
            never suspend.
        deps: Dependency list controlling when to refetch. Defaults to
            ``[]`` (fetch once per component instance).

    Returns:
        The cached [`Resource`][pythonnative.Resource].

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        @pn.component
        async def UserCard(user_id: str):
            user = await pn.use_resource(lambda: api.get_user(user_id), [user_id])
            return pn.Text(user["name"])
        ```
    """
    from .suspense import start_resource

    ctx = _require_hook_state("use_resource")
    ctx.record_hook("use_resource")

    idx = ctx.resource_index
    ctx.resource_index += 1
    deps = [] if deps is None else deps

    if idx >= len(ctx.resources):
        resource = start_resource(fetcher)
        ctx.resources.append((list(deps), resource))
        return resource

    prev_deps, prev_resource = ctx.resources[idx]
    if not _deps_changed(prev_deps, deps):
        return prev_resource

    prev_resource.cancel()
    resource = start_resource(fetcher)
    ctx.resources[idx] = (list(deps), resource)
    return resource


def use_transition() -> Tuple[bool, Callable[[Callable[[], None]], None]]:
    """Return ``(is_pending, start_transition)`` for low-priority updates.

    State updates made inside ``start_transition(fn)`` are marked as
    *transitions*: instead of re-rendering synchronously, their render
    is deferred to a later turn of the framework loop, so urgent
    updates (typing, presses) queued in the meantime render first.
    ``is_pending`` is ``True`` from the moment ``start_transition`` is
    called until the deferred render has committed, which is exactly
    when to show a lightweight busy indicator.

    Returns:
        A 2-tuple ``(is_pending, start_transition)``.

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        @pn.component
        def Search():
            query, set_query = pn.use_state("")
            results_for, set_results_for = pn.use_state("")
            is_pending, start_transition = pn.use_transition()

            def on_change(text):
                set_query(text)  # urgent: keep the input responsive
                start_transition(lambda: set_results_for(text))

            return pn.Column(
                pn.TextInput(value=query, on_change=on_change),
                pn.ActivityIndicator() if is_pending else Results(results_for),
            )
        ```
    """
    ctx = _require_hook_state("use_transition")

    is_pending, set_pending = use_state(False)

    def start_transition(fn: Callable[[], None]) -> None:
        owner = ctx.owner
        if owner is None:
            fn()
            return
        set_pending(True)
        run_in_transition(fn)
        owner.transitions.on_complete(lambda: set_pending(False))

    start = use_callback(start_transition, [])
    return is_pending, start


def use_deferred_value(value: T) -> T:
    """Return a copy of ``value`` that lags behind during fast updates.

    The returned value updates in a deferred (transition-priority)
    render after the urgent render that changed ``value`` has
    committed. Pass the deferred value to expensive subtrees (a
    filtered list, a chart) so the urgent part of the UI stays
    responsive while the expensive part catches up a beat later.

    Args:
        value: The latest value.

    Returns:
        The previous value while a newer one is still being adopted,
        then the latest value.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    _require_hook_state("use_deferred_value")

    deferred, set_deferred = use_state(value)

    def _adopt() -> None:
        run_in_transition(lambda: set_deferred(value))

    use_effect(_adopt, [value])
    return deferred


@dataclass(frozen=True)
class QueryResult(Generic[T]):
    """Snapshot of a [`use_query`][pythonnative.use_query] subscription.

    Attributes:
        data: The most recent successful result, or the ``initial``
            value before the first fetch completes.
        loading: ``True`` while a fetch is in flight (including the
            initial fetch and any refetches).
        error: The exception raised by the most recent failed fetch,
            or ``None`` if no fetch has failed since the last success.
        refetch: A zero-arg callable that triggers a refetch. Stable
            across renders.
    """

    data: Optional[T] = None
    loading: bool = True
    error: Optional[BaseException] = None
    refetch: Callable[[], None] = field(default=lambda: None)


def use_query(
    fetcher: Callable[[], Awaitable[T]],
    deps: Optional[list] = None,
    *,
    initial: Optional[T] = None,
) -> QueryResult[T]:
    """Subscribe to an async fetcher and re-render when its result changes.

    The fetcher is called on mount and any time ``deps`` change, with
    cancellation propagated when the component unmounts mid-fetch.

    Args:
        fetcher: Zero-arg ``async`` callable that resolves to the
            current data.
        deps: Dependency list. Refetches whenever any entry changes.
        initial: Optional starting value for ``data`` before the
            first fetch completes.

    Returns:
        A frozen [`QueryResult`][pythonnative.QueryResult] with
        ``data`` / ``loading`` / ``error`` / ``refetch``.

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        @pn.component
        def UserCard(user_id: str):
            q = pn.use_query(lambda: api.get_user(user_id), [user_id])
            if q.loading:
                return pn.Text("Loading...")
            if q.error:
                return pn.Text(f"Error: {q.error}")
            return pn.Text(q.data["name"])
        ```
    """
    from .runtime import run_async

    state, set_state = use_state(lambda: QueryResult[T](data=initial, loading=True))
    nonce, set_nonce = use_state(0)

    refetch = use_callback(lambda: set_nonce(lambda n: n + 1), [])

    # Surface the stable refetch callable on every returned result.
    if state.refetch is not refetch:
        state = replace(state, refetch=refetch)

    def _start_fetch() -> Callable[[], None]:
        set_state(lambda s: replace(s, loading=True, error=None))

        async def _runner() -> None:
            try:
                data = await fetcher()
                set_state(lambda s: replace(s, data=data, loading=False, error=None))
            except asyncio.CancelledError:
                raise
            except BaseException as exc:  # pragma: no cover - surfaced to user
                failure = exc
                set_state(lambda s: replace(s, loading=False, error=failure))

        future = run_async(_runner())

        def _cancel() -> None:
            future.cancel()

        return _cancel

    effect_deps: List[Any] = list(deps or []) + [nonce]
    use_effect(_start_fetch, effect_deps)

    return state


@dataclass(frozen=True)
class MutationState(Generic[T]):
    """Snapshot of a [`use_mutation`][pythonnative.use_mutation] subscription.

    Attributes:
        data: The most recent successful return value of the mutator,
            or ``None`` if no mutation has succeeded yet.
        loading: ``True`` while a mutation is in flight.
        error: The exception raised by the most recent failed
            mutation, or ``None``.
    """

    data: Optional[T] = None
    loading: bool = False
    error: Optional[BaseException] = None


class MutationCall(Generic[T]):
    """Awaitable handle returned by a mutator trigger.

    Returned by the second element of the
    [`use_mutation`][pythonnative.use_mutation] tuple. Awaiting the
    handle resolves to the mutator's return value (or re-raises its
    exception); discarding the handle is safe. Python won't warn
    about an unawaited coroutine because this is a plain object.

    Example:
        ```python
        # Fire-and-forget:
        save_button.on_press = lambda: mutate(post)

        # Or await for the result:
        async def submit():
            try:
                created = await mutate(post)
            except ApiError as exc:
                await pn.Alert.show(title="Save failed", message=str(exc))
        ```
    """

    __slots__ = ("_future",)

    def __init__(self, future: Any) -> None:
        self._future = future

    def __await__(self) -> Any:
        future = self._future
        if isinstance(future, asyncio.Future):
            return future.__await__()
        return asyncio.wrap_future(future).__await__()

    def cancel(self) -> bool:
        """Cancel the underlying mutation. Returns whether cancellation succeeded."""
        return self._future.cancel()

    def done(self) -> bool:
        """Whether the underlying mutation has finished."""
        return self._future.done()


def use_mutation(
    mutator: Callable[..., Awaitable[T]],
) -> Tuple[MutationState[T], Callable[..., MutationCall[T]]]:
    """Wrap an async mutator with loading/error state and a trigger.

    Returns ``(state, mutate)``. Call ``mutate(*args, **kwargs)`` to
    invoke the mutator; ``state`` reflects loading/error/data and
    re-renders on each transition. ``mutate`` returns a
    [`MutationCall`][pythonnative.MutationCall] you can ``await`` for
    the result, or discard for fire-and-forget.

    Args:
        mutator: An ``async`` callable that performs the side effect
            and returns the resulting data.

    Returns:
        A 2-tuple ``(state, mutate)``.

    Example:
        ```python
        @pn.component
        def NewPostForm():
            state, save = pn.use_mutation(api.create_post)

            return pn.Column(
                pn.Button("Save", on_press=lambda: save(post)),
                state.loading and pn.Text("Saving..."),
                state.error and pn.Text(str(state.error)),
            )
        ```
    """
    from .runtime import run_async

    state, set_state = use_state(lambda: MutationState[T]())
    # The trigger is identity-stable across renders (like ``set_state``)
    # so it can sit in effect deps or be passed to memoized children;
    # it always calls the latest ``mutator``.
    latest = use_ref(mutator)
    latest.current = mutator

    def _make_mutate() -> Callable[..., MutationCall[T]]:
        def mutate(*args: Any, **kwargs: Any) -> MutationCall[T]:
            set_state(lambda s: replace(s, loading=True, error=None))
            fn = latest.current

            async def _runner() -> T:
                try:
                    data = await fn(*args, **kwargs)
                    set_state(lambda s: replace(s, data=data, loading=False, error=None))
                    return data
                except asyncio.CancelledError:
                    set_state(lambda s: replace(s, loading=False))
                    raise
                except BaseException as exc:
                    failure = exc
                    set_state(lambda s: replace(s, loading=False, error=failure))
                    raise

            future = run_async(_runner())
            return MutationCall[T](future)

        return mutate

    mutate_ref: Ref[Optional[Callable[..., MutationCall[T]]]] = use_ref(None)
    if mutate_ref.current is None:
        mutate_ref.current = _make_mutate()
    return state, mutate_ref.current


# ======================================================================
# External subscriptions
# ======================================================================


def use_subscription(subscribe: Callable[[Callable[[], None]], Callable[[], None]], get_snapshot: Callable[[], T]) -> T:
    """Subscribe to an external store and re-render when its snapshot changes.

    The Pythonic counterpart of React's ``useSyncExternalStore``: the
    platform-metric hooks below are built on it, and it's the right
    primitive for app-level stores that live outside the component
    tree.

    Args:
        subscribe: ``subscribe(on_change) -> unsubscribe``. Called once
            on mount; ``on_change`` must be invoked whenever the store
            changes.
        get_snapshot: Zero-arg callable returning the current value.
            Re-read on every render.

    Returns:
        The current snapshot.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    _require_hook_state("use_subscription")
    _, set_tick = use_state(0)

    def _subscribe() -> Callable[[], None]:
        return subscribe(lambda: set_tick(lambda n: n + 1))

    use_effect(_subscribe, [])
    return get_snapshot()


def use_window_dimensions() -> WindowDimensions:
    """Return the current viewport size and re-render when it changes.

    Equivalent to React Native's ``useWindowDimensions``. The values
    are pushed by the screen host whenever the platform reports a new
    size (initial layout, rotation, multitasking split-view).

    Returns:
        A [`WindowDimensions`][pythonnative.platform_metrics.WindowDimensions]
        named tuple with ``width`` and ``height`` floats in layout
        units (pt on iOS, dp on Android). Both are ``0.0`` until the
        screen host has run its first layout pass. Being a tuple, it
        unpacks (``width, height = pn.use_window_dimensions()``) and
        compares by value.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    from . import platform_metrics

    return use_subscription(platform_metrics.subscribe, platform_metrics.get_window_dimensions)


def use_safe_area_insets() -> SafeAreaInsets:
    """Return the current safe-area insets and re-render on change.

    Mirrors ``react-native-safe-area-context``'s ``useSafeAreaInsets``.

    Returns:
        A [`SafeAreaInsets`][pythonnative.platform_metrics.SafeAreaInsets]
        named tuple with ``top``, ``left``, ``bottom``, and ``right``
        floats in layout units (pt on iOS, dp on Android).

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    from . import platform_metrics

    return use_subscription(platform_metrics.subscribe, platform_metrics.get_safe_area_insets)


def use_keyboard_height() -> float:
    """Return the on-screen keyboard height (or 0) and re-render on change.

    Useful for custom layout that needs to react to keyboard
    show/hide events. Most apps should use
    [`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView] instead
    of reading this directly.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    from . import platform_metrics

    return use_subscription(platform_metrics.subscribe, platform_metrics.get_keyboard_height)


def use_color_scheme() -> str:
    """Return the effective color scheme and re-render when it changes.

    Equivalent to React Native's ``useColorScheme``. The system value
    is published by the screen host; an app-level override set through
    [`appearance.set_color_scheme`][pythonnative.appearance.set_color_scheme]
    takes precedence.

    Returns:
        ``"light"`` or ``"dark"``.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    from . import appearance

    return use_subscription(appearance.subscribe, appearance.get_color_scheme)


# ======================================================================
# Context
# ======================================================================


class Context(Generic[T]):
    """A value shared with a subtree, created by [`create_context`][pythonnative.create_context].

    Provide a value with [`Provider`][pythonnative.hooks.Context.Provider]
    and read it with [`use_context`][pythonnative.use_context]. A
    ``Context`` is itself an element type: ``ctx.Provider(value, ...)``
    returns an element whose ``type`` is ``ctx``.

    Context is *reactive*: when a Provider's value changes, every
    component that read the context on its last render re-renders,
    even if a memoized ancestor skipped its own re-render.

    Attributes:
        default: The value returned when no Provider ancestor exists.
        name: Optional label for diagnostics.
    """

    __slots__ = ("default", "name", "_stack")

    def __init__(self, default: T, name: Optional[str] = None) -> None:
        self.default = default
        self.name = name
        self._stack: List[T] = []

    def Provider(self, value: T, *children: Node, key: Optional[str] = None) -> Element:
        """Provide ``value`` to every descendant of ``children``.

        A Provider contributes no native view of its own; its children
        mount directly into the surrounding native parent.

        When ``value`` differs from the previous render (identity, then
        ``==``), every descendant that read the context re-renders,
        including descendants of memoized components that skipped.

        Args:
            value: Value made available to descendants.
            *children: Subtree(s) under which the provider applies.
            key: Stable identity for keyed reconciliation.

        Example:
            ```python
            Theme = pn.create_context({"primary": "#007AFF"})

            @pn.component
            def App():
                return Theme.Provider({"primary": "#FF0000"}, Header(), Body())
            ```
        """
        return Element(self, {"value": value}, children, key=key)

    def current(self) -> T:
        """Return the innermost provided value, or ``default``."""
        return self._stack[-1] if self._stack else self.default

    def __repr__(self) -> str:
        return f"<Context {self.name or id(self):x}>" if self.name is None else f"<Context {self.name}>"

    # Rendering support: the reconciler pushes/pops provided values
    # while it walks a Provider's subtree.

    def _push(self, value: T) -> None:
        self._stack.append(value)

    def _pop(self) -> None:
        self._stack.pop()


def create_context(default: T = None, *, name: Optional[str] = None) -> Context[T]:  # type: ignore[assignment,unused-ignore]
    """Create a new context with an optional default value.

    Args:
        default: Returned by [`use_context`][pythonnative.use_context]
            when there is no enclosing Provider.
        name: Optional label shown in diagnostics.

    Returns:
        A fresh [`Context`][pythonnative.Context].

    Example:
        ```python
        Theme = pn.create_context({"primary": "#007AFF"}, name="Theme")
        ```
    """
    return Context(default, name=name)


def use_context(context: Context[T]) -> T:
    """Read the current value of ``context`` from the nearest Provider.

    If no enclosing Provider exists, returns the context's default.
    The component is registered as a subscriber: when the nearest
    Provider's value changes, the component re-renders even if a
    memoized ancestor skipped.

    Args:
        context: The [`Context`][pythonnative.Context] to read from.

    Returns:
        The current value for ``context``.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    ctx = _require_hook_state("use_context")
    ctx.record_hook("use_context")
    value = context.current()
    ctx.context_deps[id(context)] = value
    return value


# ======================================================================
# System back button
# ======================================================================


def use_back_handler(handler: Callable[[], bool]) -> None:
    """Intercept the system back action for this screen.

    On Android this handles the hardware back button and predictive
    back gesture; in the desktop preview it handles the Escape key.
    iOS has no system back button, so the handler never fires there
    (swipe-back is controlled by the navigation stack instead).

    Handlers registered later run first, so a component mounted on top
    of existing content (a modal, a confirmation sheet) takes priority
    over handlers that were already mounted. Return ``True`` to consume
    the event and stop both remaining handlers and the platform's
    default behavior (popping the screen); return ``False`` to pass it
    along.

    The latest ``handler`` closure from the most recent render is
    always the one invoked; registration order is fixed at mount, so
    re-renders never change priority.

    Args:
        handler: Zero-arg callable returning ``True`` if it consumed
            the back action.

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        @pn.component
        def Editor():
            dirty, set_dirty = pn.use_state(False)
            pn.use_back_handler(lambda: dirty)  # block back while dirty
            ...
        ```
    """
    ctx = _require_hook_state("use_back_handler")

    latest: Ref[Callable[[], bool]] = use_ref(handler)
    latest.current = handler

    def _register() -> Optional[Callable[[], None]]:
        owner = ctx.owner
        if owner is None:
            return None

        def _trampoline() -> bool:
            fn = latest.current
            if fn is None:
                return False
            try:
                return bool(fn())
            except Exception as exc:
                if not diagnostics.report_error(exc, phase="back handler"):
                    raise
                return True

        return owner.register_back_handler(_trampoline)

    use_effect(_register, [])


__all__ = [
    "Context",
    "HookState",
    "MutationCall",
    "MutationState",
    "QueryResult",
    "Ref",
    "RenderOwner",
    "create_context",
    "current_hook_state",
    "install_hook_state",
    "restore_hook_state",
    "use_back_handler",
    "use_callback",
    "use_color_scheme",
    "use_context",
    "use_deferred_value",
    "use_effect",
    "use_imperative_handle",
    "use_keyboard_height",
    "use_layout_effect",
    "use_memo",
    "use_mutation",
    "use_query",
    "use_reducer",
    "use_ref",
    "use_resource",
    "use_safe_area_insets",
    "use_state",
    "use_subscription",
    "use_transition",
    "use_window_dimensions",
]
