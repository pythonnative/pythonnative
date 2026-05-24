"""Animated values + animation drivers + animated component wrappers.

Modeled on React Native's ``Animated`` API but with an
``async``-aware completion contract. The core primitives are:

- [`AnimatedValue`][pythonnative.animated.AnimatedValue]: a numeric
  cell with subscribers; animations mutate it over time.
- ``Animated.timing`` / ``Animated.spring`` / ``Animated.decay``:
  animation factories. The objects they return implement
  ``__await__``, so you can write ``await Animated.timing(v, to=1.0)``
  to suspend until the animation finishes.
- ``Animated.sequence`` / ``Animated.parallel`` / ``Animated.delay``:
  composition; also awaitable.
- ``Animated.View`` / ``Animated.Text`` / ``Animated.Image``:
  components whose ``style`` may contain ``AnimatedValue`` instances.

Driver:

- A single background thread ticks at ~60 Hz, advancing every active
  animation by ``dt``.
- Animations expose two APIs:
  - ``handle.start()`` — fire-and-forget. Returns ``self``.
  - ``await handle`` (or ``await handle.run()``) — wait for the
    animation to complete; cancellation cancels the animation.

Example:
    ```python
    import pythonnative as pn


    @pn.component
    def FadeIn():
        opacity = pn.use_animated_value(0.0)

        async def fade_in():
            await pn.Animated.timing(opacity, to=1.0, duration=400)
            await pn.Animated.timing(opacity, to=0.5, duration=200)

        pn.use_async_effect(fade_in, [])

        return pn.Animated.View(
            pn.Text("Hello!"),
            style={"opacity": opacity, "padding": 20},
        )
    ```
"""

from __future__ import annotations

import asyncio
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .element import Element
from .hooks import use_effect, use_ref
from .runtime import resolve_future
from .style import StyleProp, resolve_style

# Maximum frame rate at which the Python ticker drives animations.
_TARGET_FPS = 60.0
_FRAME_DT = 1.0 / _TARGET_FPS

# Upper bound on how much wall-clock time the animation loop will try to
# catch up on in a single iteration after thread starvation. At 60 fps
# this is ~333 ms of simulated motion; further drift is dropped to keep
# the loop responsive.
_MAX_CATCHUP_FRAMES = 20

_EASINGS: Dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1.0 - (1.0 - t) * (1.0 - t),
    "ease_in_out": lambda t: 3.0 * t * t - 2.0 * t * t * t,
    "ease_in_quad": lambda t: t * t,
    "ease_out_quad": lambda t: 1.0 - (1.0 - t) * (1.0 - t),
    "bounce": lambda t: (
        # Robert Penner's bounce out, common easing.
        7.5625 * t * t
        if t < 1 / 2.75
        else (
            7.5625 * (t - 1.5 / 2.75) * (t - 1.5 / 2.75) + 0.75
            if t < 2 / 2.75
            else (
                7.5625 * (t - 2.25 / 2.75) * (t - 2.25 / 2.75) + 0.9375
                if t < 2.5 / 2.75
                else 7.5625 * (t - 2.625 / 2.75) * (t - 2.625 / 2.75) + 0.984375
            )
        )
    ),
}


def _resolve_easing(name: Any) -> Callable[[float], float]:
    if callable(name):
        return name
    return _EASINGS.get(str(name), _EASINGS["ease_in_out"])


# ======================================================================
# AnimatedValue
# ======================================================================


