"""Animated values, native-driven animation, and animated components.

Modeled on React Native's ``Animated`` API with an ``async``-aware
completion contract. The core primitives are:

- [`AnimatedValue`][pythonnative.animated.AnimatedValue]: a numeric
  cell attached to native view properties; animations drive it over
  time.
- ``Animated.timing`` / ``Animated.spring`` / ``Animated.decay``:
  animation factories. The objects they return implement
  ``__await__``, so you can write ``await Animated.timing(v, to=1.0)``
  to suspend until the animation finishes.
- ``Animated.sequence`` / ``Animated.parallel`` / ``Animated.delay``:
  composition; also awaitable.
- ``Animated.View`` / ``Animated.Text`` / ``Animated.Image``:
  components whose ``style`` may contain ``AnimatedValue`` instances.

Driver architecture (the **native driver**):

When an animation starts, PythonNative compiles its spec (curve,
duration, target value) and offers it to the platform handler of every
native view the value is attached to
([`ViewHandler.start_animation`][pythonnative.native_views.base.ViewHandler.start_animation]).

- **Accepted** (iOS Core Animation, Android ``ViewPropertyAnimator`` /
  ``DynamicAnimation``): the platform animates the property entirely
  natively; no Python code runs per frame. Python receives exactly one
  callback when the animation settles, updates the
  [`AnimatedValue`][pythonnative.animated.AnimatedValue], and resolves
  any awaiting tasks.
- **Declined** (desktop preview, unattached values, callable easings,
  values feeding Python-side listeners): a single background thread
  ticks the animation at ~60 Hz from Python, pushing each frame through
  ``set_animated_property``. Semantics are identical; only the frame
  source differs.

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
import itertools
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .element import Element
from .hooks import use_effect, use_ref
from .runtime import resolve_future
from .style import StyleProp, resolve_style

# Maximum frame rate at which the Python fallback ticker drives
# animations (native-driven animations run at the display's refresh
# rate, managed by the platform).
_TARGET_FPS = 60.0
_FRAME_DT = 1.0 / _TARGET_FPS

# Upper bound on how much wall-clock time the fallback loop will try to
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


def _backend() -> Any:
    """Return the active native-view registry (the animation backend)."""
    from .native_views import get_registry

    return get_registry()


# Process-unique ids for native animations, so completion callbacks can
# be routed without holding references on the native side.
_anim_id_counter = itertools.count(1)


# ======================================================================
# AnimatedValue
# ======================================================================


class AnimatedValue:
    """A numeric cell that can be attached to native view properties.

    Animated components (``Animated.View`` et al.) **attach** the value
    to ``(tag, prop)`` bindings after mount. Setting the value pushes
    the new number to every attached native view through the registry's
    ``set_animated_property``, and when an animation can be driven
    natively, the platform animates those same bindings directly.

    Python-side listeners registered via
    [`add_listener`][pythonnative.animated.AnimatedValue.add_listener]
    observe every Python-driven change. Natively-driven animations
    intentionally skip per-frame Python callbacks (that's the point);
    listeners see the final settled value.
    """

    __slots__ = ("_value", "_subscribers", "_attachments", "_lock", "_native_group")

    def __init__(self, initial: float = 0.0) -> None:
        self._value = float(initial)
        self._subscribers: List[Tuple[str, Callable[[float], None]]] = []
        self._attachments: List[Tuple[int, str]] = []
        self._lock = threading.Lock()
        # The in-flight native animation group driving this value, if any.
        self._native_group: Optional["_NativeAnimationGroup"] = None

    @property
    def value(self) -> float:
        """Return the current numeric value (without subscribing)."""
        return self._value

    def set_value(self, new_value: float) -> None:
        """Set the value immediately, pushing to native views and listeners."""
        self._apply(float(new_value), push_native=True)

    def _apply(self, new_value: float, push_native: bool) -> None:
        with self._lock:
            self._value = new_value
            subs = list(self._subscribers)
            attachments = list(self._attachments)
        if push_native and attachments:
            try:
                backend = _backend()
                for tag, prop in attachments:
                    backend.set_animated_property(tag, prop, new_value)
            except Exception:
                pass
        for prop, cb in subs:
            try:
                cb(new_value)
            except Exception:
                pass

    # -- bindings ------------------------------------------------------

    def attach(self, tag: int, prop: str) -> Callable[[], None]:
        """Bind this value to ``prop`` of the native view under ``tag``.

        The current value is pushed immediately so the view reflects it
        even if no animation is running. Returns a detach callable.
        """
        binding = (tag, prop)
        with self._lock:
            self._attachments.append(binding)
        try:
            _backend().set_animated_property(tag, prop, self._value)
        except Exception:
            pass

        def _detach() -> None:
            with self._lock:
                try:
                    self._attachments.remove(binding)
                except ValueError:
                    pass

        return _detach

    def attachments(self) -> List[Tuple[int, str]]:
        """Snapshot of the current ``(tag, prop)`` bindings."""
        with self._lock:
            return list(self._attachments)

    # -- listeners -----------------------------------------------------

    def add_listener(self, prop: str, callback: Callable[[float], None]) -> Callable[[], None]:
        """Register ``callback`` for Python-driven changes to this value.

        Returns an unsubscribe callable. ``prop`` is metadata only; it
        lets the subscriber differentiate this binding from others on
        the same ``AnimatedValue``.
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

    def has_listeners(self) -> bool:
        """Whether any Python-side listeners are registered."""
        with self._lock:
            return bool(self._subscribers)

    # -- native handoff ------------------------------------------------

    def _adopt_native_group(self, group: Optional["_NativeAnimationGroup"]) -> None:
        previous = self._native_group
        self._native_group = group
        if previous is not None and previous is not group:
            previous.cancel()

    def stop_animation(self) -> None:
        """Cancel any in-flight animation on this value (native or Python)."""
        self._adopt_native_group(None)
        _manager.cancel_for_value(self)

    def __float__(self) -> float:
        return self._value

    def __repr__(self) -> str:
        return f"AnimatedValue({self._value:g})"


# ======================================================================
# Python fallback driver
# ======================================================================


class _AnimationManager:
    """Single-threaded fallback driver for Python-ticked animations.

    Holds a list of ``_RunningAnimation`` instances and ticks them at
    ~60 Hz. The thread starts on first use and idles when nothing is
    active. Native-driven animations never touch this loop.
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

    def cancel_for_value(self, value: AnimatedValue) -> None:
        """Cancel every queued/running Python-driven animation on ``value``."""
        with self._lock:
            stale = [a for a in self._animations if a.value is value]
            for anim in stale:
                self._animations.remove(anim)
        for anim in stale:
            anim._finish()

    def _ensure_thread_locked(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pn-animated")
        self._thread.start()

    def _loop(self) -> None:
        last = time.monotonic()
        # Clamping the per-tick dt is important for numerical stability:
        # an underdamped spring with a 0.3 s step explodes immediately,
        # and the animation thread can be starved for several frames
        # during render bursts. We integrate physics on a clamped dt
        # (max 2 target frames) and sub-step when wall-clock has
        # advanced more than that, so the perceived motion still tracks
        # real time at most a couple of frames behind. After an extreme
        # starvation (e.g. the app was backgrounded for seconds) we cap
        # the catch-up at ``_MAX_CATCHUP_FRAMES`` worth of physics; any
        # further wall-clock drift is dropped on the floor, which keeps
        # the loop responsive instead of spinning forward through
        # hundreds of substeps.
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
# Python-driven animation primitives (the fallback path)
# ======================================================================


class _RunningAnimation:
    """Base class for Python-ticked animations; ``advance()`` returns True when done."""

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
        initial_velocity: float = 0.0,
    ) -> None:
        super().__init__(value)
        self._to = float(to)
        self._velocity = float(initial_velocity)
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
# Native-driven animation group
# ======================================================================


class _NativeAnimationGroup:
    """One logical animation fanned out to N natively-animated views.

    Each attached ``(tag, prop)`` binding gets its own ``anim_id``; the
    group completes when the platform reports completion for all of
    them. Cancellation asks each platform handler for the current
    presentation value so the ``AnimatedValue`` lands wherever the view
    visually was.
    """

    def __init__(self, value: AnimatedValue, final_value: float) -> None:
        self.value = value
        self.final_value = final_value
        self._targets: Dict[int, Tuple[int, str]] = {}  # anim_id -> (tag, prop)
        self._pending: set = set()
        self._completion_futures: List[asyncio.Future[None]] = []
        self._completed = False
        self._lock = threading.Lock()

    def add_target(self, anim_id: int, tag: int, prop: str) -> None:
        with self._lock:
            self._targets[anim_id] = (tag, prop)
            self._pending.add(anim_id)
        _native_groups[anim_id] = self

    def add_completion_future(self, future: asyncio.Future[None]) -> None:
        with self._lock:
            done = self._completed
            if not done:
                self._completion_futures.append(future)
        if done:
            resolve_future(future, None)

    def target_completed(self, anim_id: int, finished: bool) -> None:
        with self._lock:
            self._pending.discard(anim_id)
            remaining = len(self._pending)
        _native_groups.pop(anim_id, None)
        if remaining == 0:
            self._settle(self.final_value if finished else None)

    def cancel(self) -> None:
        """Cancel all in-flight native animations, syncing to presentation values."""
        with self._lock:
            targets = dict(self._targets)
            self._pending.clear()
        presentation: Optional[float] = None
        try:
            backend = _backend()
            for anim_id, (tag, _prop) in targets.items():
                _native_groups.pop(anim_id, None)
                current = backend.cancel_animation(tag, anim_id)
                if current is not None:
                    try:
                        presentation = float(current)
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass
        self._settle(presentation)

    def _settle(self, end_value: Optional[float]) -> None:
        with self._lock:
            if self._completed:
                return
            self._completed = True
            futures = list(self._completion_futures)
            self._completion_futures.clear()
        if self.value._native_group is self:
            self.value._native_group = None
        if end_value is not None:
            # The native side already shows this value; update the
            # Python cell (and listeners) without re-pushing.
            self.value._apply(end_value, push_native=False)
        for fut in futures:
            resolve_future(fut, None)


# anim_id -> group, for routing completion callbacks from platform handlers.
_native_groups: Dict[int, _NativeAnimationGroup] = {}


def native_animation_completed(anim_id: int, finished: bool = True) -> None:
    """Report a natively-driven animation as settled.

    Called by platform handlers from their completion callbacks (iOS
    ``UIView`` completion blocks, Android ``withEndAction`` /
    ``DynamicAnimation.OnAnimationEndListener``). Safe to call from any
    thread; unknown ids are ignored (e.g. an animation cancelled
    moments before its completion fired).

    Args:
        anim_id: The id passed to ``ViewHandler.start_animation``.
        finished: ``False`` when the platform reports the animation was
            interrupted rather than running to completion.
    """
    group = _native_groups.get(anim_id)
    if group is not None:
        group.target_completed(anim_id, finished)


def _projected_final_value(spec: Dict[str, Any]) -> float:
    """Compute where an animation will settle, from its spec."""
    kind = spec.get("kind")
    if kind == "decay":
        # v(t) = v0 · e^(−k·1000·t)  ⇒  ∫v dt = v0 / (k·1000)
        v0 = float(spec.get("velocity", 0.0))
        k = max(1e-6, float(spec.get("deceleration", 0.997)))
        return float(spec.get("from", 0.0)) + v0 / (k * 1000.0)
    return float(spec.get("to", spec.get("from", 0.0)))


def _start_native(value: AnimatedValue, spec: Dict[str, Any]) -> Optional[_NativeAnimationGroup]:
    """Offer ``spec`` to the platform for every binding of ``value``.

    Returns the live group when **all** bindings accepted the native
    animation; otherwise rolls back any accepted targets and returns
    ``None`` so the caller falls back to the Python ticker.
    """
    targets = value.attachments()
    if not targets:
        return None
    if value.has_listeners():
        # Python listeners want per-frame values; only the ticker
        # provides those.
        return None
    try:
        backend = _backend()
    except Exception:
        return None

    group = _NativeAnimationGroup(value, _projected_final_value(spec))
    accepted: List[Tuple[int, int]] = []  # (anim_id, tag)
    for tag, prop in targets:
        anim_id = next(_anim_id_counter)
        try:
            ok = backend.start_animation(tag, anim_id, prop, spec)
        except Exception:
            ok = False
        if not ok:
            for prev_id, prev_tag in accepted:
                _native_groups.pop(prev_id, None)
                try:
                    backend.cancel_animation(prev_tag, prev_id)
                except Exception:
                    pass
            return None
        group.add_target(anim_id, tag, prop)
        accepted.append((anim_id, tag))
    return group


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

    Each ``.start()`` call snapshots the value's current state, prefers
    the native driver, and falls back to a fresh Python-ticked
    animation otherwise (matches React Native: the ``Animated.timing``
    return value is reusable).
    """

    def __init__(
        self,
        value: Optional[AnimatedValue],
        spec_factory: Callable[[], Dict[str, Any]],
        fallback_factory: Callable[[], _RunningAnimation],
        native_eligible: bool = True,
    ) -> None:
        self._value = value
        self._spec_factory = spec_factory
        self._fallback_factory = fallback_factory
        self._native_eligible = native_eligible
        self._python_anim: Optional[_RunningAnimation] = None
        self._native_group: Optional[_NativeAnimationGroup] = None

    def start(self) -> "_AnimationHandle":
        """Begin the animation. Returns ``self`` for chaining."""
        self.stop()
        if self._value is not None and self._native_eligible:
            spec = self._spec_factory()
            group = _start_native(self._value, spec)
            if group is not None:
                self._native_group = group
                self._value._adopt_native_group(group)
                return self
        anim = self._fallback_factory()
        self._python_anim = anim
        _manager.add(anim)
        return self

    def stop(self) -> None:
        """Cancel the running instance (no-op if not running)."""
        if self._native_group is not None:
            group = self._native_group
            self._native_group = None
            if self._value is not None and self._value._native_group is group:
                self._value._native_group = None
            group.cancel()
        if self._python_anim is not None:
            anim = self._python_anim
            self._python_anim = None
            anim._finish()
            _manager.remove(anim)

    async def _drive(self) -> None:
        if self._native_group is None and self._python_anim is None:
            self.start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        if self._native_group is not None:
            self._native_group.add_completion_future(future)
        elif self._python_anim is not None:
            self._python_anim.add_completion_future(future)
        else:
            return
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
        # ``_AwaitableAnimation`` and plain awaitables/coroutines are
        # both supported: lets users mix in ``asyncio.sleep``.
        await item


# ======================================================================
# Animated component wrappers
# ======================================================================


def _resolve_style_with_values(style: StyleProp) -> Tuple[Dict[str, Any], Dict[str, AnimatedValue]]:
    """Split ``style`` into a plain dict and animated bindings.

    AnimatedValue entries in the style are replaced with their current
    numeric value in ``plain_style`` and recorded in
    ``animated_bindings`` so the wrapping component can attach them
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

        # ``@component`` packs positional children into the ``children``
        # prop (this function declares ``*args``), and the reconciler
        # re-invokes it with keyword props only, so at render time the
        # payload arrives in ``kwargs``, never in ``args``.
        children = list(args) or list(kwargs.pop("children", ()) or ())

        style = kwargs.pop("style", None)
        plain_style, bindings = _resolve_style_with_values(style)

        ref = use_ref(None)

        def _attach_bindings() -> Callable[[], None]:
            tag = ref._pn_tag
            if tag is None:
                return lambda: None
            detachers = [value.attach(tag, _animated_prop_name(prop)) for prop, value in bindings.items()]

            def _cleanup() -> None:
                for fn in detachers:
                    try:
                        fn()
                    except Exception:
                        pass

            return _cleanup

        # Re-attach whenever the binding set changes identity.
        use_effect(_attach_bindings, [tuple(sorted((k, id(v)) for k, v in bindings.items()))])

        if element_type == "Text":
            text = children[0] if children else kwargs.pop("text", "")
            return _Text(text, style=plain_style, ref=ref, **kwargs)
        if element_type == "Image":
            source = children[0] if children else kwargs.pop("source", "")
            return _Image(source, style=plain_style, ref=ref, **kwargs)
        if not accept_children:
            children = []
        return _View(*children, style=plain_style, ref=ref, **kwargs)

    return _animated


def _animated_prop_name(prop: str) -> str:
    """Map a style key to the name expected by ``set_animated_property``."""
    return prop


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
        """Interpolate ``value`` to ``to`` over ``duration`` ms with ``easing``."""

        def _spec() -> Dict[str, Any]:
            return {
                "kind": "timing",
                "from": value.value,
                "to": float(to),
                "duration_ms": float(duration),
                "easing": str(easing),
            }

        def _fallback() -> _RunningAnimation:
            return _TimingAnimation(value, to, duration, _resolve_easing(easing))

        # Callable easings can't cross the bridge; tick them in Python.
        return _AnimationHandle(value, _spec, _fallback, native_eligible=not callable(easing))

    @staticmethod
    def spring(
        value: AnimatedValue,
        *,
        to: float,
        stiffness: float = 100.0,
        damping: float = 10.0,
        mass: float = 1.0,
        initial_velocity: float = 0.0,
    ) -> _AnimationHandle:
        """Run a damped harmonic spring toward ``to``."""

        def _spec() -> Dict[str, Any]:
            return {
                "kind": "spring",
                "from": value.value,
                "to": float(to),
                "stiffness": float(stiffness),
                "damping": float(damping),
                "mass": float(mass),
                "initial_velocity": float(initial_velocity),
            }

        def _fallback() -> _RunningAnimation:
            return _SpringAnimation(value, to, stiffness, damping, mass, initial_velocity)

        return _AnimationHandle(value, _spec, _fallback)

    @staticmethod
    def decay(
        value: AnimatedValue,
        *,
        velocity: float,
        deceleration: float = 0.997,
    ) -> _AnimationHandle:
        """Decelerate ``value`` from ``velocity`` (units/ms) until it rests."""

        def _spec() -> Dict[str, Any]:
            return {
                "kind": "decay",
                "from": value.value,
                "velocity": float(velocity),
                "deceleration": float(deceleration),
            }

        def _fallback() -> _RunningAnimation:
            return _DecayAnimation(value, velocity, deceleration)

        return _AnimationHandle(value, _spec, _fallback)

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

        def _spec() -> Dict[str, Any]:
            return {"kind": "delay", "duration_ms": float(duration)}

        def _fallback() -> _RunningAnimation:
            return _DelayAnimation(duration)

        return _AnimationHandle(None, _spec, _fallback)

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
    "native_animation_completed",
]
