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

- **iOS** attaches real ``UIGestureRecognizer`` instances
  (``PythonNativeKit``), so gestures cooperate with scroll views and
  system gestures.
- **Android, the browser preview, and headless tests** feed raw pointer
  streams to the renderer core's gesture engine (RFC 0007), which
  recognizes and arbitrates them on the UI thread with the same rules.

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

Every descriptor accepts ``enabled=False`` to keep it in the list (so
sibling indices and composition stay stable) while it neither
recognizes nor takes part in arbitration. [`Pan`][pythonnative.gestures.Pan]
adds React Native Gesture Handler's activation criteria
(``active_offset_x``, ``fail_offset_y``, ``max_pointers``,
``min_velocity``, ...); the rules are spelled out on the class and
implemented identically by the core's engine and the iOS recognizers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, ClassVar, Dict, List, Literal, Optional, Sequence, Set, Tuple, Union

__all__ = [
    "DEFAULT_PAN_MIN_DISTANCE",
    "GestureState",
    "GestureEvent",
    "GestureSpec",
    "SwipeDirection",
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
    "serialize_gestures",
]


class GestureState(str, Enum):
    """Lifecycle states reported on [`GestureEvent.state`][pythonnative.gestures.GestureEvent].

    A ``str`` enum, so members compare equal to their wire value
    (``GestureState.ENDED == "ended"``) and serialize as plain strings
    across the native bridge, while callers get exhaustive
    ``match`` support and autocomplete.

    Attributes:
        BEGAN: The gesture activated (first callback).
        CHANGED: A continuous gesture updated (pan, pinch, rotation).
        ENDED: The gesture completed successfully.
        CANCELLED: The gesture was interrupted (lost arbitration, view
            unmounted, pointer left the window).
    """

    BEGAN = "began"
    CHANGED = "changed"
    ENDED = "ended"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value


GestureCallback = Callable[["GestureEvent"], Any]

SwipeDirection = Literal["left", "right", "up", "down"]
"""A resolved swipe or fling direction; ``None`` on a descriptor means any direction."""

_SWIPE_DIRECTIONS = frozenset({"left", "right", "up", "down"})

Offset = Union[float, Tuple[float, float]]
"""A pan activation or failure bound: one number or a ``(negative_bound, positive_bound)`` pair."""

DEFAULT_PAN_MIN_DISTANCE = 10.0
"""Points a pan must travel before activating when no other activation criterion is given."""


@dataclass(frozen=True)
class GestureEvent:
    """Snapshot delivered to gesture callbacks.

    Attributes:
        kind: Gesture kind (``"tap"``, ``"long_press"``, ``"pan"``,
            ``"swipe"``, ``"fling"``, ``"pinch"``, ``"rotation"``).
        state: One of [`GestureState`][pythonnative.gestures.GestureState].
        x: Pointer x-position in the view's coordinate space (points).
        y: Pointer y-position in the view's coordinate space (points).
        absolute_x: Pointer x-position in the window's coordinate
            space (points).
        absolute_y: Pointer y-position in the window's coordinate
            space (points).
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
        direction: Resolved swipe/fling direction, or ``None`` for
            other gesture kinds.
    """

    kind: str
    state: GestureState
    x: float = 0.0
    y: float = 0.0
    absolute_x: float = 0.0
    absolute_y: float = 0.0
    translation_x: float = 0.0
    translation_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0
    pointer_count: int = 1
    direction: Optional[SwipeDirection] = None

    def __post_init__(self) -> None:
        # Payloads from the native bridge carry plain strings; coerce
        # so ``event.state`` is always a ``GestureState`` member.
        if not isinstance(self.state, GestureState):
            object.__setattr__(self, "state", GestureState(self.state))


