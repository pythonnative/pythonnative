"""Hook primitives for function components.

Provides React-like hooks for managing state, effects, memoization,
context, and navigation within function components decorated with
[`component`][pythonnative.component]. Hooks must be called at the top
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
  run after the layout effects, at the end of the same commit.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Counter(initial=0):
        count, set_count = pn.use_state(initial)
        return pn.Column(
            pn.Text(f"Count: {count}"),
            pn.Button("+", on_press=lambda: set_count(count + 1)),
        )
    ```
"""

import asyncio
import inspect
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Any, Awaitable, Callable, Dict, Generator, Generic, List, Optional, Tuple, TypeVar

from . import diagnostics
from .element import Element

T = TypeVar("T")

_SENTINEL = object()

_hook_context: threading.local = threading.local()

_batch_context: threading.local = threading.local()


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

    Each `@component` instance owns one `HookState`. Hooks are matched
    to slots by call order, so they must always be called in the same
    order across renders. Effects scheduled during render are deferred
    (layout effects into ``_pending_layout_effects``, passive effects
    into ``_pending_effects``) and flushed by the reconciler in two
    phases after native mutations commit.

    Attributes:
        states: One entry per `use_state` / `use_reducer` call.
        effects: One `(deps, cleanup)` tuple per `use_effect` call.
        layout_effects: One `(deps, cleanup)` tuple per
            `use_layout_effect` call.
        memos: One `(deps, value)` tuple per `use_memo` / `use_callback`.
        refs: One [`Ref`][pythonnative.Ref] per `use_ref` call.
    """

    __slots__ = (
        "states",
        "effects",
        "layout_effects",
        "memos",
        "refs",
        "state_index",
        "effect_index",
        "layout_effect_index",
        "memo_index",
        "ref_index",
        "context_deps",
        "_trigger_render",
        "_pending_effects",
        "_pending_layout_effects",
        "_dirty",
        "_vnode",
        "_reconciler",
        "_hook_log",
        "_hook_signature",
        "_component_name",
    )

    def __init__(self) -> None:
        self.states: List[Any] = []
        self.effects: List[Tuple[Any, Any]] = []
        self.layout_effects: List[Tuple[Any, Any]] = []
        self.memos: List[Tuple[Any, Any]] = []
        self.refs: List[Ref] = []
        self.state_index: int = 0
        self.effect_index: int = 0
        self.layout_effect_index: int = 0
        self.memo_index: int = 0
        self.ref_index: int = 0
        # Contexts read during the last completed render, keyed by
        # ``id(context)``. The reconciler consults this when a
        # Provider's value changes so consumers re-render even when a
        # memoized ancestor skipped (reactive context).
        self.context_deps: Dict[int, Any] = {}
        self._trigger_render: Optional[Callable[[], None]] = None
        self._pending_effects: List[Tuple[int, Callable, Any]] = []
        self._pending_layout_effects: List[Tuple[int, Callable, Any]] = []
        # Cleared by the reconciler after each successful render.
        # ``use_state`` / ``use_reducer`` setters flip it to ``True``
        # whenever they actually mutate state, so [`memo`][pythonnative.memo]
        # knows that a memoized component still needs to re-render even
        # when its props didn't change.
        self._dirty: bool = False
        # Back-references wired by the reconciler so a state setter can
        # mark *its own* component subtree dirty for a local re-render
        # (instead of forcing a whole-app re-render from the root). Both
        # stay ``None`` until the component is mounted, and are cleared
        # again when it unmounts.
        self._vnode: Any = None
        self._reconciler: Any = None
        # Dev-mode hook-order guard: the sequence of hook kinds called
        # during the in-flight render, and the signature captured from
        # the first successful render.
        self._hook_log: Optional[List[str]] = None
        self._hook_signature: Optional[List[str]] = None
        self._component_name: str = ""

    def begin_render(self, component_name: str = "") -> None:
        """Prepare for a render pass: reset cursors and the dev-mode hook log.

        Called by the reconciler before each invocation of the
        component body so the next render reads slots in the same
        order they were written.
        """
        self.state_index = 0
        self.effect_index = 0
        self.layout_effect_index = 0
        self.memo_index = 0
        self.ref_index = 0
        self.context_deps = {}
        if component_name:
            self._component_name = component_name
        self._hook_log = [] if diagnostics.is_dev() else None

    def finish_render(self) -> None:
        """Finalize a successful render: lock in / verify the hook signature.

        Only called when the component body returned without raising,
        so a failed render never corrupts the signature.

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
        """Forget the recorded hook signature (used by Fast Refresh).

        After a hot reload swaps in a new component body, the old
        signature no longer applies; the next render records a fresh
        one.
        """
        self._hook_signature = None

    def flush_layout_effects(self) -> None:
        """Run layout effects queued during render (commit phase, pre-paint)."""
        pending = self._pending_layout_effects
        self._pending_layout_effects = []
        for idx, effect_fn, deps in pending:
            _, prev_cleanup = self.layout_effects[idx]
            if callable(prev_cleanup):
                try:
                    prev_cleanup()
                except Exception:
                    pass
            cleanup = effect_fn()
            self.layout_effects[idx] = (list(deps) if deps is not None else None, cleanup)

    def flush_pending_effects(self) -> None:
        """Run passive effects queued during render, after native commit.

        For each pending effect, the previous cleanup is invoked first
        (if any), then the new effect callback. The new return value
        becomes the next cleanup.
        """
        pending = self._pending_effects
        self._pending_effects = []
        for idx, effect_fn, deps in pending:
            _, prev_cleanup = self.effects[idx]
            if callable(prev_cleanup):
                try:
                    prev_cleanup()
                except Exception:
                    pass
            cleanup = effect_fn()
            self.effects[idx] = (list(deps) if deps is not None else None, cleanup)

    def cleanup_all_effects(self) -> None:
        """Run every outstanding cleanup function, then clear state.

        Layout-effect cleanups run before passive-effect cleanups,
        matching the mount order in reverse. Called when the component
        instance is unmounted by the reconciler.
        """
        for i, (_deps, cleanup) in enumerate(self.layout_effects):
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    pass
            self.layout_effects[i] = (_SENTINEL, None)
        for i, (_deps, cleanup) in enumerate(self.effects):
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    pass
            self.effects[i] = (_SENTINEL, None)
        self._pending_effects = []
        self._pending_layout_effects = []


