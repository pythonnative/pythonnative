"""Animated values, derived animated nodes, and native-driven animation.

Modeled on React Native's ``Animated`` API with an ``async``-aware
completion contract. The core primitives are:

- [`AnimatedValue`][pythonnative.animated.AnimatedValue]: a numeric
  cell attached to native view properties; animations drive it over
  time.
- **Derived nodes**: every animated node supports
  [`interpolate`][pythonnative.animated.AnimatedNode.interpolate]
  (range mapping with numeric, color, and angle outputs) and Python
  arithmetic (``opacity * 0.5``, ``x + y``, ``-value``), producing
  read-only [`AnimatedNode`][pythonnative.animated.AnimatedNode]
  instances that update whenever their inputs change.
- ``Animated.timing`` / ``Animated.spring`` / ``Animated.decay``:
  animation factories. The objects they return implement
  ``__await__``, so you can write ``await Animated.timing(v, to=1.0)``
  to suspend until the animation finishes.
- ``Animated.sequence`` / ``Animated.parallel`` / ``Animated.stagger``
  / ``Animated.delay`` / ``Animated.loop``: composition; also
  awaitable.
- ``Animated.event``: build an event-prop callback that copies event
  fields into animated values (``on_scroll=pn.Animated.event(y=v)``).
- ``Animated.diff_clamp``: accumulate an input's *deltas* into a
  clamped range (the collapsing-header primitive).
- ``Animated.View`` / ``Animated.Text`` / ``Animated.Image``:
  components whose ``style`` may contain animated nodes, including
  inside ``transform`` entries.

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
  values feeding Python-side listeners or derived nodes): a single
  background thread ticks the animation at ~60 Hz from Python, pushing
  each frame through ``set_animated_property``. Semantics are
  identical; only the frame source differs.

Values driven by *events* (scroll offsets via ``Animated.event``,
gesture translations) flow through Python: the native listener fires,
the bound values update, and every attachment (including derived
nodes) is pushed in the same call.

Example:
    ```python
    import pythonnative as pn


    @pn.component
    def FadeIn():
        opacity = pn.use_animated_value(0.0)

        async def fade_in():
            await pn.Animated.timing(opacity, to=1.0, duration=400)
            await pn.Animated.timing(opacity, to=0.5, duration=200)

        pn.use_effect(fade_in, [])

        return pn.Animated.View(
            pn.Text("Hello!"),
            style={"opacity": opacity, "padding": 20},
        )
    ```
"""

from __future__ import annotations

import asyncio
import bisect
import itertools
import math
import threading
import time
import weakref
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

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
# AnimatedNode: the shared graph-node base
# ======================================================================