_EVENT_FIELDS = frozenset(
    {
        "kind",
        "state",
        "x",
        "y",
        "absolute_x",
        "absolute_y",
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


@dataclass(frozen=True, kw_only=True)
class _BaseGesture:
    """Shared callback slots and the ``enabled`` switch for every gesture.

    Attributes:
        on_begin: Called when a continuous gesture activates.
        on_change: Called on every update of a continuous gesture.
        on_end: Called when the gesture ends or is cancelled.
        enabled: When ``False`` the gesture stays in the list (indices
            and composition are unchanged) but never recognizes and is
            skipped by ``Race`` and ``Exclusive`` arbitration, so a
            later ``Exclusive`` member doesn't wait for it.
    """

    on_begin: Optional[GestureCallback] = None
    on_change: Optional[GestureCallback] = None
    on_end: Optional[GestureCallback] = None
    enabled: bool = True

    kind: ClassVar[str] = ""

    def _config(self) -> Dict[str, Any]:
        return {}

    def _to_spec(self) -> Dict[str, Any]:
        spec: Dict[str, Any] = {"kind": self.kind, "enabled": bool(self.enabled)}
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
            from .runtime import invoke

            invoke(callback, event)


@dataclass(frozen=True, kw_only=True)
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
    kind: ClassVar[str] = "tap"

    def _config(self) -> Dict[str, Any]:
        return {"n_taps": int(self.n_taps), "max_distance": float(self.max_distance)}

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.ENDED and self.on_tap is not None:
            from .runtime import invoke

            invoke(self.on_tap, event)
        else:
            super()._dispatch(event)


@dataclass(frozen=True, kw_only=True)
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
    kind: ClassVar[str] = "long_press"

    def _config(self) -> Dict[str, Any]:
        return {
            "min_duration_ms": float(self.min_duration_ms),
            "max_distance": float(self.max_distance),
        }

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.BEGAN and self.on_long_press is not None:
            from .runtime import invoke

            invoke(self.on_long_press, event)
        else:
            super()._dispatch(event)


def _normalize_offset(name: str, value: Any) -> Optional[List[Optional[float]]]:
    """Turn an ``Offset`` argument into the wire form ``[negative_bound, positive_bound]``.

    A single number ``n`` is a one-sided threshold: ``n >= 0`` bounds the
    positive direction only (``[None, n]``) and ``n < 0`` the negative
    direction only (``[n, None]``). A pair is ``(negative_bound,
    positive_bound)`` and must satisfy ``negative_bound <= 0 <=
    positive_bound``; either side may be ``None`` for "unbounded".
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a number or a (negative_bound, positive_bound) pair, not a bool")
    if isinstance(value, (int, float)):
        n = float(value)
        return [None, n] if n >= 0 else [n, None]
    try:
        lo, hi = value
    except (TypeError, ValueError):
        raise TypeError(f"{name} must be a number or a (negative_bound, positive_bound) pair (got {value!r})") from None
    low = None if lo is None else float(lo)
    high = None if hi is None else float(hi)
    if (low is not None and low > 0.0) or (high is not None and high < 0.0):
        raise ValueError(f"{name} pair must satisfy negative_bound <= 0 <= positive_bound (got {value!r})")
    return [low, high]


def _crosses(bounds: Optional[List[Optional[float]]], delta: float) -> bool:
    """Whether ``delta`` lies outside ``[negative_bound, positive_bound]`` (strict)."""
    if bounds is None:
        return False
    low, high = bounds
    return (low is not None and delta < low) or (high is not None and delta > high)


@dataclass(frozen=True, kw_only=True)
class Pan(_BaseGesture):
    """Track a drag with translation and velocity.

    Once the pan activates it reports ``on_change`` for every movement
    with translation measured from the activation point, and ``on_end``
    with the release velocity.

    **Activation rules** (the same on iOS, Android, and the browser
    preview). Before activation, with ``dx``/``dy`` the pointer travel
    from where it first touched down:

    1. If ``dx`` crosses ``fail_offset_x`` or ``dy`` crosses
       ``fail_offset_y``, the pan fails for the rest of the interaction.
    2. Otherwise the pan activates as soon as any one criterion holds:
       ``dx`` crosses ``active_offset_x``; ``dy`` crosses
       ``active_offset_y``; the straight-line travel is at least
       ``min_distance``; or the pointer speed is at least
       ``min_velocity``.

    "Crossing" a bound is strict: a single number ``n`` means ``dx > n``
    when ``n >= 0`` and ``dx < n`` when ``n < 0``; a
    ``(negative_bound, positive_bound)`` pair means ``dx <
    negative_bound or dx > positive_bound``, and the pair must satisfy
    ``negative_bound <= 0 <= positive_bound``. Following React Native
    Gesture Handler, the default ``min_distance`` of
    ``DEFAULT_PAN_MIN_DISTANCE`` (10 points) applies only when none of
    the offset or velocity criteria is given; pass ``min_distance``
    explicitly to combine it with them.

    Pointer counts: the pan tracks only while at least ``min_pointers``
    are down. When more than ``max_pointers`` touch down, a pan that
    hasn't activated fails and an active pan is cancelled.

    Attributes:
        min_distance: Travel (points) that activates the pan. ``None``
            (default) means 10 points unless another activation
            criterion is set.
        min_pointers: Minimum pointers that must be down.
        max_pointers: Maximum pointers allowed; ``None`` for no limit.
        active_offset_x: Horizontal travel that activates the pan.
        active_offset_y: Vertical travel that activates the pan.
        fail_offset_x: Horizontal travel that fails the pan.
        fail_offset_y: Vertical travel that fails the pan.
        min_velocity: Pointer speed in points/second that activates the
            pan regardless of distance.

    Example:
        ```python
        # A horizontal swipe-to-dismiss row inside a vertical list.
        gestures.Pan(active_offset_x=(-20, 20), fail_offset_y=(-15, 15), on_change=drag)
        ```
    """

    min_distance: Optional[float] = None
    min_pointers: int = 1
    max_pointers: Optional[int] = None
    active_offset_x: Optional[Offset] = None
    active_offset_y: Optional[Offset] = None
    fail_offset_x: Optional[Offset] = None
    fail_offset_y: Optional[Offset] = None
    min_velocity: Optional[float] = None
    kind: ClassVar[str] = "pan"

    def __post_init__(self) -> None:
        for name in ("active_offset_x", "active_offset_y", "fail_offset_x", "fail_offset_y"):
            _normalize_offset(name, getattr(self, name))
        if self.min_distance is not None and float(self.min_distance) < 0.0:
            raise ValueError("min_distance must be non-negative")
        if int(self.min_pointers) < 1:
            raise ValueError("min_pointers must be at least 1")
        if self.max_pointers is not None and int(self.max_pointers) < int(self.min_pointers):
            raise ValueError("max_pointers must be at least min_pointers")
        if self.min_velocity is not None and float(self.min_velocity) < 0.0:
            raise ValueError("min_velocity must be non-negative")

    def _has_custom_activation(self) -> bool:
        return any(
            value is not None
            for value in (
                self.active_offset_x,
                self.active_offset_y,
                self.fail_offset_x,
                self.fail_offset_y,
                self.min_velocity,
            )
        )

    def _config(self) -> Dict[str, Any]:
        min_distance: Optional[float]
        if self.min_distance is not None:
            min_distance = float(self.min_distance)
        elif self._has_custom_activation():
            min_distance = None
        else:
            min_distance = DEFAULT_PAN_MIN_DISTANCE
        return {
            "min_distance": min_distance,
            "min_pointers": int(self.min_pointers),
            "max_pointers": None if self.max_pointers is None else int(self.max_pointers),
            "active_offset_x": _normalize_offset("active_offset_x", self.active_offset_x),
            "active_offset_y": _normalize_offset("active_offset_y", self.active_offset_y),
            "fail_offset_x": _normalize_offset("fail_offset_x", self.fail_offset_x),
            "fail_offset_y": _normalize_offset("fail_offset_y", self.fail_offset_y),
            "min_velocity": None if self.min_velocity is None else float(self.min_velocity),
        }


def _check_direction(direction: Any) -> None:
    if direction is not None and direction not in _SWIPE_DIRECTIONS:
        raise ValueError(
            f"direction must be one of left, right, up, down, or None for any direction (got {direction!r})"
        )


@dataclass(frozen=True, kw_only=True)
class Swipe(_BaseGesture):
    """Recognize a quick directional flick.

    Attributes:
        on_swipe: Called once on release with the resolved
            ``direction`` and release velocity.
        direction: Required direction, or ``None`` for any direction.
        min_velocity: Minimum release speed in points/second.
    """

    on_swipe: Optional[GestureCallback] = None
    direction: Optional[SwipeDirection] = None
    min_velocity: float = 300.0
    kind: ClassVar[str] = "swipe"

    def __post_init__(self) -> None:
        _check_direction(self.direction)

    def _config(self) -> Dict[str, Any]:
        return {"direction": self.direction or "any", "min_velocity": float(self.min_velocity)}

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.ENDED and self.on_swipe is not None:
            from .runtime import invoke

            invoke(self.on_swipe, event)
        else:
            super()._dispatch(event)


@dataclass(frozen=True, kw_only=True)
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
        direction: Required direction, or ``None`` for any direction.
        n_pointers: Number of pointers that must participate.
        min_velocity: Minimum release speed in points/second.
    """

    on_fling: Optional[GestureCallback] = None
    direction: Optional[SwipeDirection] = None
    n_pointers: int = 1
    min_velocity: float = 300.0
    kind: ClassVar[str] = "fling"

    def __post_init__(self) -> None:
        _check_direction(self.direction)

    def _config(self) -> Dict[str, Any]:
        return {
            "direction": self.direction or "any",
            "n_pointers": int(self.n_pointers),
            "min_velocity": float(self.min_velocity),
        }

    def _dispatch(self, event: GestureEvent) -> None:
        if event.state == GestureState.ENDED and self.on_fling is not None:
            from .runtime import invoke

            invoke(self.on_fling, event)
        else:
            super()._dispatch(event)


@dataclass(frozen=True, kw_only=True)
class Pinch(_BaseGesture):
    """Track a two-finger pinch; ``event.scale`` is relative to activation."""

    kind: ClassVar[str] = "pinch"


@dataclass(frozen=True, kw_only=True)
class Rotation(_BaseGesture):
    """Track a two-finger rotation; ``event.rotation`` is in radians."""

    kind: ClassVar[str] = "rotation"


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

    A gesture with ``enabled=False`` keeps its index and its
    ``"enabled": false`` config so the native side can skip it, but it
    is left out of every relationship: nothing waits for it and it
    races nobody.

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

    def _enabled(leaf: Any) -> bool:
        if isinstance(leaf, _BaseGesture):
            return bool(leaf.enabled)
        if isinstance(leaf, dict):
            return leaf.get("enabled", True) is not False
        return True

    disabled = {i for i, leaf in enumerate(leaves) if not _enabled(leaf)}
    sim_pairs = {(a, b) for a, b in sim_pairs if a not in disabled and b not in disabled}
    wait_pairs = {(w, t) for w, t in wait_pairs if w not in disabled and t not in disabled}

    clean: List[Dict[str, Any]] = []
    events: Dict[str, Callable[..., Any]] = {}
    for i, leaf in enumerate(leaves):
        if isinstance(leaf, _BaseGesture):
            spec = leaf._to_spec()
            from .animated import AnimatedEvent

            animated = {}
            for state, callback in (
                ("began", leaf.on_begin),
                ("changed", leaf.on_change),
                ("ended", leaf.on_end),
            ):
                if isinstance(callback, AnimatedEvent):
                    animated[state] = {field: id(node) for field, node in callback._bindings.items()}
            if animated:
                spec["animated_events"] = animated

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