# ======================================================================
# Thread-local context helpers
# ======================================================================


def _get_hook_state() -> Optional[HookState]:
    """Return the active `HookState`, or `None` if no render is in flight."""
    return getattr(_hook_context, "current", None)


def _set_hook_state(state: Optional[HookState]) -> None:
    """Install `state` as the active `HookState` for the current thread."""
    _hook_context.current = state


def _deps_changed(prev: Any, current: Any) -> bool:
    """Return whether the dependency arrays differ enough to re-run an effect."""
    if prev is _SENTINEL:
        return True
    if prev is None or current is None:
        return True
    if len(prev) != len(current):
        return True
    return any(p is not c and p != c for p, c in zip(prev, current))


# ======================================================================
# Batching helpers
# ======================================================================


def _schedule_trigger(trigger: Callable[[], None]) -> None:
    """Run ``trigger`` immediately, or defer it inside a `batch_updates` block."""
    if getattr(_batch_context, "depth", 0) > 0:
        _batch_context.pending_trigger = trigger
    else:
        trigger()


def _notify_state_changed(ctx: "HookState") -> None:
    """Mark ``ctx``'s component dirty and schedule a render after a state change.

    Enqueuing the owning ``VNode`` in the reconciler's dirty set is what
    makes the subsequent render *local*: the screen host's trigger calls
    ``flush_dirty``, which re-renders only the components marked here
    rather than the whole app. The dirty mark is eager (so several
    setters coalesce), while the render trigger respects
    [`batch_updates`][pythonnative.batch_updates].
    """
    ctx._dirty = True
    reconciler = ctx._reconciler
    vnode = ctx._vnode
    if reconciler is not None and vnode is not None:
        reconciler.mark_dirty(vnode)
    if ctx._trigger_render:
        _schedule_trigger(ctx._trigger_render)


@contextmanager
def batch_updates() -> Generator[None, None, None]:
    """Coalesce multiple state updates into a single re-render.

    State setters called inside the `with` block defer their
    re-render trigger until the block exits, so any number of
    `set_*` calls produce at most one render pass.

    Yields:
        None. The block executes normally; deferred renders fire on
        exit.

    Example:
        ```python
        import pythonnative as pn

        with pn.batch_updates():
            set_count(1)
            set_name("hello")
        ```
    """
    depth = getattr(_batch_context, "depth", 0)
    _batch_context.depth = depth + 1
    if depth == 0:
        _batch_context.pending_trigger = None
    try:
        yield
    finally:
        _batch_context.depth -= 1
        if _batch_context.depth == 0:
            trigger = _batch_context.pending_trigger
            _batch_context.pending_trigger = None
            if trigger is not None:
                trigger()


