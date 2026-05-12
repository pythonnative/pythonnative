"""Hook primitives for function components.

Provides React-like hooks for managing state, effects, memoization,
context, and navigation within function components decorated with
[`component`][pythonnative.component]. Hooks must be called at the top
level of a component (not inside conditionals or loops) so they map to
the same slot across renders.

Effects are queued during the render phase and flushed *after* the
reconciler commits native-view mutations. This ordering guarantees that
effect callbacks can safely measure layout or interact with the
committed native tree.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Counter(initial=0):
        count, set_count = pn.use_state(initial)
        return pn.Column(
            pn.Text(f"Count: {count}"),
            pn.Button("+", on_click=lambda: set_count(count + 1)),
        )
    ```
"""

import inspect
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, TypeVar

from .element import Element

T = TypeVar("T")

_SENTINEL = object()

_hook_context: threading.local = threading.local()

_batch_context: threading.local = threading.local()

# ======================================================================
# Hook state container
# ======================================================================


class HookState:
    """Per-instance storage for one component's hooks.

    Each `@component` instance owns one `HookState`. Hooks are matched
    to slots by call order, so they must always be called in the same
    order across renders. Effects scheduled during render are deferred
    into `_pending_effects` and flushed after the reconciler commits
    native mutations, which guarantees effect callbacks can safely
    interact with the committed native tree.

    Attributes:
        states: One entry per `use_state` / `use_reducer` call.
        effects: One `(deps, cleanup)` tuple per `use_effect` call.
        memos: One `(deps, value)` tuple per `use_memo` / `use_callback`.
        refs: One mutable dict per `use_ref` call.
        hook_index: Cursor reset to 0 at the start of every render.
    """

    __slots__ = (
        "states",
        "effects",
        "memos",
        "refs",
        "hook_index",
        "state_index",
        "effect_index",
        "memo_index",
        "ref_index",
        "_trigger_render",
        "_pending_effects",
    )

    def __init__(self) -> None:
        self.states: List[Any] = []
        self.effects: List[Tuple[Any, Any]] = []
        self.memos: List[Tuple[Any, Any]] = []
        self.refs: List[dict] = []
        # ``hook_index`` is retained for backwards compatibility with
        # any external code that still reads it; the per-hook cursors
        # below are what each hook function actually uses so that
        # ``use_state`` and ``use_effect`` can coexist in the same
        # component without colliding on a shared counter.
        self.hook_index: int = 0
        self.state_index: int = 0
        self.effect_index: int = 0
        self.memo_index: int = 0
        self.ref_index: int = 0
        self._trigger_render: Optional[Callable[[], None]] = None
        self._pending_effects: List[Tuple[int, Callable, Any]] = []

    def reset_index(self) -> None:
        """Reset every per-hook cursor to ``0``.

        Called by the reconciler at the start of every render pass so
        the next render reads slots in the same order they were
        written.
        """
        self.hook_index = 0
        self.state_index = 0
        self.effect_index = 0
        self.memo_index = 0
        self.ref_index = 0

    def flush_pending_effects(self) -> None:
        """Run effects queued during render, after native commit.

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

        Called when the component instance is unmounted by the
        reconciler.
        """
        for i, (deps, cleanup) in enumerate(self.effects):
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    pass
            self.effects[i] = (_SENTINEL, None)
        self._pending_effects = []


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
                on_click=lambda: set_count(count + 1),
            )
        ```
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_state must be called inside a @component function")

    idx = ctx.state_index
    ctx.state_index += 1
    ctx.hook_index += 1

    if idx >= len(ctx.states):
        val = initial() if callable(initial) else initial
        ctx.states.append(val)

    current = ctx.states[idx]

    def setter(new_value: Any) -> None:
        if callable(new_value):
            new_value = new_value(ctx.states[idx])
        if ctx.states[idx] is not new_value and ctx.states[idx] != new_value:
            ctx.states[idx] = new_value
            if ctx._trigger_render:
                _schedule_trigger(ctx._trigger_render)

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
                pn.Button("+", on_click=lambda: dispatch("increment")),
                pn.Button("Reset", on_click=lambda: dispatch("reset")),
            )
        ```
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_reducer must be called inside a @component function")

    idx = ctx.state_index
    ctx.state_index += 1
    ctx.hook_index += 1

    if idx >= len(ctx.states):
        val = initial_state() if callable(initial_state) else initial_state
        ctx.states.append(val)

    current = ctx.states[idx]

    def dispatch(action: Any) -> None:
        new_state = reducer(ctx.states[idx], action)
        if ctx.states[idx] is not new_state and ctx.states[idx] != new_state:
            ctx.states[idx] = new_state
            if ctx._trigger_render:
                _schedule_trigger(ctx._trigger_render)

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

    idx = ctx.effect_index
    ctx.effect_index += 1
    ctx.hook_index += 1

    if idx >= len(ctx.effects):
        ctx.effects.append((_SENTINEL, None))
        ctx._pending_effects.append((idx, effect, deps))
        return

    prev_deps, _prev_cleanup = ctx.effects[idx]
    if _deps_changed(prev_deps, deps):
        ctx._pending_effects.append((idx, effect, deps))


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

    idx = ctx.memo_index
    ctx.memo_index += 1
    ctx.hook_index += 1

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


