"""Native-backed gesture system with composition and arbitration.

Attach gestures to any view-like element via the ``gestures=`` prop:

```python
import pythonnative as pn
from pythonnative import gestures


@pn.component
def Draggable():
    tx = pn.use_animated_value(0.0)
    ty = pn.use_animated_value(0.0)

    def on_end(event):
        pn.Animated.spring(tx, to=0.0).start()
        pn.Animated.spring(ty, to=0.0).start()

    return pn.Animated.View(
        pn.Text("Drag me"),
        style={"transform": [{"translate_x": tx}, {"translate_y": ty}], "padding": 24},
        gestures=[
            gestures.Pan(
                on_change=pn.Animated.event(translation_x=tx, translation_y=ty),
                on_end=on_end,
            )
        ],
    )
```

Each gesture descriptor is a frozen dataclass holding numeric
configuration plus user callbacks. The reconciler serializes the
configuration into plain dicts for the native handler (so prop diffing
never compares closures) and routes the callbacks through the
tag-based event channel. Recognition itself is native:

- **iOS** attaches real ``UIGestureRecognizer`` instances.
- **Android** feeds raw ``MotionEvent`` streams into the pure-Python
  [`GestureArbiter`][pythonnative.gestures.GestureArbiter] below.
- **Desktop** feeds Tk pointer events into the same arbiter.

Composition
-----------

Gestures in a plain ``gestures=[...]`` list all recognize
*simultaneously* (a press ripple plus a pan plus a pinch can all run at
once). To control how gestures interact, wrap them in composition
nodes, which nest arbitrarily:

- [`Simultaneous`][pythonnative.gestures.Simultaneous]: members may all
  activate together (the flat-list default, useful inside other nodes).
- [`Race`][pythonnative.gestures.Race]: the first member to activate
  wins; the rest fail for the remainder of the interaction.
- [`Exclusive`][pythonnative.gestures.Exclusive]: priority order. A
  member may only activate after every member listed *before* it has
  failed. ``Exclusive(double_tap, single_tap)`` is the classic
  double-tap-wins arrangement: the single tap fires only after the
  double-tap window expires.

```python
gestures=[
    gestures.Race(
        gestures.Pan(on_change=drag),
        gestures.LongPress(on_long_press=show_menu),
    ),
]
```

Every callback receives a [`GestureEvent`][pythonnative.gestures.GestureEvent]
with position, translation, velocity, scale, and rotation populated as
appropriate for the gesture kind.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Set, Tuple

__all__ = [
    "GestureState",
    "GestureEvent",
    "Tap",
    "LongPress",
    "Pan",
    "Swipe",
    "Fling",
    "Pinch",
    "Rotation",
    "Simultaneous",
    "Race",
    "Exclusive",
    "GestureGroup",
    "GestureArbiter",
    "serialize_gestures",
]


class GestureState:
    """States reported on [`GestureEvent.state`][pythonnative.gestures.GestureEvent]."""

    BEGAN = "began"
    CHANGED = "changed"
    ENDED = "ended"
    CANCELLED = "cancelled"


GestureStateName = Literal["began", "changed", "ended", "cancelled"]

GestureCallback = Callable[["GestureEvent"], None]

SwipeDirection = Literal["any", "left", "right", "up", "down"]


@dataclass(frozen=True)
class GestureEvent:
    """Snapshot delivered to gesture callbacks.

    Attributes:
        kind: Gesture kind (``"tap"``, ``"long_press"``, ``"pan"``,
            ``"swipe"``, ``"fling"``, ``"pinch"``, ``"rotation"``).
        state: One of [`GestureState`][pythonnative.gestures.GestureState].
        x: Pointer x-position in the view's coordinate space (points).
        y: Pointer y-position in the view's coordinate space (points).
        translation_x: Horizontal displacement since the gesture
            activated (pan only).
        translation_y: Vertical displacement since the gesture
            activated (pan only).
        velocity_x: Horizontal pointer velocity in points/second
            (pan, swipe, and fling).
        velocity_y: Vertical pointer velocity in points/second
            (pan, swipe, and fling).
        scale: Pinch scale factor relative to activation (pinch only).
        rotation: Rotation in radians relative to activation
            (rotation only).
        pointer_count: Number of pointers currently down.
        direction: Resolved swipe/fling direction.
    """

    kind: str
    state: GestureStateName
    x: float = 0.0
    y: float = 0.0
    translation_x: float = 0.0
    translation_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0
    pointer_count: int = 1
    direction: Optional[str] = None


_EVENT_FIELDS = frozenset(
    {
        "kind",
        "state",
        "x",
        "y",
        "translation_x",
        "translation_y",
        "velocity_x",
        "velocity_y",
        "scale",
        "rotation",
        "pointer_count",
        "direction",
    }
)


def event_from_payload(payload: Dict[str, Any]) -> GestureEvent:
    """Build a [`GestureEvent`][pythonnative.gestures.GestureEvent] from a payload dict.

    Unknown keys are dropped so platform handlers can attach extra
    diagnostics without breaking the public dataclass.
    """
    return GestureEvent(**{k: v for k, v in payload.items() if k in _EVENT_FIELDS})


# ======================================================================
# Public gesture descriptors
# ======================================================================


@dataclass(frozen=True)
class _BaseGesture:
    """Shared callback slots for continuous gestures."""

    on_begin: Optional[GestureCallback] = None
    on_change: Optional[GestureCallback] = None
    on_end: Optional[GestureCallback] = None

    kind: str = ""

    def _config(self) -> Dict[str, Any]:
        return {}

    def _to_spec(self) -> Dict[str, Any]:
        spec: Dict[str, Any] = {"kind": self.kind}
        spec.update(self._config())
        return spec

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.BEGAN:
            callback = self.on_begin
        elif event.state == GestureState.CHANGED:
            callback = self.on_change
        else:
            callback = self.on_end
        if callback is not None:
            callback(event)


@dataclass(frozen=True)
class Tap(_BaseGesture):
    """Recognize ``n_taps`` quick taps.

    Attributes:
        on_tap: Called once the tap (or multi-tap) completes.
        n_taps: Number of consecutive taps required (``2`` for
            double-tap).
        max_distance: Maximum pointer travel (points) for a touch to
            still count as a tap.
    """

    on_tap: Optional[GestureCallback] = None
    n_taps: int = 1
    max_distance: float = 12.0
    kind: str = "tap"

    def _config(self) -> Dict[str, Any]:
        return {"n_taps": int(self.n_taps), "max_distance": float(self.max_distance)}

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.ENDED and self.on_tap is not None:
            self.on_tap(event)
        else:
            super()._dispatch(event)


@dataclass(frozen=True)
class LongPress(_BaseGesture):
    """Recognize a sustained press.

    ``on_long_press`` fires as soon as the press has been held for
    ``min_duration_ms`` (matching ``UILongPressGestureRecognizer``);
    ``on_end`` fires when the finger lifts.

    Attributes:
        on_long_press: Called at activation time.
        min_duration_ms: Hold duration required to activate.
        max_distance: Maximum pointer travel before the press fails.
    """

    on_long_press: Optional[GestureCallback] = None
    min_duration_ms: float = 500.0
    max_distance: float = 12.0
    kind: str = "long_press"

    def _config(self) -> Dict[str, Any]:
        return {
            "min_duration_ms": float(self.min_duration_ms),
            "max_distance": float(self.max_distance),
        }

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.BEGAN and self.on_long_press is not None:
            self.on_long_press(event)
        else:
            super()._dispatch(event)


@dataclass(frozen=True)
class Pan(_BaseGesture):
    """Track a drag with translation and velocity.

    Activates once the pointer travels ``min_distance`` points, then
    reports ``on_change`` for every movement with translation measured
    from the activation point, and ``on_end`` with release velocity.

    Attributes:
        min_distance: Travel (points) required before the pan activates.
        min_pointers: Minimum pointers that must be down.
    """

    min_distance: float = 10.0
    min_pointers: int = 1
    kind: str = "pan"

    def _config(self) -> Dict[str, Any]:
        return {
            "min_distance": float(self.min_distance),
            "min_pointers": int(self.min_pointers),
        }


@dataclass(frozen=True)
class Swipe(_BaseGesture):
    """Recognize a quick directional flick.

    Attributes:
        on_swipe: Called once on release with the resolved
            ``direction`` and release velocity.
        direction: Required direction, or ``"any"``.
        min_velocity: Minimum release speed in points/second.
    """

    on_swipe: Optional[GestureCallback] = None
    direction: SwipeDirection = "any"
    min_velocity: float = 300.0
    kind: str = "swipe"

    def _config(self) -> Dict[str, Any]:
        return {"direction": str(self.direction), "min_velocity": float(self.min_velocity)}

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.ENDED and self.on_swipe is not None:
            self.on_swipe(event)
        else:
            super()._dispatch(event)


@dataclass(frozen=True)
class Fling(_BaseGesture):
    """Recognize a quick multi-pointer directional flick.

    Like [`Swipe`][pythonnative.gestures.Swipe] but with a pointer-count
    requirement, mirroring React Native Gesture Handler's ``Fling``
    (and iOS ``UISwipeGestureRecognizer`` with
    ``numberOfTouchesRequired``). A two-finger downward fling is a
    common dismiss gesture:

    ```python
    gestures.Fling(direction="down", n_pointers=2, on_fling=dismiss)
    ```

    Attributes:
        on_fling: Called once on release with the resolved
            ``direction`` and release velocity.
        direction: Required direction, or ``"any"``.
        n_pointers: Number of pointers that must participate.
        min_velocity: Minimum release speed in points/second.
    """

    on_fling: Optional[GestureCallback] = None
    direction: SwipeDirection = "any"
    n_pointers: int = 1
    min_velocity: float = 300.0
    kind: str = "fling"

    def _config(self) -> Dict[str, Any]:
        return {
            "direction": str(self.direction),
            "n_pointers": int(self.n_pointers),
            "min_velocity": float(self.min_velocity),
        }

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.ENDED and self.on_fling is not None:
            self.on_fling(event)
        else:
            super()._dispatch(event)


@dataclass(frozen=True)
class Pinch(_BaseGesture):
    """Track a two-finger pinch; ``event.scale`` is relative to activation."""

    kind: str = "pinch"


@dataclass(frozen=True)
class Rotation(_BaseGesture):
    """Track a two-finger rotation; ``event.rotation`` is in radians."""

    kind: str = "rotation"


GestureSpec = _BaseGesture
"""Any gesture descriptor accepted by the ``gestures=`` prop."""


# ======================================================================
# Composition nodes
# ======================================================================


@dataclass(frozen=True)
class GestureGroup:
    """A composition node relating child gestures (or nested groups).

    Build instances with [`Simultaneous`][pythonnative.gestures.Simultaneous],
    [`Race`][pythonnative.gestures.Race], or
    [`Exclusive`][pythonnative.gestures.Exclusive] rather than directly.
    """

    mode: Literal["simultaneous", "race", "exclusive"]
    children: Tuple[Any, ...] = field(default_factory=tuple)


def Simultaneous(*gestures: Any) -> GestureGroup:
    """Compose gestures that may all be active at the same time.

    This matches the flat-list default; it exists so simultaneity can
    be expressed *inside* [`Race`][pythonnative.gestures.Race] or
    [`Exclusive`][pythonnative.gestures.Exclusive] nodes:

    ```python
    gestures.Race(
        gestures.Simultaneous(gestures.Pinch(...), gestures.Rotation(...)),
        gestures.Pan(...),
    )
    ```
    """
    return GestureGroup("simultaneous", tuple(gestures))


def Race(*gestures: Any) -> GestureGroup:
    """Compose gestures where only the first to activate wins.

    As soon as one member activates, every other member fails for the
    rest of the interaction (its in-progress recognition is abandoned
    without firing callbacks).
    """
    return GestureGroup("race", tuple(gestures))


def Exclusive(*gestures: Any) -> GestureGroup:
    """Compose gestures by priority: earlier members outrank later ones.

    A member may only activate once every member listed before it has
    *failed*. ``Exclusive(double_tap, single_tap)`` delays the single
    tap until the double-tap window has expired, then fires it; if the
    second tap lands in time, only the double tap fires.
    """
    return GestureGroup("exclusive", tuple(gestures))


def serialize_gestures(
    specs: Sequence[Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Callable[..., Any]]]:
    """Flatten gesture descriptors into native config dicts and event routers.

    Composition nodes ([`Simultaneous`][pythonnative.gestures.Simultaneous],
    [`Race`][pythonnative.gestures.Race],
    [`Exclusive`][pythonnative.gestures.Exclusive]) are flattened
    depth-first; each resulting spec dict carries the relationship
    metadata the recognizers need:

    - ``"simultaneous"``: indices this gesture may be active alongside.
    - ``"wait_for"``: indices that must *fail* before this gesture may
      activate.

    Two gestures that are not in each other's ``simultaneous`` sets
    race: the first to activate causes the other to fail. Gestures in
    the top-level list (outside any composition node) are mutually
    simultaneous.

    Args:
        specs: The value of an element's ``gestures`` prop. Plain dicts
            are passed through with relationship metadata attached (no
            callbacks to route).

    Returns:
        ``(clean_specs, events)`` where ``clean_specs`` is a list of
        JSON-ish config dicts (one per leaf gesture, depth-first) and
        ``events`` maps ``"gesture:<i>"`` to a router that unpacks the
        native payload into a `GestureEvent` and invokes the right
        user callback.
    """
    leaves: List[Any] = []
    sim_pairs: Set[Tuple[int, int]] = set()
    wait_pairs: Set[Tuple[int, int]] = set()  # (waiter, target)

    def _flatten(node: Any) -> List[int]:
        if isinstance(node, GestureGroup):
            subtree_leaves: List[List[int]] = [_flatten(child) for child in node.children]
            for a_i in range(len(subtree_leaves)):
                for b_i in range(a_i + 1, len(subtree_leaves)):
                    for a in subtree_leaves[a_i]:
                        for b in subtree_leaves[b_i]:
                            if node.mode == "simultaneous":
                                sim_pairs.add((a, b))
                            elif node.mode == "exclusive":
                                # Later members wait for earlier ones.
                                wait_pairs.add((b, a))
            return [i for group in subtree_leaves for i in group]
        leaves.append(node)
        return [len(leaves) - 1]

    top_level: List[List[int]] = [_flatten(node) for node in specs]
    # Top-level entries are mutually simultaneous (flat-list default).
    for a_i in range(len(top_level)):
        for b_i in range(a_i + 1, len(top_level)):
            for a in top_level[a_i]:
                for b in top_level[b_i]:
                    sim_pairs.add((a, b))

    clean: List[Dict[str, Any]] = []
    events: Dict[str, Callable[..., Any]] = {}
    for i, leaf in enumerate(leaves):
        if isinstance(leaf, _BaseGesture):
            spec = leaf._to_spec()

            def _router(payload: Dict[str, Any], _spec: _BaseGesture = leaf) -> None:
                _spec._dispatch(event_from_payload(payload))

            events[f"gesture:{i}"] = _router
        elif isinstance(leaf, dict):
            spec = dict(leaf)
        else:
            spec = {"kind": ""}
        spec["simultaneous"] = sorted({b for a, b in sim_pairs if a == i} | {a for a, b in sim_pairs if b == i})
        spec["wait_for"] = sorted({t for w, t in wait_pairs if w == i})
        clean.append(spec)
    return clean, events


# ======================================================================
# Pure-Python recognition engine (Android + desktop backends)
# ======================================================================
#
# iOS uses real UIGestureRecognizers. Android and the desktop preview
# receive raw pointer streams instead, which this arbiter turns into
# the same GestureEvent payloads. Keeping it in pure Python makes the
# state machines unit-testable with scripted event sequences and
# guarantees identical semantics on both backends.

EmitFn = Callable[[int, Dict[str, Any]], None]
"""``emit(gesture_index, payload)``: the arbiter's output channel."""