# ======================================================================
# Public hooks
# ======================================================================


def use_state(initial: Any = None) -> Tuple[Any, Callable]:
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
        RuntimeError: If called outside a `@component` function.

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
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_state must be called inside a @component function")
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


def use_reducer(reducer: Callable[[Any, Any], Any], initial_state: Any) -> Tuple[Any, Callable]:
    """Return ``(state, dispatch)`` for reducer-based state management.

    A reducer is a pure function that takes the current state and an
    action and returns the next state. Use it instead of
    [`use_state`][pythonnative.use_state] when state transitions are
    complex enough that centralizing them in one function aids
    readability and testing.

    Args:
        reducer: ``reducer(current_state, action) -> new_state``.
            The component re-renders only when `reducer` returns a
            value different from the current state.
        initial_state: Initial state value, or a callable invoked once
            on the first render.

    Returns:
        A 2-tuple ``(state, dispatch)`` where `dispatch` runs the
        reducer with the supplied action.

    Raises:
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        def reducer(state, action):
            if action == "increment":
                return state + 1
            if action == "reset":
                return 0
            return state

        @pn.component
        def Counter():
            count, dispatch = pn.use_reducer(reducer, 0)
            return pn.Row(
                pn.Button("+", on_press=lambda: dispatch("increment")),
                pn.Button("Reset", on_press=lambda: dispatch("reset")),
            )
        ```
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_reducer must be called inside a @component function")
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


def use_effect(effect: Callable, deps: Optional[list] = None) -> None:
    """Schedule a side effect to run after the native commit.

    Effects are queued during the render pass and flushed once the
    reconciler has finished applying all native-view mutations, which
    means effect callbacks can safely measure layout or interact with
    committed native views.

    The `deps` argument controls when the effect re-runs:

    - `None`: every render.
    - `[]`: mount only.
    - `[a, b]`: when `a` or `b` change (compared by identity, then `==`).

    `effect` may return a cleanup callable; the previous cleanup runs
    before the next effect (and on unmount).

    Args:
        effect: A zero-arg callable invoked after commit. Optionally
            returns a cleanup callable.
        deps: Dependency list, or `None` to run on every render.

    Raises:
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Timer():
            seconds, set_seconds = pn.use_state(0)

            def tick():
                import threading
                t = threading.Timer(1.0, lambda: set_seconds(seconds + 1))
                t.start()
                return t.cancel

            pn.use_effect(tick, [seconds])
            return pn.Text(f"Elapsed: {seconds}s")
        ```
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_effect must be called inside a @component function")
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


def use_layout_effect(effect: Callable, deps: Optional[list] = None) -> None:
    """Schedule a side effect that runs synchronously inside the commit.

    Like [`use_effect`][pythonnative.use_effect], but the callback
    fires *before* passive effects, immediately after native mutations
    and the layout pass are applied. Use it when you need to measure a
    committed frame (via a [`Ref`][pythonnative.Ref]) or issue an
    imperative view command before the user sees the new frame, for
    example scrolling a list into position on mount.

    Prefer `use_effect` for everything else; layout effects block the
    commit, so heavy work here delays the frame.

    Args:
        effect: A zero-arg callable invoked during commit. Optionally
            returns a cleanup callable.
        deps: Dependency list, or `None` to run on every render.

    Raises:
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def AutoScrollList(items):
            list_ref = pn.use_ref()

            def scroll_to_bottom():
                if list_ref.current is not None:
                    list_ref.current.scroll_to_end(animated=False)

            pn.use_layout_effect(scroll_to_bottom, [len(items)])
            return pn.FlatList(items, render_item=Row, ref=list_ref)
        ```
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_layout_effect must be called inside a @component function")
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


