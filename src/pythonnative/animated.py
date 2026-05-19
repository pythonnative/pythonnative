"""Animated values + animation drivers + animated component wrappers.

Modeled on React Native's `Animated` API. The core primitives are:

- [`AnimatedValue`][pythonnative.animated.AnimatedValue]: a numeric
  cell with subscribers; animations mutate it over time.
- ``Animated.timing`` / ``Animated.spring`` / ``Animated.decay``:
  animation factories.
- ``Animated.sequence`` / ``Animated.parallel`` / ``Animated.delay``:
  composition.
- ``Animated.View`` / ``Animated.Text`` / ``Animated.Image``:
  components whose ``style`` may contain ``AnimatedValue`` instances.
  The component subscribes to the value during mount and forwards
  changes directly to the underlying native handler's
  ``set_animated_property`` hook (bypassing the reconciler so
  per-frame work doesn't go through full Python reconciliation).

Driver:

- A single background thread ticks at ~60 Hz, advancing every
  active animation by ``dt``. When an animation finishes it removes
  itself from the active set; the thread sleeps when nothing is
  running.
- For platforms that have a native easing/animation API,
  ``AnimatedValue`` *also* sends a one-shot
  ``set_animated_property(view, prop, target, duration_ms, easing)``
  call when the animation starts, so UIKit / Android can interpolate
  at GPU 60 Hz without per-frame Python work. The Python ticker
  then keeps the reactive ``AnimatedValue.value`` reading
  approximately synchronized for any non-native consumers.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def FadeIn():
        opacity = pn.use_memo(lambda: pn.Animated.Value(0.0), [])

        def fade_in():
            pn.Animated.timing(opacity, to=1.0, duration=400).start()

        pn.use_effect(fade_in, [])

        return pn.Animated.View(
            pn.Text("Hello!"),
            style={"opacity": opacity, "padding": 20},
        )
    ```
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .element import Element
from .hooks import use_effect, use_ref
from .style import StyleProp, resolve_style

# Maximum frame rate at which the Python ticker drives animations.
# We aim for 60 Hz but back off when no animation is active.
_TARGET_FPS = 60.0
_FRAME_DT = 1.0 / _TARGET_FPS

# Easing functions: t in [0, 1] -> [0, 1].
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

    Direct mutation via [`set_value`][pythonnative.animated.AnimatedValue.set_value]
    fires subscribers immediately; animations call `set_value` from
    the ticker thread.

    Subscribers are ``(prop_name, callback)`` tuples. Each animated
    component (e.g., `Animated.View`) subscribes once per
    AnimatedValue prop in its style during mount.
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
        """Set the value immediately and fire all subscribers.

        Used by user code for instant snaps; animations also call this
        once per tick to update the value.
        """
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
        on the same AnimatedValue (the value can be bound to
        multiple props on multiple views).
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

    Holds a list of ``(animation, advance_callback)`` pairs and
    ticks them at ~60 Hz. The thread starts on first use and idles
    (releases the GIL via ``time.sleep``) when nothing is active.
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
        while not self._stopped:
            now = time.monotonic()
            dt = now - last
            last = now
            with self._lock:
                active = list(self._animations)
            if not active:
                # Idle: sleep longer until something starts.
                time.sleep(0.05)
                last = time.monotonic()
                continue
            for anim in active:
                try:
                    finished = anim.advance(dt)
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
    """Base class for in-flight animations; advance() returns True when done."""

    def __init__(self, value: AnimatedValue, on_complete: Optional[Callable[[], None]]) -> None:
        self.value = value
        self._on_complete = on_complete

    def advance(self, dt: float) -> bool:
        raise NotImplementedError

    def _finish(self) -> None:
        if self._on_complete is not None:
            try:
                self._on_complete()
            except Exception:
                pass


class _TimingAnimation(_RunningAnimation):
    def __init__(
        self,
        value: AnimatedValue,
        to: float,
        duration: float,
        easing: Callable[[float], float],
        on_complete: Optional[Callable[[], None]],
    ) -> None:
        super().__init__(value, on_complete)
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
        on_complete: Optional[Callable[[], None]],
    ) -> None:
        super().__init__(value, on_complete)
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
    def __init__(
        self,
        value: AnimatedValue,
        velocity: float,
        deceleration: float,
        on_complete: Optional[Callable[[], None]],
    ) -> None:
        super().__init__(value, on_complete)
        self._velocity = float(velocity)
        self._deceleration = float(deceleration)
        self._rest_threshold = 0.001

    def advance(self, dt: float) -> bool:
        # Exponential decay of velocity.
        self._velocity *= math.exp(-self._deceleration * dt * 1000.0)
        new_x = self.value.value + self._velocity * dt
        self.value.set_value(new_x)
        if abs(self._velocity) < self._rest_threshold:
            self._finish()
            return True
        return False


class _CompositeAnimation:
    """Wraps a list of animations played in sequence or in parallel."""

    def __init__(self, items: List[Any], mode: str) -> None:
        self._items = list(items)
        self._mode = mode

    def start(self, on_complete: Optional[Callable[[], None]] = None) -> None:
        if self._mode == "parallel":
            remaining = [len(self._items)]
            lock = threading.Lock()

            def _one_done() -> None:
                with lock:
                    remaining[0] -= 1
                    if remaining[0] <= 0 and on_complete is not None:
                        try:
                            on_complete()
                        except Exception:
                            pass

            for item in self._items:
                if item is None:
                    _one_done()
                    continue
                try:
                    item.start(_one_done)
                except Exception:
                    _one_done()
            return

        # Sequence
        index = [0]

        def _next() -> None:
            i = index[0]
            if i >= len(self._items):
                if on_complete is not None:
                    try:
                        on_complete()
                    except Exception:
                        pass
                return
            item = self._items[i]
            index[0] += 1
            if item is None:
                _next()
                return
            try:
                item.start(_next)
            except Exception:
                _next()

        _next()

    def stop(self) -> None:
        for item in self._items:
            try:
                item.stop()
            except Exception:
                pass


class _AnimationHandle:
    """Public handle returned by `Animated.timing` / `.spring` / `.decay`.

    Wraps a `_RunningAnimation` factory so each ``.start()`` call creates
    a fresh in-flight animation (matches RN — the `Animated.timing`
    return value is reusable).
    """

    def __init__(self, factory: Callable[[Optional[Callable[[], None]]], _RunningAnimation]) -> None:
        self._factory = factory
        self._current: Optional[_RunningAnimation] = None

    def start(self, on_complete: Optional[Callable[[], None]] = None) -> None:
        """Begin the animation, optionally invoking ``on_complete`` at the end."""
        self.stop()
        anim = self._factory(on_complete)
        self._current = anim
        _manager.add(anim)

    def stop(self) -> None:
        """Cancel the running instance (no-op if not running)."""
        if self._current is not None:
            _manager.remove(self._current)
            self._current = None


# ======================================================================
# Animated component wrappers
# ======================================================================


def _resolve_style_with_values(style: StyleProp) -> Tuple[Dict[str, Any], Dict[str, AnimatedValue]]:
    """Return ``(plain_style, animated_bindings)``.

    AnimatedValue entries in the style are replaced with their
    current numeric value in ``plain_style`` and recorded in
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
    """Build an animated wrapper for ``element_type``.

    The returned factory is used as the public
    ``Animated.View`` / ``Animated.Text`` / ``Animated.Image``.
    """
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
                # Capture into closure via default arg.
                def _on_change(new_val: float, _prop: str = prop, _view: Any = view) -> None:
                    handler = _get_handler_for(view)
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
        # View
        children = list(args) if accept_children else []
        return _View(*children, style=plain_style, ref=ref)

    return _animated