def use_ref(initial: Any = None) -> dict:
    """Return a mutable ref dict ``{"current": initial}`` that persists across renders.

    Refs are useful for storing values that must survive renders without
    triggering them: timers, last-seen values, native handles, and so on.

    The ``current`` key is also populated by the reconciler with the
    underlying native view (`UIView` on iOS, `android.view.View` on
    Android) when the ref is passed via the ``ref=`` prop on a built-in
    element. This is how ``Animated.View`` obtains a handle to the
    native view it animates without going through the reconciler.

    Args:
        initial: Value placed at `ref["current"]` on first render.

    Returns:
        A dict with a single `"current"` key. Mutations to the dict do
        *not* trigger re-renders.

    Raises:
        RuntimeError: If called outside a `@component` function.
    """
    ctx = _get_hook_state()
    if ctx is None:
        raise RuntimeError("use_ref must be called inside a @component function")

    idx = ctx.ref_index
    ctx.ref_index += 1
    ctx.hook_index += 1

    if idx >= len(ctx.refs):
        ref: dict = {"current": initial}
        ctx.refs.append(ref)
        return ref

    return ctx.refs[idx]


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


# ======================================================================
# Context
# ======================================================================


class Context:
    """Container for a value shared across a subtree.

    Created by [`create_context`][pythonnative.create_context]; consumed
    via [`use_context`][pythonnative.use_context]. Use
    [`Provider`][pythonnative.Provider] to set the value for a subtree.

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
    return context._current()


# ======================================================================
# Provider element helper
# ======================================================================


def Provider(context: Context, value: Any, child: Element) -> Element:
    """Provide `value` for `context` to all descendants of `child`.

    Args:
        context: The `Context` to set.
        value: Value made available to descendants via
            [`use_context`][pythonnative.use_context].
        child: Subtree under which the provider applies.

    Returns:
        An [`Element`][pythonnative.Element] that the reconciler treats
        as a context boundary.

    Example:
        ```python
        import pythonnative as pn

        ThemeContext = pn.create_context({"primary": "#007AFF"})

        @pn.component
        def App():
            return pn.Provider(ThemeContext, {"primary": "#FF0000"}, MyView())
        ```
    """
    return Element("__Provider__", {"__context__": context, "__value__": value}, [child])


# ======================================================================
# Navigation
# ======================================================================

_NavigationContext: Context = create_context(None)


class NavigationHandle:
    """Handle returned by [`use_navigation`][pythonnative.use_navigation].

    Wraps the host's push/pop primitives so screens can navigate
    without knowing the underlying native navigation stack. The
    typical user-facing surface is the declarative handle returned by
    a [`Stack`][pythonnative.create_stack_navigator] — this class is
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
                on_click=lambda: nav.navigate("Detail", {"id": 42}),
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