def use_memo(factory: Callable[[], T], deps: list) -> T:
    """Return a memoized value that is recomputed only when `deps` change.

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
        RuntimeError: If called outside a `@component` function.
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_memo must be called inside a @component function")
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


def use_callback(callback: Callable, deps: list) -> Callable:
    """Return a stable reference to ``callback``, refreshed when ``deps`` change.

    Equivalent to `use_memo(lambda: callback, deps)`. Useful when passing
    a function as a prop to a memoized child component, so the child
    doesn't see a fresh function identity on every render.

    Args:
        callback: The callable to memoize.
        deps: Dependency list controlling when the reference refreshes.

    Returns:
        A callable with stable identity across renders (until `deps` change).
    """
    return use_memo(lambda: callback, deps)


def use_ref(initial: Optional[T] = None) -> Ref[T]:
    """Return a [`Ref`][pythonnative.Ref] that persists across renders.

    Refs are useful for storing values that must survive renders without
    triggering them: timers, last-seen values, native handles, and so on.

    ``ref.current`` is also populated by the reconciler with the
    underlying native view (`UIView` on iOS, `android.view.View` on
    Android, a Tk widget on desktop) when the ref is passed via the
    ``ref=`` prop on a built-in element, and cleared to ``None`` when
    that element unmounts. Composite components such as
    [`FlatList`][pythonnative.FlatList] publish a typed controller
    object instead (see
    [`use_imperative_handle`][pythonnative.use_imperative_handle]).

    Args:
        initial: Value placed at ``ref.current`` on first render.

    Returns:
        A [`Ref`][pythonnative.Ref]. Mutations to ``ref.current`` do
        *not* trigger re-renders.

    Raises:
        RuntimeError: If called outside a `@component` function.
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_ref must be called inside a @component function")
    ctx.record_hook("use_ref")

    idx = ctx.ref_index
    ctx.ref_index += 1

    if idx >= len(ctx.refs):
        ref: Ref[T] = Ref(initial)
        ctx.refs.append(ref)
        return ref

    return ctx.refs[idx]