class AnimatedValue:
    """A subscribable numeric cell driven by animations.

    Direct mutation via
    [`set_value`][pythonnative.animated.AnimatedValue.set_value]
    fires subscribers immediately; animations call ``set_value`` from
    the ticker thread.

    Subscribers are ``(prop_name, callback)`` tuples. Each animated
    component (e.g., ``Animated.View``) subscribes once per
    ``AnimatedValue`` prop in its style during mount.
    """

    __slots__ = ("_value", "_subscribers", "_lock")

    def __init__(self, initial: float = 0.0) -> None:
        self._value = float(initial)
        self._subscribers: List[Tuple[str, Callable[[float], None]]] = []
        self._lock = threading.Lock()

    @property
    def value(self) -> float:
        """Return the current numeric value (without subscribing)."""
        return self._value

    def set_value(self, new_value: float) -> None:
        """Set the value immediately and fire all subscribers."""
        new_value = float(new_value)
        with self._lock:
            self._value = new_value
            subs = list(self._subscribers)
        for prop, cb in subs:
            try:
                cb(new_value)
            except Exception:
                pass

    def add_listener(self, prop: str, callback: Callable[[float], None]) -> Callable[[], None]:
        """Register ``callback`` for changes to this value.

        Returns an unsubscribe callable. ``prop`` is metadata only —
        it lets the subscriber differentiate this binding from others
        on the same ``AnimatedValue``.
        """
        with self._lock:
            self._subscribers.append((prop, callback))

        def _unsubscribe() -> None:
            with self._lock:
                try:
                    self._subscribers.remove((prop, callback))
                except ValueError:
                    pass

        return _unsubscribe

    def __float__(self) -> float:
        return self._value

    def __repr__(self) -> str:
        return f"AnimatedValue({self._value:g})"


# ======================================================================
# Animation driver
# ======================================================================