# Internal (never user-visible) state used by recognizers to tell the
# arbiter they can no longer succeed for this interaction.
_FAILED = "__failed"


class _VelocityTracker:
    """Estimate pointer velocity from recent samples (points/second)."""

    __slots__ = ("_samples",)

    _WINDOW_S = 0.1

    def __init__(self) -> None:
        self._samples: List[Tuple[float, float, float]] = []

    def add(self, x: float, y: float, t: float) -> None:
        self._samples.append((x, y, t))
        cutoff = t - self._WINDOW_S
        while len(self._samples) > 2 and self._samples[0][2] < cutoff:
            self._samples.pop(0)

    def velocity(self) -> Tuple[float, float]:
        if len(self._samples) < 2:
            return (0.0, 0.0)
        x0, y0, t0 = self._samples[0]
        x1, y1, t1 = self._samples[-1]
        dt = t1 - t0
        if dt <= 1e-6:
            return (0.0, 0.0)
        return ((x1 - x0) / dt, (y1 - y0) / dt)

    def reset(self) -> None:
        self._samples.clear()


class _Recognizer:
    """Base class for one gesture's state machine."""

    def __init__(self, index: int, config: Dict[str, Any], emit: EmitFn) -> None:
        self.index = index
        self.config = config
        self._emit_fn = emit

    def emit(self, state: str, **fields: Any) -> None:
        payload: Dict[str, Any] = {"kind": self.kind(), "state": state}
        payload.update(fields)
        self._emit_fn(self.index, payload)

    def fail(self) -> None:
        """Report that this gesture can no longer succeed this interaction."""
        self._emit_fn(self.index, {"kind": self.kind(), "state": _FAILED})

    def force_fail(self, t: float) -> None:
        """Abandon recognition without emitting anything (lost a race)."""
        self.cancel(t)

    def kind(self) -> str:
        return str(self.config.get("kind", ""))

    # Event hooks: ``pointers`` maps pointer id -> (x, y).
    def down(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        pass

    def move(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        pass

    def up(self, pointers: Dict[int, Tuple[float, float]], t: float, x: float, y: float) -> None:
        pass

    def cancel(self, t: float) -> None:
        pass

    def deadline(self) -> Optional[float]:
        """Next time `poll` should run, or ``None``."""
        return None

    def poll(self, t: float) -> None:
        pass


def _centroid(pointers: Dict[int, Tuple[float, float]]) -> Tuple[float, float]:
    if not pointers:
        return (0.0, 0.0)
    xs = sum(p[0] for p in pointers.values())
    ys = sum(p[1] for p in pointers.values())
    n = len(pointers)
    return (xs / n, ys / n)


class _TapRecognizer(_Recognizer):
    def __init__(self, index: int, config: Dict[str, Any], emit: EmitFn) -> None:
        super().__init__(index, config, emit)
        self._n_taps = max(1, int(config.get("n_taps", 1)))
        self._slop = float(config.get("max_distance", 12.0))
        self._down_pos: Optional[Tuple[float, float]] = None
        self._down_time = 0.0
        self._tap_count = 0
        self._last_tap_time = 0.0
        self._failed = False
        # Deadline for the *next* tap of a multi-tap (or None).
        self._gap_deadline: Optional[float] = None

    _MAX_TAP_DURATION_S = 0.4
    _MULTI_TAP_GAP_S = 0.3

    def down(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if len(pointers) != 1:
            if not self._failed:
                self._failed = True
                self.fail()
            return
        if self._tap_count > 0 and t - self._last_tap_time > self._MULTI_TAP_GAP_S:
            self._tap_count = 0
        self._failed = False
        self._gap_deadline = None
        self._down_pos = _centroid(pointers)
        self._down_time = t

    def move(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if self._failed or self._down_pos is None:
            return
        x, y = _centroid(pointers)
        if math.hypot(x - self._down_pos[0], y - self._down_pos[1]) > self._slop:
            self._failed = True
            self.fail()

    def up(self, pointers: Dict[int, Tuple[float, float]], t: float, x: float, y: float) -> None:
        if self._failed or self._down_pos is None:
            self._reset()
            return
        if t - self._down_time > self._MAX_TAP_DURATION_S:
            self._reset()
            self.fail()
            return
        self._tap_count += 1
        self._last_tap_time = t
        if self._tap_count >= self._n_taps:
            self.emit(GestureState.ENDED, x=x, y=y)
            self._reset()
        else:
            # Waiting for the next tap; fail if it never arrives so
            # gestures waiting on this one (Exclusive) can proceed.
            self._gap_deadline = t + self._MULTI_TAP_GAP_S
        self._down_pos = None

    def cancel(self, t: float) -> None:
        self._reset()

    def deadline(self) -> Optional[float]:
        return self._gap_deadline

    def poll(self, t: float) -> None:
        if self._gap_deadline is not None and t >= self._gap_deadline:
            self._gap_deadline = None
            self._tap_count = 0
            self.fail()

    def _reset(self) -> None:
        self._down_pos = None
        self._tap_count = 0 if self._tap_count >= self._n_taps else self._tap_count
        self._failed = False
        self._gap_deadline = None


class _LongPressRecognizer(_Recognizer):
    def __init__(self, index: int, config: Dict[str, Any], emit: EmitFn) -> None:
        super().__init__(index, config, emit)
        self._duration_s = float(config.get("min_duration_ms", 500.0)) / 1000.0
        self._slop = float(config.get("max_distance", 12.0))
        self._down_pos: Optional[Tuple[float, float]] = None
        self._deadline: Optional[float] = None
        self._active = False

    def down(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        self._down_pos = _centroid(pointers)
        self._deadline = t + self._duration_s
        self._active = False

    def move(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if self._down_pos is None:
            return
        x, y = _centroid(pointers)
        if math.hypot(x - self._down_pos[0], y - self._down_pos[1]) > self._slop:
            if self._active:
                self.emit(GestureState.CANCELLED, x=x, y=y)
            self._reset()
            self.fail()

    def up(self, pointers: Dict[int, Tuple[float, float]], t: float, x: float, y: float) -> None:
        if self._active:
            self.emit(GestureState.ENDED, x=x, y=y)
        elif self._down_pos is not None:
            self.fail()
        self._reset()

    def cancel(self, t: float) -> None:
        if self._active:
            self.emit(GestureState.CANCELLED)
        self._reset()

    def deadline(self) -> Optional[float]:
        return self._deadline

    def poll(self, t: float) -> None:
        if self._deadline is None or self._down_pos is None or self._active:
            return
        if t >= self._deadline:
            self._active = True
            self._deadline = None
            self.emit(GestureState.BEGAN, x=self._down_pos[0], y=self._down_pos[1])

    def _reset(self) -> None:
        self._down_pos = None
        self._deadline = None
        self._active = False


class _PanRecognizer(_Recognizer):
    def __init__(self, index: int, config: Dict[str, Any], emit: EmitFn) -> None:
        super().__init__(index, config, emit)
        self._min_distance = float(config.get("min_distance", 10.0))
        self._min_pointers = max(1, int(config.get("min_pointers", 1)))
        self._origin: Optional[Tuple[float, float]] = None
        self._anchor: Optional[Tuple[float, float]] = None
        self._active = False
        self._velocity = _VelocityTracker()
        self._last_translation: Tuple[float, float] = (0.0, 0.0)

    @property
    def active(self) -> bool:
        return self._active

    def down(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if len(pointers) < self._min_pointers:
            return
        if self._origin is None:
            self._origin = _centroid(pointers)
            self._velocity.reset()
            x, y = self._origin
            self._velocity.add(x, y, t)
        else:
            # Pointer count changed; re-anchor so the centroid jump
            # doesn't teleport the translation.
            self._rebase(pointers)

    def move(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if self._origin is None or len(pointers) < self._min_pointers:
            return
        x, y = _centroid(pointers)
        self._velocity.add(x, y, t)
        if not self._active:
            if math.hypot(x - self._origin[0], y - self._origin[1]) < self._min_distance:
                return
            self._active = True
            self._anchor = (x, y)
            self.emit(GestureState.BEGAN, x=x, y=y, pointer_count=len(pointers))
            return
        assert self._anchor is not None
        vx, vy = self._velocity.velocity()
        self._last_translation = (x - self._anchor[0], y - self._anchor[1])
        self.emit(
            GestureState.CHANGED,
            x=x,
            y=y,
            translation_x=self._last_translation[0],
            translation_y=self._last_translation[1],
            velocity_x=vx,
            velocity_y=vy,
            pointer_count=len(pointers),
        )

    def up(self, pointers: Dict[int, Tuple[float, float]], t: float, x: float, y: float) -> None:
        if self._active and len(pointers) < self._min_pointers:
            vx, vy = self._velocity.velocity()
            anchor = self._anchor or (x, y)
            self.emit(
                GestureState.ENDED,
                x=x,
                y=y,
                translation_x=x - anchor[0],
                translation_y=y - anchor[1],
                velocity_x=vx,
                velocity_y=vy,
                pointer_count=len(pointers),
            )
            self._reset()
        elif not pointers:
            if not self._active and self._origin is not None:
                self.fail()
            self._reset()
        elif self._active:
            self._rebase(pointers)

    def cancel(self, t: float) -> None:
        if self._active:
            self.emit(GestureState.CANCELLED)
        self._reset()

    def _rebase(self, pointers: Dict[int, Tuple[float, float]]) -> None:
        """Re-anchor after a pointer-count change, preserving translation."""
        if not self._active or self._anchor is None:
            self._origin = _centroid(pointers)
            return
        x, y = _centroid(pointers)
        prev_tx, prev_ty = self._last_translation
        self._anchor = (x - prev_tx, y - prev_ty)

    def _reset(self) -> None:
        self._origin = None
        self._anchor = None
        self._active = False
        self._velocity.reset()
        self._last_translation = (0.0, 0.0)


class _SwipeRecognizer(_Recognizer):
    """Directional flick recognizer; also serves ``fling`` (adds pointer count)."""

    def __init__(self, index: int, config: Dict[str, Any], emit: EmitFn) -> None:
        super().__init__(index, config, emit)
        self._direction = str(config.get("direction", "any"))
        self._min_velocity = float(config.get("min_velocity", 300.0))
        self._n_pointers = max(1, int(config.get("n_pointers", 1)))
        self._velocity = _VelocityTracker()
        self._tracking = False
        self._max_pointers = 0

    def down(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if not self._tracking:
            self._velocity.reset()
            self._tracking = True
            self._max_pointers = 0
        self._max_pointers = max(self._max_pointers, len(pointers))
        x, y = _centroid(pointers)
        self._velocity.add(x, y, t)

    def move(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if not self._tracking:
            return
        self._max_pointers = max(self._max_pointers, len(pointers))
        x, y = _centroid(pointers)
        self._velocity.add(x, y, t)

    def up(self, pointers: Dict[int, Tuple[float, float]], t: float, x: float, y: float) -> None:
        if not self._tracking or pointers:
            return
        self._tracking = False
        self._velocity.add(x, y, t)
        vx, vy = self._velocity.velocity()
        speed = math.hypot(vx, vy)
        if speed < self._min_velocity or self._max_pointers < self._n_pointers:
            self.fail()
            return
        if abs(vx) >= abs(vy):
            direction = "right" if vx > 0 else "left"
        else:
            direction = "down" if vy > 0 else "up"
        if self._direction not in ("any", direction):
            self.fail()
            return
        self.emit(
            GestureState.ENDED,
            x=x,
            y=y,
            velocity_x=vx,
            velocity_y=vy,
            direction=direction,
            pointer_count=self._max_pointers,
        )

    def cancel(self, t: float) -> None:
        self._tracking = False
        self._max_pointers = 0
        self._velocity.reset()


class _PinchRecognizer(_Recognizer):
    def __init__(self, index: int, config: Dict[str, Any], emit: EmitFn) -> None:
        super().__init__(index, config, emit)
        self._initial: Optional[float] = None
        self._active = False
        self._scale = 1.0

    def _span(self, pointers: Dict[int, Tuple[float, float]]) -> Optional[float]:
        if len(pointers) < 2:
            return None
        pts = list(pointers.values())[:2]
        return math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])

    def down(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        span = self._span(pointers)
        if span is not None and span > 0 and self._initial is None:
            self._initial = span
            self._active = True
            x, y = _centroid(pointers)
            self.emit(GestureState.BEGAN, x=x, y=y, scale=1.0, pointer_count=len(pointers))

    def move(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if not self._active or self._initial is None:
            return
        span = self._span(pointers)
        if span is None or span <= 0:
            return
        self._scale = span / self._initial
        x, y = _centroid(pointers)
        self.emit(
            GestureState.CHANGED,
            x=x,
            y=y,
            scale=self._scale,
            pointer_count=len(pointers),
        )

    def up(self, pointers: Dict[int, Tuple[float, float]], t: float, x: float, y: float) -> None:
        if self._active and len(pointers) < 2:
            self.emit(GestureState.ENDED, x=x, y=y, scale=self._scale, pointer_count=len(pointers))
            self._reset()
        elif not self._active and not pointers:
            self.fail()

    def cancel(self, t: float) -> None:
        if self._active:
            self.emit(GestureState.CANCELLED, scale=self._scale)
        self._reset()

    def _reset(self) -> None:
        self._initial = None
        self._active = False
        self._scale = 1.0


class _RotationRecognizer(_Recognizer):
    def __init__(self, index: int, config: Dict[str, Any], emit: EmitFn) -> None:
        super().__init__(index, config, emit)
        self._initial: Optional[float] = None
        self._active = False
        self._rotation = 0.0

    def _angle(self, pointers: Dict[int, Tuple[float, float]]) -> Optional[float]:
        if len(pointers) < 2:
            return None
        pts = list(pointers.values())[:2]
        return math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0])

    def down(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        angle = self._angle(pointers)
        if angle is not None and self._initial is None:
            self._initial = angle
            self._active = True
            x, y = _centroid(pointers)
            self.emit(GestureState.BEGAN, x=x, y=y, rotation=0.0, pointer_count=len(pointers))

    def move(self, pointers: Dict[int, Tuple[float, float]], t: float) -> None:
        if not self._active or self._initial is None:
            return
        angle = self._angle(pointers)
        if angle is None:
            return
        delta = angle - self._initial
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi
        self._rotation = delta
        x, y = _centroid(pointers)
        self.emit(
            GestureState.CHANGED,
            x=x,
            y=y,
            rotation=self._rotation,
            pointer_count=len(pointers),
        )

    def up(self, pointers: Dict[int, Tuple[float, float]], t: float, x: float, y: float) -> None:
        if self._active and len(pointers) < 2:
            self.emit(GestureState.ENDED, x=x, y=y, rotation=self._rotation, pointer_count=len(pointers))
            self._reset()
        elif not self._active and not pointers:
            self.fail()

    def cancel(self, t: float) -> None:
        if self._active:
            self.emit(GestureState.CANCELLED, rotation=self._rotation)
        self._reset()

    def _reset(self) -> None:
        self._initial = None
        self._active = False
        self._rotation = 0.0


_RECOGNIZERS: Dict[str, Any] = {
    "tap": _TapRecognizer,
    "long_press": _LongPressRecognizer,
    "pan": _PanRecognizer,
    "swipe": _SwipeRecognizer,
    "fling": _SwipeRecognizer,
    "pinch": _PinchRecognizer,
    "rotation": _RotationRecognizer,
}

# Arbitration states for one recognizer within one interaction.
_POSSIBLE = "possible"
_WAITING = "waiting"  # activation buffered, awaiting wait_for targets
_ACTIVE = "active"
_DONE = "done"
_ST_FAILED = "failed"


class GestureArbiter:
    """Turn a raw pointer-event stream into arbitrated gesture payloads.

    One arbiter serves one view. The host backend feeds it normalized
    pointer events (positions in the view's coordinate space, times in
    seconds, any monotonic clock) and provides an ``emit`` callback
    that forwards ``(gesture_index, payload)`` pairs to
    [`dispatch_event`][pythonnative.events.dispatch_event].

    Beyond running each gesture's state machine, the arbiter enforces
    the relationships computed by
    [`serialize_gestures`][pythonnative.gestures.serialize_gestures]:

    - Two gestures not in each other's ``"simultaneous"`` sets race;
      when one activates, the other is force-failed for the rest of
      the interaction.
    - A gesture with a ``"wait_for"`` set may only activate after all
      of those gestures have failed. Its output (including a buffered
      discrete completion, like a single tap waiting out a double-tap
      window) is held and either flushed on failure of the targets or
      discarded if a target succeeds.

    Specs without relationship metadata (hand-built dicts) default to
    fully simultaneous, matching pre-composition behavior.

    Timing: after each pointer event, hosts should check
    [`next_deadline`][pythonnative.gestures.GestureArbiter.next_deadline]
    and schedule a [`poll`][pythonnative.gestures.GestureArbiter.poll]
    call for that time (long-press activation and multi-tap windows).
    """

    _DISCRETE_KINDS = frozenset({"tap", "swipe", "fling"})

    def __init__(self, specs: Sequence[Dict[str, Any]], emit: EmitFn) -> None:
        self._emit_out = emit
        self._pointers: Dict[int, Tuple[float, float]] = {}
        self._recognizers: List[_Recognizer] = []
        self._indices: List[int] = []
        self._sim: Dict[int, Optional[Set[int]]] = {}
        self._wait_for: Dict[int, Set[int]] = {}
        self._states: Dict[int, str] = {}
        self._buffers: Dict[int, List[Dict[str, Any]]] = {}
        self._last_t = 0.0
        for i, spec in enumerate(specs):
            recognizer_cls = _RECOGNIZERS.get(str(spec.get("kind", "")))
            if recognizer_cls is None:
                continue
            self._recognizers.append(recognizer_cls(i, spec, self._mediate))
            self._indices.append(i)
            sim = spec.get("simultaneous")
            # None means "simultaneous with everything" (back-compat
            # for hand-built spec dicts without metadata).
            self._sim[i] = None if sim is None else set(int(s) for s in sim)
            self._wait_for[i] = set(int(w) for w in spec.get("wait_for", ()) or ())
            self._states[i] = _POSSIBLE

    # -- pointer input ---------------------------------------------------

    def pointer_down(self, pointer_id: int, x: float, y: float, t: float) -> None:
        """Record a pointer press and advance every recognizer."""
        self._last_t = t
        if not self._pointers and not any(s == _WAITING for s in self._states.values()):
            # Fresh interaction: clear per-interaction verdicts.
            for i in self._indices:
                self._states[i] = _POSSIBLE
            self._buffers.clear()
        self._pointers[pointer_id] = (x, y)
        for recognizer in self._recognizers:
            recognizer.down(self._pointers, t)

    def pointer_move(self, pointer_id: int, x: float, y: float, t: float) -> None:
        """Record pointer travel and advance every recognizer."""
        self._last_t = t
        if pointer_id not in self._pointers:
            return
        self._pointers[pointer_id] = (x, y)
        for recognizer in self._recognizers:
            recognizer.move(self._pointers, t)

    def pointer_up(self, pointer_id: int, x: float, y: float, t: float) -> None:
        """Record a pointer release and advance every recognizer."""
        self._last_t = t
        self._pointers.pop(pointer_id, None)
        for recognizer in self._recognizers:
            recognizer.up(self._pointers, t, x, y)

    def cancel(self, t: float) -> None:
        """Abort every in-flight gesture (e.g. touch stolen by a scroll parent)."""
        self._last_t = t
        self._pointers.clear()
        self._buffers.clear()
        for i in self._indices:
            if self._states[i] == _WAITING:
                self._states[i] = _ST_FAILED
        for recognizer in self._recognizers:
            recognizer.cancel(t)

    def poll(self, t: float) -> None:
        """Advance time-based recognizers (long-press, multi-tap windows)."""
        self._last_t = t
        for recognizer in self._recognizers:
            recognizer.poll(t)

    def next_deadline(self) -> Optional[float]:
        """Earliest time `poll` should be called, or ``None``."""
        deadlines = [d for r in self._recognizers if (d := r.deadline()) is not None]
        return min(deadlines) if deadlines else None

    def has_active_pan(self) -> bool:
        """Whether a pan gesture is currently activated.

        Android handlers use this to call
        ``requestDisallowInterceptTouchEvent`` so an enclosing
        ScrollView doesn't steal the drag.
        """
        return any(isinstance(r, _PanRecognizer) and r.active for r in self._recognizers)

    # -- arbitration -------------------------------------------------------

    def _recognizer_for(self, index: int) -> Optional[_Recognizer]:
        for r in self._recognizers:
            if r.index == index:
                return r
        return None

    def _is_simultaneous(self, a: int, b: int) -> bool:
        sim_a = self._sim.get(a)
        sim_b = self._sim.get(b)
        if sim_a is None or sim_b is None:
            return True
        return b in sim_a and a in sim_b

    def _mediate(self, index: int, payload: Dict[str, Any]) -> None:
        state = payload.get("state")
        current = self._states.get(index, _POSSIBLE)

        if state == _FAILED:
            if current in (_POSSIBLE, _WAITING):
                self._set_failed(index, discard_buffer=True)
            return

        if current == _ST_FAILED:
            return

        if current == _ACTIVE:
            self._emit_out(index, payload)
            if state == GestureState.ENDED:
                self._states[index] = _DONE
                self._on_resolved(index, succeeded=True)
            elif state == GestureState.CANCELLED:
                self._states[index] = _ST_FAILED
                self._on_resolved(index, succeeded=False)
            return

        if current == _WAITING:
            # Recognition continues while the activation is parked;
            # keep buffering so a flush replays the full stream.
            self._buffers.setdefault(index, []).append(payload)
            return

        # current == _POSSIBLE: this payload is an activation attempt
        # (BEGAN, or a discrete completion such as a tap's ENDED).
        self._request_activation(index, payload)

    def _request_activation(self, index: int, payload: Dict[str, Any]) -> None:
        # Race check: blocked by any non-simultaneous gesture that has
        # already activated (or completed) this interaction.
        for j in self._indices:
            if j == index:
                continue
            if self._states[j] in (_ACTIVE, _DONE) and not self._is_simultaneous(index, j):
                self._set_failed(index, discard_buffer=True)
                return

        targets = [t for t in self._wait_for.get(index, ()) if t in self._states]
        if any(self._states[t] in (_ACTIVE, _DONE) for t in targets):
            self._set_failed(index, discard_buffer=True)
            return
        if any(self._states[t] in (_POSSIBLE, _WAITING) for t in targets):
            self._states[index] = _WAITING
            self._buffers.setdefault(index, []).append(payload)
            return

        self._activate(index, [payload])

    def _activate(self, index: int, payloads: List[Dict[str, Any]]) -> None:
        discrete_done = bool(payloads) and payloads[-1].get("state") in (
            GestureState.ENDED,
            GestureState.CANCELLED,
        )
        self._states[index] = _DONE if discrete_done else _ACTIVE
        # Winning a race force-fails every unresolved non-simultaneous
        # competitor before any output, so their recognizers stand down
        # (no stray callbacks later in the interaction).
        for j in self._indices:
            if j == index:
                continue
            if self._states[j] in (_POSSIBLE, _WAITING) and not self._is_simultaneous(index, j):
                recognizer = self._recognizer_for(j)
                if recognizer is not None:
                    recognizer.force_fail(self._last_t)
                self._set_failed(j, discard_buffer=True)
        for payload in payloads:
            self._emit_out(index, payload)
        if self._states[index] == _DONE:
            self._on_resolved(index, succeeded=True)

    def _set_failed(self, index: int, discard_buffer: bool) -> None:
        if self._states.get(index) == _ST_FAILED:
            return
        self._states[index] = _ST_FAILED
        if discard_buffer:
            self._buffers.pop(index, None)
        self._on_resolved(index, succeeded=False)

    def _on_resolved(self, index: int, succeeded: bool) -> None:
        """Re-evaluate gestures waiting on ``index`` after it resolves."""
        for waiter in self._indices:
            if self._states.get(waiter) != _WAITING:
                continue
            if index not in self._wait_for.get(waiter, ()):
                continue
            if succeeded:
                recognizer = self._recognizer_for(waiter)
                if recognizer is not None:
                    recognizer.force_fail(self._last_t)
                self._set_failed(waiter, discard_buffer=True)
                continue
            targets = [t for t in self._wait_for.get(waiter, ()) if t in self._states]
            if any(self._states[t] in (_POSSIBLE, _WAITING) for t in targets):
                continue  # still waiting on someone else
            if any(self._states[t] in (_ACTIVE, _DONE) for t in targets):
                recognizer = self._recognizer_for(waiter)
                if recognizer is not None:
                    recognizer.force_fail(self._last_t)
                self._set_failed(waiter, discard_buffer=True)
                continue
            payloads = self._buffers.pop(waiter, [])
            self._states[waiter] = _POSSIBLE
            self._activate(waiter, payloads)


# Re-exported via ``pythonnative.gestures`` for handler-side construction.
def make_arbiter(specs: Sequence[Dict[str, Any]], emit: EmitFn) -> GestureArbiter:
    """Build a [`GestureArbiter`][pythonnative.gestures.GestureArbiter] from serialized specs."""
    return GestureArbiter(specs, emit)