def use_imperative_handle(
    ref: Optional[Ref],
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
            Defaults to ``[]`` semantics only if you pass ``[]``;
            ``None`` rebuilds on every render, matching effects.

    Raises:
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def VideoPlayer(source, ref=None):
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


def use_async_effect(
    effect: Callable[[], Awaitable[None]],
    deps: Optional[list] = None,
) -> None:
    """Schedule an async effect that's cancelled on re-run / unmount.

    Like [`use_effect`][pythonnative.use_effect] but takes an
    ``async def`` (or any zero-arg callable returning an awaitable).
    The coroutine is scheduled on the framework runtime via
    [`run_async`][pythonnative.runtime.run_async] after the native
    commit. When ``deps`` change (or the component unmounts), the
    in-flight future is cancelled.

    Args:
        effect: A zero-arg callable returning an awaitable. Typically
            an ``async def`` defined inside the component.
        deps: Dependency list, or ``None`` to re-run on every render.

    Raises:
        RuntimeError: If called outside a ``@component`` function.

    Example:
        ```python
        import pythonnative as pn


        @pn.component
        def Posts(user_id):
            posts, set_posts = pn.use_state([])

            async def load():
                set_posts(await api.get_posts(user_id))

            pn.use_async_effect(load, [user_id])
            return pn.FlatList(posts, render_item=...)
        ```
    """
    from .runtime import run_async

    def _sync_effect() -> Callable[[], None]:
        future = run_async(effect())

        def _observe(fut: Any) -> None:
            # Surface unhandled async-effect crashes instead of letting
            # the future's exception vanish unobserved: RedBox in dev
            # mode, traceback in production.
            if fut.cancelled():
                return
            exc = fut.exception()
            if exc is None or isinstance(exc, asyncio.CancelledError):
                return
            if not diagnostics.report_error(exc, phase="async effect"):
                import traceback

                traceback.print_exception(type(exc), exc, exc.__traceback__)

        future.add_done_callback(_observe)

        def _cancel() -> None:
            future.cancel()

        return _cancel

    use_effect(_sync_effect, deps)


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
        import pythonnative as pn


        @pn.component
        def UserCard(user_id):
            q = pn.use_query(lambda: api.get_user(user_id), [user_id])
            if q.loading:
                return pn.Text("Loading…")
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
                set_state(lambda s, e=exc: replace(s, loading=False, error=e))

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

    def __init__(self, future: "Any") -> None:
        self._future = future

    def __await__(self) -> Any:
        return asyncio.wrap_future(self._future).__await__()

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
        import pythonnative as pn


        @pn.component
        def NewPostForm():
            state, save = pn.use_mutation(api.create_post)

            return pn.Column(
                pn.Button("Save", on_press=lambda: save(post)),
                pn.Text("Saving…") if state.loading else pn.Text(""),
                pn.Text(str(state.error)) if state.error else pn.Text(""),
            )
        ```
    """
    from .runtime import run_async

    state, set_state = use_state(lambda: MutationState[T]())

    def mutate(*args: Any, **kwargs: Any) -> MutationCall[T]:
        set_state(lambda s: replace(s, loading=True, error=None))

        async def _runner() -> T:
            try:
                data = await mutator(*args, **kwargs)
                set_state(lambda s: replace(s, data=data, loading=False, error=None))
                return data
            except asyncio.CancelledError:
                set_state(lambda s: replace(s, loading=False))
                raise
            except BaseException as exc:
                set_state(lambda s, e=exc: replace(s, loading=False, error=e))
                raise

        future = run_async(_runner())
        return MutationCall[T](future)

    return state, mutate


# ======================================================================
# Platform-metric hooks (window dimensions, safe-area insets, keyboard)
# ======================================================================


def use_window_dimensions() -> Dict[str, float]:
    """Return the current viewport size and re-render when it changes.

    Equivalent to React Native's ``useWindowDimensions``. The values
    are pushed by the screen host whenever the platform reports a new
    size (initial layout, rotation, multitasking split-view).

    Returns:
        A dict with ``"width"`` and ``"height"`` floats in layout
        units (pt on iOS, dp on Android). Both are ``0.0`` until the
        screen host has run its first layout pass.

    Raises:
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def MyView():
            dims = pn.use_window_dimensions()
            return pn.Text(f"{dims['width']:.0f} x {dims['height']:.0f}")
        ```
    """
    from . import platform_metrics

    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_window_dimensions must be called inside a @component function")

    _, set_tick = use_state(0)

    def subscribe() -> Callable[[], None]:
        return platform_metrics.subscribe(lambda: set_tick(lambda n: n + 1))

    use_effect(subscribe, [])

    dims = platform_metrics.get_window_dimensions()
    return {"width": dims.width, "height": dims.height}


def use_safe_area_insets() -> Dict[str, float]:
    """Return the current safe-area insets and re-render on change.

    Mirrors ``react-native-safe-area-context``'s ``useSafeAreaInsets``.

    Returns:
        A dict with ``"top"``, ``"bottom"``, ``"left"``, and ``"right"``
        floats in layout units (pt on iOS, dp on Android).

    Raises:
        RuntimeError: If called outside a `@component` function.
    """
    from . import platform_metrics

    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_safe_area_insets must be called inside a @component function")

    _, set_tick = use_state(0)

    def subscribe() -> Callable[[], None]:
        return platform_metrics.subscribe(lambda: set_tick(lambda n: n + 1))

    use_effect(subscribe, [])

    insets = platform_metrics.get_safe_area_insets()
    return {
        "top": insets.top,
        "bottom": insets.bottom,
        "left": insets.left,
        "right": insets.right,
    }


def use_keyboard_height() -> float:
    """Return the on-screen keyboard height (or 0) and re-render on change.

    Useful for custom layout that needs to react to keyboard
    show/hide events. Most apps should use
    [`KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView] instead
    of reading this directly.

    Raises:
        RuntimeError: If called outside a `@component` function.
    """
    from . import platform_metrics

    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_keyboard_height must be called inside a @component function")

    _, set_tick = use_state(0)

    def subscribe() -> Callable[[], None]:
        return platform_metrics.subscribe(lambda: set_tick(lambda n: n + 1))

    use_effect(subscribe, [])

    return platform_metrics.get_keyboard_height()


def use_color_scheme() -> str:
    """Return the effective color scheme and re-render when it changes.

    Equivalent to React Native's ``useColorScheme``. The system value
    is published by the screen host; an app-level override set through
    [`appearance.set_color_scheme`][pythonnative.appearance.set_color_scheme]
    takes precedence.

    Returns:
        ``"light"`` or ``"dark"``.

    Raises:
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Banner():
            scheme = pn.use_color_scheme()
            bg = "#000000" if scheme == "dark" else "#FFFFFF"
            return pn.View(style=pn.style(background_color=bg))
        ```
    """
    from . import appearance

    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_color_scheme must be called inside a @component function")

    _, set_tick = use_state(0)

    def subscribe() -> Callable[[], None]:
        return appearance.subscribe(lambda: set_tick(lambda n: n + 1))

    use_effect(subscribe, [])

    return appearance.get_color_scheme()


# ======================================================================
# Context
# ======================================================================


class Context:
    """Container for a value shared across a subtree.

    Created by [`create_context`][pythonnative.create_context]; consumed
    via [`use_context`][pythonnative.use_context]. Use
    [`Provider`][pythonnative.Provider] to set the value for a subtree.

    Context is *reactive*: when a Provider's value changes, every
    component that read the context on its last render re-renders,
    even if a memoized ancestor skipped its own re-render.

    Attributes:
        default: The value returned when no `Provider` ancestor exists.
    """

    def __init__(self, default: Any = None) -> None:
        self.default = default
        self._stack: List[Any] = []

    def _current(self) -> Any:
        return self._stack[-1] if self._stack else self.default


def create_context(default: Any = None) -> Context:
    """Create a new context with an optional default value.

    Args:
        default: Returned by [`use_context`][pythonnative.use_context]
            when there is no enclosing
            [`Provider`][pythonnative.Provider].

    Returns:
        A fresh `Context` instance.

    Example:
        ```python
        import pythonnative as pn

        ThemeContext = pn.create_context({"primary": "#007AFF"})
        ```
    """
    return Context(default)


def use_context(context: Context) -> Any:
    """Read the current value of `context` from the nearest `Provider`.

    If no enclosing `Provider` exists, returns the context's default.
    The component is registered as a subscriber: when the nearest
    Provider's value changes, the component re-renders even if a
    memoized ancestor skipped.

    Args:
        context: The `Context` to read from.

    Returns:
        The current value for `context`.

    Raises:
        RuntimeError: If called outside a `@component` function.
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_context must be called inside a @component function")
    ctx.record_hook("use_context")
    value = context._current()
    ctx.context_deps[id(context)] = value
    return value


# ======================================================================
# Provider element helper
# ======================================================================


def Provider(context: "Context", value: Any, *children: Element) -> Element:
    """Provide ``value`` for ``context`` to all descendants of ``children``.

    Accepts any number of children (varargs). A Provider contributes no
    native view of its own; its children mount directly into the
    surrounding native parent.

    When ``value`` differs from the previous render (identity, then
    ``==``), every descendant that read the context via
    [`use_context`][pythonnative.use_context] re-renders, including
    descendants of memoized components that skipped.

    Args:
        context: The [`Context`][pythonnative.hooks.Context] to set.
        value: Value made available to descendants via
            [`use_context`][pythonnative.use_context].
        *children: Subtree(s) under which the provider applies.

    Returns:
        An [`Element`][pythonnative.Element] that the reconciler treats
        as a context boundary.

    Example:
        ```python
        import pythonnative as pn

        ThemeContext = pn.create_context({"primary": "#007AFF"})

        @pn.component
        def App():
            return pn.Provider(
                ThemeContext,
                {"primary": "#FF0000"},
                Header(),
                Body(),
            )
        ```
    """
    return Element("__Provider__", {"__context__": context, "__value__": value}, list(children))


def memo(component_fn: Callable[..., Element]) -> Callable[..., Element]:
    """Skip a function component's render when its props haven't changed.

    Decorate a ``@component``-wrapped function to opt into shallow-prop
    memoization. When the reconciler re-renders the parent tree, a
    memoized child is skipped (its previously-rendered subtree is
    reused) iff:

    - Its props are shallowly equal to the previous render's props
      (callables compared by identity, scalars by ``==``).
    - None of its internal ``use_state`` / ``use_reducer`` setters fired
      since the last render.

    Pair with [`use_callback`][pythonnative.use_callback] when passing
    callbacks as props, otherwise a fresh closure will defeat the memo.

    Args:
        component_fn: A function previously decorated with
            [`component`][pythonnative.component].

    Returns:
        The same function, marked for memoization.

    Example:
        ```python
        import pythonnative as pn

        @pn.memo
        @pn.component
        def ExpensiveRow(label: str):
            ...
        ```
    """
    component_fn._pn_memo = True
    # ``@component`` builds a wrapper that emits an ``Element`` whose
    # ``type`` is the underlying function, so propagate the marker to
    # ``__wrapped__`` so the reconciler can find it via ``Element.type``.
    wrapped = getattr(component_fn, "__wrapped__", None)
    if wrapped is not None:
        wrapped._pn_memo = True
    return component_fn


# ======================================================================
# Navigation
# ======================================================================

_NavigationContext: Context = create_context(None)


class NavigationHandle:
    """Handle returned by [`use_navigation`][pythonnative.use_navigation].

    Wraps the host's push/pop primitives so screens can navigate
    without knowing the underlying native navigation stack. The
    typical user-facing surface is the declarative handle returned by
    a [`Stack`][pythonnative.create_stack_navigator]; this class is
    the lower-level fallback used when no navigator is rendered (and
    as the bridge that declarative navigators delegate to when they
    need to push real native screens).

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def HomeScreen():
            nav = pn.use_navigation()
            return pn.Button(
                "Open Detail",
                on_press=lambda: nav.navigate("Detail", {"id": 42}),
            )
        ```
    """

    def __init__(self, host: Any) -> None:
        self._host = host

    def navigate(self, component: Any, params: Optional[Dict[str, Any]] = None) -> None:
        """Push ``component`` onto the navigation stack.

        Args:
            component: A ``@component`` function or a dotted Python
                path (e.g. ``"app.detail.DetailScreen"``). When a
                Stack navigator is the root of the app, prefer the
                declarative ``nav.navigate("Detail", params)`` form
                returned by ``use_navigation()`` (it pushes by route
                name and the host re-uses its own ``App`` component).
            params: Optional dict of arguments serialized into the
                target screen.
        """
        self._host._push(component, params)

    def go_back(self) -> None:
        """Pop the current screen and return to the previous one."""
        self._host._pop()

    def get_params(self) -> Dict[str, Any]:
        """Return the params dict passed to this screen.

        Returns:
            The dict supplied by the caller's
            [`navigate`][pythonnative.hooks.NavigationHandle.navigate]
            call, or an empty dict if none was supplied.
        """
        return self._host._get_nav_args()


def use_navigation() -> NavigationHandle:
    """Return a [`NavigationHandle`][pythonnative.hooks.NavigationHandle] for the screen.

    Returns:
        The handle bound to the current screen's host.

    Raises:
        RuntimeError: If called outside a component rendered via
            [`create_screen`][pythonnative.create_screen].
    """
    handle = use_context(_NavigationContext)
    if handle is None:
        raise RuntimeError(
            "use_navigation() called outside a PythonNative screen. "
            "Ensure your component is rendered via create_screen()."
        )
    return handle


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
        RuntimeError: If called outside a `@component` function.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Editor():
            dirty, set_dirty = pn.use_state(False)
            pn.use_back_handler(lambda: dirty)  # block back while dirty
            ...
        ```
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_back_handler must be called inside a @component function")

    latest: Ref[Callable[[], bool]] = use_ref(handler)
    latest.current = handler

    def _register() -> Optional[Callable[[], None]]:
        reconciler = ctx._reconciler
        if reconciler is None or not hasattr(reconciler, "register_back_handler"):
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

        return reconciler.register_back_handler(_trampoline)

    use_effect(_register, [])


# ======================================================================
# @component decorator
# ======================================================================


def component(func: Callable) -> Callable[..., Element]:
    """Mark a function as a PythonNative component.

    The decorated function may use hooks (`use_state`, `use_effect`,
    etc.) and returns an [`Element`][pythonnative.Element] tree.
    Each call site creates an independent component instance with its
    own hook state.

    Positional arguments are mapped onto the function's positional
    parameters. If the function declares `*args`, positional arguments
    instead become the special `children` prop.

    Args:
        func: The function to wrap.

    Returns:
        A wrapper that, when called, returns an `Element` whose `type`
        is `func` itself.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Greeting(name: str = "World"):
            return pn.Text(f"Hello, {name}!")
        ```
    """
    sig = inspect.signature(func)
    positional_params = [
        name
        for name, p in sig.parameters.items()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_var_positional = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values())

    def wrapper(*args: Any, **kwargs: Any) -> Element:
        props: dict = dict(kwargs)

        if args:
            if has_var_positional:
                props["children"] = list(args)
            else:
                for i, arg in enumerate(args):
                    if i < len(positional_params):
                        props[positional_params[i]] = arg

        key = props.pop("key", None)
        return Element(func, props, [], key=key)

    wrapper.__wrapped__ = func  # noqa: B010
    wrapper.__name__ = func.__name__
    wrapper.__qualname__ = func.__qualname__
    wrapper._pn_component = True  # noqa: B010
    return wrapper