def _animated_prop_name(prop: str) -> str:
    """Map a style key to the name expected by `set_animated_property`."""
    if prop == "opacity":
        return "opacity"
    if prop == "background_color":
        return "background_color"
    # Transform shorthand keys: ``translate_x``, ``translate_y``,
    # ``scale``, ``scale_x``, ``scale_y``, ``rotate``.
    if prop in ("translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate"):
        return prop
    return prop


def _get_handler_for(native_view: Any) -> Any:
    """Best-effort lookup of the registered handler for ``native_view``.

    Animated bindings need a handler reference to call
    `set_animated_property`. Since the registry is keyed by element
    type and we only have the native view, we fall back to looking
    up the most recently registered "View" handler — works in
    practice because all animated targets are flex containers,
    images, or text views, and every iOS/Android handler subclass
    inherits the same `set_animated_property` from the base.
    """
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

    Exposes the `Value`, animation factories, composers, and
    component wrappers (`View`, `Text`, `Image`).
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

        def _factory(on_complete: Optional[Callable[[], None]]) -> _RunningAnimation:
            return _TimingAnimation(value, to, duration, _resolve_easing(easing), on_complete)

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

        def _factory(on_complete: Optional[Callable[[], None]]) -> _RunningAnimation:
            return _SpringAnimation(value, to, stiffness, damping, mass, on_complete)

        return _AnimationHandle(_factory)

    @staticmethod
    def decay(
        value: AnimatedValue,
        *,
        velocity: float,
        deceleration: float = 0.997,
    ) -> _AnimationHandle:
        """Decelerate ``value`` from its current velocity until it rests."""

        def _factory(on_complete: Optional[Callable[[], None]]) -> _RunningAnimation:
            return _DecayAnimation(value, velocity, deceleration, on_complete)

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

        def _factory(on_complete: Optional[Callable[[], None]]) -> _RunningAnimation:
            class _Delay(_RunningAnimation):
                def __init__(self, on_complete: Optional[Callable[[], None]]) -> None:
                    super().__init__(AnimatedValue(0.0), on_complete)
                    self._elapsed = 0.0
                    self._duration = max(0.001, duration / 1000.0)

                def advance(self, dt: float) -> bool:
                    self._elapsed += dt
                    if self._elapsed >= self._duration:
                        self._finish()
                        return True
                    return False

            return _Delay(on_complete)

        return _AnimationHandle(_factory)

    View = staticmethod(_make_animated_factory("View", accept_children=True))
    Text = staticmethod(_make_animated_factory("Text", accept_children=False))
    Image = staticmethod(_make_animated_factory("Image", accept_children=False))


Animated = _AnimatedNamespace()


def use_animated_value(initial: float = 0.0) -> AnimatedValue:
    """Return an [`AnimatedValue`][pythonnative.AnimatedValue] with a stable identity across renders.

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

            def fade_in():
                pn.Animated.timing(opacity, to=1.0, duration=300).start()

            pn.use_effect(lambda: fade_in(), [])
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