class AnimatedNode:
    """Base class for every animated node (settable leaves and derived nodes).

    An animated node holds a current output value and a set of
    ``(tag, prop)`` **attachments** binding it to native view
    properties. Whenever the node's output changes (a leaf was set or
    animated, or an input of a derived node changed), the new value is
    pushed to every attachment through the registry's
    ``set_animated_property`` and to every Python-side listener, then
    propagated to derived nodes built from this one.

    Derived nodes are constructed with
    [`interpolate`][pythonnative.animated.AnimatedNode.interpolate],
    with Python arithmetic operators (``+``, ``-``, ``*``, ``/``,
    ``%``, unary ``-``), or with ``Animated.diff_clamp``. They are
    read-only: only [`AnimatedValue`][pythonnative.AnimatedValue]
    leaves can be set or animated directly.
    """

    __slots__ = ("_subscribers", "_attachments", "_lock", "_children", "__weakref__")

    def __init__(self) -> None:
        self._subscribers: List[Tuple[str, Callable[[Any], None]]] = []
        self._attachments: List[Tuple[int, str]] = []
        self._lock = threading.Lock()
        # Derived nodes built from this one. Weak so a discarded
        # interpolation doesn't keep receiving pushes forever.
        self._children: "weakref.WeakSet[AnimatedNode]" = weakref.WeakSet()

    # -- value -----------------------------------------------------------

    @property
    def value(self) -> Any:
        """Return the node's current output value."""
        raise NotImplementedError

    def __float__(self) -> float:
        try:
            return float(self.value)
        except (TypeError, ValueError):
            return 0.0

    # -- graph -----------------------------------------------------------

    def _adopt_child(self, child: "AnimatedNode") -> None:
        with self._lock:
            self._children.add(child)

    def _has_dependents(self) -> bool:
        """Whether any derived node consumes this node's output."""
        with self._lock:
            return len(self._children) > 0

    def _refresh(self) -> None:
        """Hook for stateful derived nodes to update from their inputs."""

    def _propagate(self) -> None:
        """Push the current output to attachments/listeners and descend."""
        self._refresh()
        current = self.value
        with self._lock:
            subs = list(self._subscribers)
            attachments = list(self._attachments)
            children = list(self._children)
        if attachments:
            try:
                backend = _backend()
                for tag, prop in attachments:
                    backend.set_animated_property(tag, prop, current)
            except Exception:
                pass
        for _prop, cb in subs:
            try:
                cb(current)
            except Exception:
                pass
        for child in children:
            child._propagate()

    # -- bindings ----------------------------------------------------------

    def attach(self, tag: int, prop: str) -> Callable[[], None]:
        """Bind this node to ``prop`` of the native view under ``tag``.

        The current value is pushed immediately so the view reflects it
        even if no animation is running. Returns a detach callable.
        """
        binding = (tag, prop)
        with self._lock:
            self._attachments.append(binding)
        try:
            _backend().set_animated_property(tag, prop, self.value)
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

    # -- listeners ---------------------------------------------------------

    def add_listener(self, prop: str, callback: Callable[[Any], None]) -> Callable[[], None]:
        """Register ``callback`` for Python-driven changes to this node.

        Returns an unsubscribe callable. ``prop`` is metadata only; it
        lets the subscriber differentiate this binding from others on
        the same node.
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

    # -- derivation --------------------------------------------------------

    def interpolate(
        self,
        input_range: Sequence[float],
        output_range: Sequence[Any],
        extrapolate: str = "extend",
        extrapolate_left: Optional[str] = None,
        extrapolate_right: Optional[str] = None,
    ) -> "AnimatedInterpolation":
        """Map this node's value through an input/output range.

        Mirrors React Native's ``interpolate``. ``output_range`` may
        contain numbers, colors (``"#RRGGBB"`` / ``"#AARRGGBB"``), or
        angle strings (``"45deg"`` / ``"0.5rad"``, emitted as numeric
        degrees for the ``rotate`` transform).

        Args:
            input_range: Monotonically non-decreasing breakpoints for
                this node's value. At least two entries.
            output_range: Output breakpoints, same length as
                ``input_range``.
            extrapolate: Behavior outside the input range:
                ``"extend"`` (continue the edge segment's slope,
                default), ``"clamp"`` (pin to the edge output), or
                ``"identity"`` (return the input unchanged).
            extrapolate_left: Override ``extrapolate`` below the range.
            extrapolate_right: Override ``extrapolate`` above the range.

        Returns:
            A derived, read-only animated node.

        Example:
            ```python
            header_height = scroll_y.interpolate(
                input_range=[0, 120],
                output_range=[160, 56],
                extrapolate="clamp",
            )
            ```
        """
        return AnimatedInterpolation(
            self,
            input_range,
            output_range,
            extrapolate=extrapolate,
            extrapolate_left=extrapolate_left,
            extrapolate_right=extrapolate_right,
        )

    # -- arithmetic --------------------------------------------------------

    def __add__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("add", lambda a, b: a + b, [self, other])

    def __radd__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("add", lambda a, b: a + b, [other, self])

    def __sub__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("subtract", lambda a, b: a - b, [self, other])

    def __rsub__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("subtract", lambda a, b: a - b, [other, self])

    def __mul__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("multiply", lambda a, b: a * b, [self, other])

    def __rmul__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("multiply", lambda a, b: a * b, [other, self])

    def __truediv__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("divide", lambda a, b: a / b if b else 0.0, [self, other])

    def __rtruediv__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("divide", lambda a, b: a / b if b else 0.0, [other, self])

    def __mod__(self, other: Any) -> "_AnimatedOperation":
        return _AnimatedOperation("modulo", lambda a, b: math.fmod(a, b) if b else 0.0, [self, other])

    def __neg__(self) -> "_AnimatedOperation":
        return _AnimatedOperation("negate", lambda a: -a, [self])


# ======================================================================
# AnimatedValue: the settable leaf
# ======================================================================


class AnimatedValue(AnimatedNode):
    """A numeric cell that can be attached to native view properties.

    Animated components (``Animated.View`` et al.) **attach** the value
    to ``(tag, prop)`` bindings after mount. Setting the value pushes
    the new number to every attached native view through the registry's
    ``set_animated_property`` (and through every derived node built
    from this value), and when an animation can be driven natively, the
    platform animates those same bindings directly.

    Python-side listeners registered via
    [`add_listener`][pythonnative.animated.AnimatedNode.add_listener]
    observe every Python-driven change. Natively-driven animations
    intentionally skip per-frame Python callbacks (that's the point);
    listeners see the final settled value.
    """

    __slots__ = ("_value", "_native_group")

    def __init__(self, initial: float = 0.0) -> None:
        super().__init__()
        self._value = float(initial)
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
            children = list(self._children)
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
        for child in children:
            child._propagate()

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

    def __repr__(self) -> str:
        return f"AnimatedValue({self._value:g})"


# ======================================================================
# Derived nodes
# ======================================================================


def _parse_color_output(value: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse ``"#RRGGBB"`` / ``"#AARRGGBB"`` into an ``(a, r, g, b)`` tuple."""
    c = value.strip().lstrip("#")
    if len(c) == 6:
        c = "FF" + c
    if len(c) != 8:
        return None
    try:
        raw = int(c, 16)
    except ValueError:
        return None
    return ((raw >> 24) & 0xFF, (raw >> 16) & 0xFF, (raw >> 8) & 0xFF, raw & 0xFF)


def _parse_angle_output(value: str) -> Optional[float]:
    """Parse ``"45deg"`` / ``"0.5rad"`` into numeric degrees."""
    text = value.strip()
    try:
        if text.endswith("deg"):
            return float(text[:-3])
        if text.endswith("rad"):
            return math.degrees(float(text[:-3]))
    except ValueError:
        return None
    return None


class AnimatedInterpolation(AnimatedNode):
    """Read-only node mapping a parent node through an input/output range.

    Built via
    [`AnimatedNode.interpolate`][pythonnative.animated.AnimatedNode.interpolate];
    see that method for the semantics of the arguments.
    """

    __slots__ = (
        "_parent",
        "_inputs",
        "_outputs",
        "_kind",
        "_left",
        "_right",
    )

    def __init__(
        self,
        parent: AnimatedNode,
        input_range: Sequence[float],
        output_range: Sequence[Any],
        extrapolate: str = "extend",
        extrapolate_left: Optional[str] = None,
        extrapolate_right: Optional[str] = None,
    ) -> None:
        super().__init__()
        inputs = [float(v) for v in input_range]
        outputs = list(output_range)
        if len(inputs) < 2:
            raise ValueError("interpolate() needs at least two input_range entries")
        if len(inputs) != len(outputs):
            raise ValueError("interpolate() input_range and output_range must have the same length")
        for a, b in zip(inputs, inputs[1:]):
            if b < a:
                raise ValueError("interpolate() input_range must be monotonically non-decreasing")

        kind = "number"
        first = outputs[0]
        if isinstance(first, str):
            if _parse_color_output(first) is not None:
                kind = "color"
                outputs = [_parse_color_output(str(v)) for v in outputs]
                if any(v is None for v in outputs):
                    raise ValueError("interpolate() color output_range entries must all be colors")
            else:
                angles = [_parse_angle_output(str(v)) for v in outputs]
                if any(v is None for v in angles):
                    raise ValueError(f"interpolate() cannot parse output value {first!r}")
                outputs = angles
        else:
            outputs = [float(v) for v in outputs]

        self._parent = parent
        self._inputs = inputs
        self._outputs: List[Any] = outputs
        self._kind = kind
        self._left = extrapolate_left or extrapolate
        self._right = extrapolate_right or extrapolate
        parent._adopt_child(self)

    @property
    def value(self) -> Any:
        """Return the interpolated output for the parent's current value."""
        return self._compute(float(self._parent))

    def _compute(self, x: float) -> Any:
        inputs = self._inputs
        n = len(inputs)
        if x < inputs[0]:
            if self._left == "identity":
                return x
            if self._left == "clamp":
                x = inputs[0]
            i = 0
        elif x > inputs[-1]:
            if self._right == "identity":
                return x
            if self._right == "clamp":
                x = inputs[-1]
            i = n - 2
        else:
            i = max(0, min(n - 2, bisect.bisect_right(inputs, x) - 1))

        x0, x1 = inputs[i], inputs[i + 1]
        span = x1 - x0
        t = 0.0 if span <= 0 else (x - x0) / span

        if self._kind == "color":
            c0 = self._outputs[i]
            c1 = self._outputs[i + 1]
            t_cl = max(0.0, min(1.0, t))
            channels = [int(round(c0[j] + (c1[j] - c0[j]) * t_cl)) for j in range(4)]
            a, r, g, b = (max(0, min(255, ch)) for ch in channels)
            return f"#{a:02X}{r:02X}{g:02X}{b:02X}"

        y0 = self._outputs[i]
        y1 = self._outputs[i + 1]
        return y0 + (y1 - y0) * t

    def __repr__(self) -> str:
        return f"AnimatedInterpolation({self._inputs} -> {self._outputs})"


class _AnimatedOperation(AnimatedNode):
    """Read-only node computed from other nodes (and constants) by ``fn``."""

    __slots__ = ("_op", "_fn", "_parents")

    def __init__(self, op: str, fn: Callable[..., float], parents: List[Any]) -> None:
        super().__init__()
        self._op = op
        self._fn = fn
        self._parents = list(parents)
        for parent in self._parents:
            if isinstance(parent, AnimatedNode):
                parent._adopt_child(self)

    @property
    def value(self) -> float:
        args = [float(p) if isinstance(p, AnimatedNode) else float(p) for p in self._parents]
        try:
            return float(self._fn(*args))
        except Exception:
            return 0.0

    def __repr__(self) -> str:
        return f"AnimatedOperation({self._op})"


class _AnimatedDiffClamp(AnimatedNode):
    """Accumulate a parent's *deltas* into a clamped range.

    Mirrors React Native's ``Animated.diffClamp``: the output moves by
    the same amount as the input but is pinned to ``[min, max]``, so
    scrolling far down then slightly up immediately re-reveals a
    collapsing header regardless of absolute offset.
    """

    __slots__ = ("_parent", "_min", "_max", "_last_input", "_current")

    def __init__(self, parent: AnimatedNode, min_value: float, max_value: float) -> None:
        super().__init__()
        if max_value < min_value:
            raise ValueError("diff_clamp() requires min_value <= max_value")
        self._parent = parent
        self._min = float(min_value)
        self._max = float(max_value)
        self._last_input = float(parent)
        self._current = max(self._min, min(self._max, self._last_input))
        parent._adopt_child(self)

    @property
    def value(self) -> float:
        return self._current

    def _refresh(self) -> None:
        latest = float(self._parent)
        delta = latest - self._last_input
        self._last_input = latest
        self._current = max(self._min, min(self._max, self._current + delta))


# ======================================================================
# Animated.event
# ======================================================================


class AnimatedEvent:
    """Callable event handler copying event fields into animated values.

    Built via ``pn.Animated.event(...)``. Each keyword argument names a
    field on the incoming event payload (a dict key for scroll payloads
    such as ``{"x": ..., "y": ...}``, or an attribute for
    [`GestureEvent`][pythonnative.gestures.GestureEvent] instances) and
    maps it onto an [`AnimatedValue`][pythonnative.AnimatedValue].

    Because the result is an ordinary callable, it can be passed to any
    event prop:

    ```python
    scroll_y = pn.use_animated_value(0.0)
    pn.ScrollView(..., on_scroll=pn.Animated.event(y=scroll_y))

    tx = pn.use_animated_value(0.0)
    gestures.Pan(on_change=pn.Animated.event(translation_x=tx))
    ```
    """

    __slots__ = ("_bindings", "_listener")

    def __init__(self, listener: Optional[Callable[..., None]] = None, **bindings: AnimatedValue) -> None:
        for name, node in bindings.items():
            if not isinstance(node, AnimatedValue):
                raise TypeError(
                    f"Animated.event() field {name!r} must map to an AnimatedValue "
                    f"(got {type(node).__name__}); derived nodes are read-only."
                )
        self._bindings = dict(bindings)
        self._listener = listener

    def __call__(self, payload: Any = None, *args: Any) -> None:
        """Write bound payload fields into their values, then run the listener.

        Args:
            payload: The event payload; a dict is read by key, any
                other object by attribute. Missing or non-numeric
                fields are skipped.
            *args: Extra positional arguments forwarded to the
                listener.
        """
        for name, node in self._bindings.items():
            raw: Any = None
            if isinstance(payload, dict):
                raw = payload.get(name)
            elif payload is not None:
                raw = getattr(payload, name, None)
            if raw is None:
                continue
            try:
                node.set_value(float(raw))
            except (TypeError, ValueError):
                continue
        if self._listener is not None:
            try:
                self._listener(payload, *args)
            except Exception:
                pass


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
    if value._has_dependents():
        # Derived nodes (interpolations, arithmetic) need per-frame
        # Python evaluation to keep their own attachments in sync.
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

    def _is_running(self) -> bool:
        if self._native_group is not None and not self._native_group._completed:
            return True
        if self._python_anim is not None and not self._python_anim._completed:
            return True
        return False

    async def _drive(self) -> None:
        # (Re)start unless an instance is currently mid-flight, so a
        # reused handle (``Animated.loop``, awaiting the same handle
        # twice) runs a fresh animation instead of resolving instantly
        # against the finished previous instance.
        if not self._is_running():
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
    """Run a list of animations in sequence, in parallel, or staggered."""

    def __init__(self, items: List[Any], mode: str, stagger_ms: float = 0.0) -> None:
        self._items = list(items)
        self._mode = mode
        self._stagger_ms = float(stagger_ms)

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
        if self._mode == "stagger":
            delay_s = max(0.0, self._stagger_ms) / 1000.0

            async def _delayed(index: int, item: Any) -> None:
                if index > 0 and delay_s > 0.0:
                    await asyncio.sleep(delay_s * index)
                await self._await_item(item)

            await asyncio.gather(*(_delayed(i, item) for i, item in enumerate(self._items)))
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


class _LoopAnimation(_AwaitableAnimation):
    """Repeat an animation, resetting its values before each iteration."""

    def __init__(self, animation: Any, iterations: int = -1, reset: bool = True) -> None:
        self._animation = animation
        self._iterations = int(iterations)
        self._reset = bool(reset)
        self._stopped = False

    def start(self) -> "_LoopAnimation":
        from .runtime import run_async

        self._stopped = False
        run_async(self._drive())
        return self

    def stop(self) -> None:
        self._stopped = True
        try:
            self._animation.stop()
        except Exception:
            pass

    def _collect_values(self, item: Any, out: List[AnimatedValue]) -> None:
        if isinstance(item, _AnimationHandle):
            if item._value is not None and item._value not in out:
                out.append(item._value)
        elif isinstance(item, _CompositeAnimation):
            for sub in item._items:
                self._collect_values(sub, out)
        elif isinstance(item, _LoopAnimation):
            self._collect_values(item._animation, out)

    async def _drive(self) -> None:
        self._stopped = False
        values: List[AnimatedValue] = []
        self._collect_values(self._animation, values)
        origins = [(v, v.value) for v in values]
        count = 0
        while not self._stopped and (self._iterations < 0 or count < self._iterations):
            if self._reset and count > 0:
                for value, origin in origins:
                    value.set_value(origin)
            await self._animation
            count += 1


# ======================================================================
# Animated component wrappers
# ======================================================================

# Transform-entry keys that may carry animated nodes; the key doubles
# as the ``set_animated_property`` prop name.
_ANIMATED_TRANSFORM_KEYS = frozenset(
    {"translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate"},
)


def _resolve_style_with_values(style: StyleProp) -> Tuple[Dict[str, Any], Dict[str, AnimatedNode]]:
    """Split ``style`` into a plain dict and animated bindings.

    Animated nodes in the style (top-level values *and* values inside
    ``transform`` entries) are replaced with their current numeric
    value in ``plain_style`` and recorded in ``animated_bindings`` so
    the wrapping component can attach them after mount.
    """
    flat = resolve_style(style)
    bindings: Dict[str, AnimatedNode] = {}
    plain: Dict[str, Any] = {}
    for k, v in flat.items():
        if isinstance(v, AnimatedNode):
            bindings[k] = v
            plain[k] = v.value
        elif k == "transform" and v is not None:
            entries = v if isinstance(v, list) else [v]
            plain_entries: List[Any] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    plain_entries.append(entry)
                    continue
                clean_entry: Dict[str, Any] = {}
                for prop, val in entry.items():
                    if isinstance(val, AnimatedNode) and prop in _ANIMATED_TRANSFORM_KEYS:
                        bindings[prop] = val
                        clean_entry[prop] = val.value
                    else:
                        clean_entry[prop] = val
                plain_entries.append(clean_entry)
            plain[k] = plain_entries
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

    Exposes the ``Value`` type, animation factories, composers,
    derived-node helpers (``event``, ``diff_clamp``), and component
    wrappers (``View``, ``Text``, ``Image``).
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
    def stagger(delay: float, animations: List[Any]) -> _CompositeAnimation:
        """Run ``animations`` in parallel, each starting ``delay`` ms after the previous.

        Args:
            delay: Milliseconds between successive starts.
            animations: Animation handles (or awaitables) to run.

        Example:
            ```python
            pn.Animated.stagger(80, [
                pn.Animated.timing(v, to=1.0) for v in card_opacities
            ]).start()
            ```
        """
        return _CompositeAnimation(animations, "stagger", stagger_ms=delay)

    @staticmethod
    def loop(animation: Any, *, iterations: int = -1, reset: bool = True) -> _LoopAnimation:
        """Repeat ``animation``, optionally forever.

        Values driven by the animation are captured when the loop
        starts and restored before each iteration (matching React
        Native's ``resetBeforeIteration``), so ``timing`` loops replay
        the same motion instead of animating in place.

        Args:
            animation: A handle from ``timing`` / ``spring`` / ``decay``
                or a ``sequence`` / ``parallel`` / ``stagger`` composite.
            iterations: Number of repetitions; ``-1`` (default) loops
                until [`stop`][pythonnative.animated._LoopAnimation.stop]
                is called or the awaiting task is cancelled.
            reset: When ``False``, values continue from wherever the
                previous iteration ended.

        Example:
            ```python
            pulse = pn.Animated.loop(
                pn.Animated.sequence([
                    pn.Animated.timing(scale, to=1.15, duration=350),
                    pn.Animated.timing(scale, to=1.0, duration=350),
                ]),
            ).start()
            # later: pulse.stop()
            ```
        """
        return _LoopAnimation(animation, iterations=iterations, reset=reset)

    @staticmethod
    def delay(duration: float) -> _AnimationHandle:
        """Wait ``duration`` ms before continuing in a sequence."""

        def _spec() -> Dict[str, Any]:
            return {"kind": "delay", "duration_ms": float(duration)}

        def _fallback() -> _RunningAnimation:
            return _DelayAnimation(duration)

        return _AnimationHandle(None, _spec, _fallback)

    @staticmethod
    def event(listener: Optional[Callable[..., None]] = None, **bindings: AnimatedValue) -> AnimatedEvent:
        """Build a callback that copies event fields into animated values.

        Pass the result to any event prop. Each keyword maps a payload
        field (dict key or dataclass attribute) onto an
        [`AnimatedValue`][pythonnative.AnimatedValue]:

        ```python
        scroll_y = pn.use_animated_value(0.0)
        pn.ScrollView(..., on_scroll=pn.Animated.event(y=scroll_y))

        tx = pn.use_animated_value(0.0)
        gestures.Pan(on_change=pn.Animated.event(translation_x=tx))
        ```

        Args:
            listener: Optional plain callback invoked with the raw
                event after the values update.
            **bindings: ``field_name=animated_value`` pairs.

        Returns:
            A callable [`AnimatedEvent`][pythonnative.animated.AnimatedEvent].
        """
        return AnimatedEvent(listener, **bindings)

    @staticmethod
    def diff_clamp(node: AnimatedNode, min_value: float, max_value: float) -> AnimatedNode:
        """Accumulate ``node``'s deltas into ``[min_value, max_value]``.

        The classic collapsing-header primitive: unlike ``interpolate``
        with ``"clamp"`` (which pins the *absolute* input), the output
        tracks input *movement*, so a small scroll upward immediately
        re-reveals the header no matter how far down the list is.

        ```python
        header_shift = pn.Animated.diff_clamp(scroll_y, 0, 56)
        ```
        """
        return _AnimatedDiffClamp(node, min_value, max_value)

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

            pn.use_effect(fade_in, [])
            return pn.Animated.View(
                pn.Text("Hello"),
                style=pn.style(opacity=opacity),
            )
        ```
    """
    from .hooks import use_memo

    return use_memo(lambda: AnimatedValue(initial), [])


__all__ = [
    "AnimatedNode",
    "AnimatedValue",
    "AnimatedInterpolation",
    "AnimatedEvent",
    "Animated",
    "use_animated_value",
    "native_animation_completed",
]