class _AnimationManager:
    """Single-threaded driver for all currently-running animations.

    Holds a list of ``_RunningAnimation`` instances and ticks them at
    ~60 Hz. The thread starts on first use and idles when nothing is
    active.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._animations: List[_RunningAnimation] = []
        self._thread: Optional[threading.Thread] = None
        self._stopped = False

    def add(self, anim: "_RunningAnimation") -> None:
        with self._lock:
            self._animations.append(anim)
            self._ensure_thread_locked()

    def remove(self, anim: "_RunningAnimation") -> None:
        with self._lock:
            try:
                self._animations.remove(anim)
            except ValueError:
                pass

    def _ensure_thread_locked(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pn-animated")
        self._thread.start()

    def _loop(self) -> None:
        last = time.monotonic()
        # Clamping the per-tick dt is important for numerical stability:
        # an underdamped spring with a 0.3 s step explodes immediately,
        # and on iOS/Android the animation thread can be starved for
        # several frames during render bursts. We integrate physics on a
        # clamped dt (max 2 target frames) and sub-step when wall-clock
        # has advanced more than that, so the perceived motion still
        # tracks real time at most a couple of frames behind. After an
        # extreme starvation (e.g. the app was backgrounded for seconds)
        # we cap the catch-up at ``_MAX_CATCHUP_FRAMES`` worth of
        # physics; any further wall-clock drift is dropped on the floor,
        # which keeps the loop responsive instead of spinning forward
        # through hundreds of substeps.
        max_step = _FRAME_DT * 2.0
        max_catchup = _FRAME_DT * _MAX_CATCHUP_FRAMES
        while not self._stopped:
            now = time.monotonic()
            dt = now - last
            last = now
            with self._lock:
                active = list(self._animations)
            if not active:
                time.sleep(0.05)
                last = time.monotonic()
                continue
            remaining = min(dt, max_catchup)
            while remaining > 0.0:
                step = remaining if remaining <= max_step else max_step
                remaining -= step
                for anim in active:
                    if getattr(anim, "_completed", False):
                        continue
                    try:
                        finished = anim.advance(step)
                    except Exception:
                        finished = True
                    if finished:
                        self.remove(anim)
            time.sleep(_FRAME_DT)


_manager = _AnimationManager()


# ======================================================================
# Animation primitives
# ======================================================================


class _RunningAnimation:
    """Base class for in-flight animations; ``advance()`` returns True when done."""

    def __init__(self, value: AnimatedValue) -> None:
        self.value = value
        self._completion_futures: List[asyncio.Future[None]] = []
        self._completed = False

    def add_completion_future(self, future: asyncio.Future[None]) -> None:
        """Register ``future`` to be resolved when the animation ends."""
        self._completion_futures.append(future)
        if self._completed:
            resolve_future(future, None)

    def advance(self, dt: float) -> bool:
        raise NotImplementedError

    def _finish(self) -> None:
        if self._completed:
            return
        self._completed = True
        for fut in self._completion_futures:
            resolve_future(fut, None)


class _TimingAnimation(_RunningAnimation):
    def __init__(
        self,
        value: AnimatedValue,
        to: float,
        duration: float,
        easing: Callable[[float], float],
    ) -> None:
        super().__init__(value)
        self._from = value.value
        self._to = float(to)
        self._duration = max(0.001, float(duration) / 1000.0)
        self._easing = easing
        self._elapsed = 0.0

    def advance(self, dt: float) -> bool:
        self._elapsed += dt
        progress = min(1.0, self._elapsed / self._duration)
        eased = self._easing(progress)
        new_val = self._from + (self._to - self._from) * eased
        self.value.set_value(new_val)
        if progress >= 1.0:
            self._finish()
            return True
        return False


class _SpringAnimation(_RunningAnimation):
    """Damped harmonic spring driver."""

    def __init__(
        self,
        value: AnimatedValue,
        to: float,
        stiffness: float,
        damping: float,
        mass: float,
    ) -> None:
        super().__init__(value)
        self._to = float(to)
        self._velocity = 0.0
        self._stiffness = float(stiffness)
        self._damping = float(damping)
        self._mass = float(mass)
        self._rest_threshold = 0.001

    def advance(self, dt: float) -> bool:
        x = self.value.value
        a = (-self._stiffness * (x - self._to) - self._damping * self._velocity) / self._mass
        self._velocity += a * dt
        new_x = x + self._velocity * dt
        self.value.set_value(new_x)
        if abs(new_x - self._to) < self._rest_threshold and abs(self._velocity) < self._rest_threshold:
            self.value.set_value(self._to)
            self._finish()
            return True
        return False


class _DecayAnimation(_RunningAnimation):
    def __init__(self, value: AnimatedValue, velocity: float, deceleration: float) -> None:
        super().__init__(value)
        self._velocity = float(velocity)
        self._deceleration = float(deceleration)
        self._rest_threshold = 0.001

    def advance(self, dt: float) -> bool:
        self._velocity *= math.exp(-self._deceleration * dt * 1000.0)
        new_x = self.value.value + self._velocity * dt
        self.value.set_value(new_x)
        if abs(self._velocity) < self._rest_threshold:
            self._finish()
            return True
        return False


class _DelayAnimation(_RunningAnimation):
    def __init__(self, duration_ms: float) -> None:
        super().__init__(AnimatedValue(0.0))
        self._elapsed = 0.0
        self._duration = max(0.001, duration_ms / 1000.0)

    def advance(self, dt: float) -> bool:
        self._elapsed += dt
        if self._elapsed >= self._duration:
            self._finish()
            return True
        return False


# ======================================================================
# Public animation handles
# ======================================================================


class _AwaitableAnimation:
    """Base for awaitable animation handles.

    Subclasses implement :meth:`start` and :meth:`stop`. Awaiting the
    handle (``await handle``) starts the animation if necessary and
    suspends until it completes. Cancelling the awaiting task calls
    :meth:`stop`.

    Calling :meth:`start` returns ``self`` so handles can be chained
    or stashed: ``handle = pn.Animated.timing(...).start()``.
    """

    def start(self) -> "_AwaitableAnimation":
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def run(self) -> "_AwaitableAnimation":
        """Return ``self`` for explicit ``await handle.run()`` style.

        Equivalent to ``await handle`` directly; provided because some
        readers prefer the slightly more explicit form, particularly
        when storing the awaitable before resolving it.
        """
        return self

    async def _drive(self) -> None:
        raise NotImplementedError

    def __await__(self) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError(
                "Animations can only be awaited from inside an asyncio task; "
                "use handle.start() to fire-and-forget instead."
            ) from exc

        async def _runner() -> None:
            try:
                await self._drive()
            except asyncio.CancelledError:
                self.stop()
                raise

        return _runner().__await__()


class _AnimationHandle(_AwaitableAnimation):
    """Public handle returned by ``Animated.timing`` / ``.spring`` / ``.decay``.

    Wraps a ``_RunningAnimation`` factory so each ``.start()`` call
    creates a fresh in-flight animation (matches React Native — the
    ``Animated.timing`` return value is reusable).
    """

    def __init__(self, factory: Callable[[], _RunningAnimation]) -> None:
        self._factory = factory
        self._current: Optional[_RunningAnimation] = None

    def start(self) -> "_AnimationHandle":
        """Begin the animation. Returns ``self`` for chaining."""
        self.stop()
        anim = self._factory()
        self._current = anim
        _manager.add(anim)
        return self

    def stop(self) -> None:
        """Cancel the running instance (no-op if not running)."""
        if self._current is not None:
            self._current._finish()
            _manager.remove(self._current)
            self._current = None

    async def _drive(self) -> None:
        if self._current is None:
            self.start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        assert self._current is not None
        self._current.add_completion_future(future)
        await future


class _CompositeAnimation(_AwaitableAnimation):
    """Run a list of animations in sequence or in parallel."""

    def __init__(self, items: List[Any], mode: str) -> None:
        self._items = list(items)
        self._mode = mode

    def start(self) -> "_CompositeAnimation":
        """Schedule the composite on the framework runtime, fire-and-forget."""
        from .runtime import run_async

        run_async(self._drive())
        return self

    def stop(self) -> None:
        for item in self._items:
            try:
                item.stop()
            except Exception:
                pass

    async def _drive(self) -> None:
        if self._mode == "parallel":
            await asyncio.gather(*(self._await_item(item) for item in self._items))
            return
        for item in self._items:
            await self._await_item(item)

    @staticmethod
    async def _await_item(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, _AwaitableAnimation):
            await item
        else:
            # Plain awaitables and coroutines are supported too — lets
            # users mix in ``asyncio.sleep`` or other awaitables.
            await item


# ======================================================================
# Animated component wrappers
# ======================================================================


def _resolve_style_with_values(style: StyleProp) -> Tuple[Dict[str, Any], Dict[str, AnimatedValue]]:
    """Split ``style`` into a plain dict and animated bindings.

    AnimatedValue entries in the style are replaced with their current
    numeric value in ``plain_style`` and recorded in
    ``animated_bindings`` so the wrapping component can subscribe
    after mount.
    """
    flat = resolve_style(style)
    bindings: Dict[str, AnimatedValue] = {}
    plain: Dict[str, Any] = {}
    for k, v in flat.items():
        if isinstance(v, AnimatedValue):
            bindings[k] = v
            plain[k] = v.value
        else:
            plain[k] = v
    return plain, bindings


def _make_animated_factory(
    element_type: str,
    accept_children: bool,
) -> Callable[..., Element]:
    """Build an animated wrapper for ``element_type``."""
    from .hooks import component  # local import to avoid cycle

    @component
    def _animated(*args: Any, **kwargs: Any) -> Element:
        from .components import Image as _Image
        from .components import Text as _Text
        from .components import View as _View

        style = kwargs.pop("style", None)
        plain_style, bindings = _resolve_style_with_values(style)

        ref = use_ref(None)

        def _subscribe() -> Callable[[], None]:
            view = ref["current"]
            unsubs: List[Callable[[], None]] = []
            if view is None:
                return lambda: None

            for prop, value in bindings.items():

                def _on_change(new_val: float, _prop: str = prop, _view: Any = view) -> None:
                    handler = _get_handler_for(_view)
                    if handler is None:
                        return
                    setter = getattr(handler, "set_animated_property", None)
                    if setter is None:
                        return
                    try:
                        setter(_view, _animated_prop_name(_prop), new_val)
                    except Exception:
                        pass

                unsub = value.add_listener(prop, _on_change)
                unsubs.append(unsub)

            def _cleanup() -> None:
                for fn in unsubs:
                    try:
                        fn()
                    except Exception:
                        pass

            return _cleanup

        # Re-subscribe whenever bindings change identity.
        use_effect(_subscribe, [tuple(sorted((k, id(v)) for k, v in bindings.items()))])

        if element_type == "Text":
            text = args[0] if args else kwargs.pop("text", "")
            return _Text(text, style=plain_style, ref=ref)
        if element_type == "Image":
            source = args[0] if args else kwargs.pop("source", "")
            return _Image(source, style=plain_style, ref=ref)
        children = list(args) if accept_children else []
        return _View(*children, style=plain_style, ref=ref)

    return _animated


def _animated_prop_name(prop: str) -> str:
    """Map a style key to the name expected by ``set_animated_property``."""
    if prop == "opacity":
        return "opacity"
    if prop == "background_color":
        return "background_color"
    if prop in ("translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate"):
        return prop
    return prop


def _get_handler_for(native_view: Any) -> Any:
    """Best-effort lookup of the registered handler for ``native_view``."""
    del native_view
    try:
        from .native_views import get_registry

        registry = get_registry()
        handlers = getattr(registry, "_handlers", {})
        handler = handlers.get("View")
        if handler is not None:
            return handler
        if handlers:
            return next(iter(handlers.values()))
        return None
    except Exception:
        return None


# ======================================================================
# Public API
# ======================================================================


class _AnimatedNamespace:
    """Public ``Animated`` namespace.

    Exposes the ``Value`` type, animation factories, composers, and
    component wrappers (``View``, ``Text``, ``Image``).
    """

    Value = AnimatedValue

    @staticmethod
    def timing(
        value: AnimatedValue,
        *,
        to: float,
        duration: float = 300.0,
        easing: Any = "ease_in_out",
    ) -> _AnimationHandle:
        """Linearly interpolate ``value`` to ``to`` over ``duration`` ms."""

        def _factory() -> _RunningAnimation:
            return _TimingAnimation(value, to, duration, _resolve_easing(easing))

        return _AnimationHandle(_factory)

    @staticmethod
    def spring(
        value: AnimatedValue,
        *,
        to: float,
        stiffness: float = 100.0,
        damping: float = 10.0,
        mass: float = 1.0,
    ) -> _AnimationHandle:
        """Run a damped harmonic spring toward ``to``."""

        def _factory() -> _RunningAnimation:
            return _SpringAnimation(value, to, stiffness, damping, mass)

        return _AnimationHandle(_factory)

    @staticmethod
    def decay(
        value: AnimatedValue,
        *,
        velocity: float,
        deceleration: float = 0.997,
    ) -> _AnimationHandle:
        """Decelerate ``value`` from its current velocity until it rests."""

        def _factory() -> _RunningAnimation:
            return _DecayAnimation(value, velocity, deceleration)

        return _AnimationHandle(_factory)

    @staticmethod
    def parallel(animations: List[Any]) -> _CompositeAnimation:
        """Run all ``animations`` concurrently; complete when all finish."""
        return _CompositeAnimation(animations, "parallel")

    @staticmethod
    def sequence(animations: List[Any]) -> _CompositeAnimation:
        """Run ``animations`` one after another."""
        return _CompositeAnimation(animations, "sequence")

    @staticmethod
    def delay(duration: float) -> _AnimationHandle:
        """Wait ``duration`` ms before continuing in a sequence."""

        def _factory() -> _RunningAnimation:
            return _DelayAnimation(duration)

        return _AnimationHandle(_factory)

    View = staticmethod(_make_animated_factory("View", accept_children=True))
    Text = staticmethod(_make_animated_factory("Text", accept_children=False))
    Image = staticmethod(_make_animated_factory("Image", accept_children=False))


Animated = _AnimatedNamespace()


def use_animated_value(initial: float = 0.0) -> AnimatedValue:
    """Return an [`AnimatedValue`][pythonnative.AnimatedValue] that is stable across renders.

    Convenience wrapper for the common pattern
    ``pn.use_memo(lambda: AnimatedValue(initial), [])``. The same
    instance is returned on every render of the same component, so
    you can drive it from event handlers without recreating it.

    Args:
        initial: The starting numeric value.

    Returns:
        A mount-stable [`AnimatedValue`][pythonnative.AnimatedValue].

    Example:
        ```python
        import pythonnative as pn


        @pn.component
        def FadeIn():
            opacity = pn.use_animated_value(0.0)

            async def fade_in():
                await pn.Animated.timing(opacity, to=1.0, duration=300)

            pn.use_async_effect(fade_in, [])
            return pn.Animated.View(
                pn.Text("Hello"),
                style=pn.style(opacity=opacity),
            )
        ```
    """
    from .hooks import use_memo

    return use_memo(lambda: AnimatedValue(initial), [])


__all__ = [
    "AnimatedValue",
    "Animated",
    "use_animated_value",
]
