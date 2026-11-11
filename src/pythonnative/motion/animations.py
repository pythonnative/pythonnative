"""Animation descriptors, easing curves, and the helpers worklets share with Python (RFC 0009).

``with_timing``, ``with_spring``, ``with_decay``, ``with_delay``,
``with_sequence``, and ``with_repeat`` return frozen descriptors. Assign
one to a shared value (``offset.value = pn.with_spring(0)``) in a worklet or
in Python, or await it from Python (``await offset.animate(...)``), and the
renderer core runs it on the UI thread. Inside a worklet the same calls
build the same descriptors in the core.

``interpolate``, ``interpolate_color``, ``clamp``, and ``snap_point`` are
plain functions here and intrinsics in the core, so a worklet computes the
same result in both places.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal, Optional, Sequence, Tuple, TypeVar, Union

__all__ = [
    "Animation",
    "Easing",
    "EasingSpec",
    "Extrapolate",
    "ReduceMotion",
    "Spring",
    "clamp",
    "interpolate",
    "interpolate_color",
    "run_on_python",
    "snap_point",
    "with_decay",
    "with_delay",
    "with_repeat",
    "with_sequence",
    "with_spring",
    "with_timing",
]

T = TypeVar("T")

ReduceMotion = Literal["system", "always", "never"]
"""How an animation treats the system's reduce-motion setting."""

Extrapolate = Union[Literal["extend", "clamp", "identity"], Tuple[str, str]]
"""How ``interpolate`` behaves outside its input range: one mode, or ``(left, right)``."""

# ======================================================================
# Easing
# ======================================================================

_BEZIER_EPSILON = 1e-7


def _bezier_component(t: float, p1: float, p2: float) -> float:
    inv = 1.0 - t
    return 3.0 * inv * inv * t * p1 + 3.0 * inv * t * t * p2 + t * t * t


def _bezier_slope(t: float, p1: float, p2: float) -> float:
    inv = 1.0 - t
    return 3.0 * inv * inv * p1 + 6.0 * inv * t * (p2 - p1) + 3.0 * t * t * (1.0 - p2)


@functools.lru_cache(maxsize=64)
def _bezier_function(x1: float, y1: float, x2: float, y2: float) -> Callable[[float], float]:
    """A ``progress -> eased`` function for a CSS cubic bezier."""

    def solve_t(x: float) -> float:
        t = x
        for _ in range(8):
            error = _bezier_component(t, x1, x2) - x
            if abs(error) < _BEZIER_EPSILON:
                return t
            slope = _bezier_slope(t, x1, x2)
            if abs(slope) < 1e-6:
                break
            t -= error / slope
        lo, hi = 0.0, 1.0
        for _ in range(40):
            t = (lo + hi) / 2.0
            if _bezier_component(t, x1, x2) < x:
                lo = t
            else:
                hi = t
            if hi - lo < _BEZIER_EPSILON:
                break
        return t

    def evaluate(progress: float) -> float:
        if progress <= 0.0:
            return 0.0
        if progress >= 1.0:
            return 1.0
        return _bezier_component(solve_t(progress), y1, y2)

    return evaluate


def _bounce(t: float) -> float:
    """Robert Penner's bounce-out, React Native's ``Easing.bounce``."""
    if t < 1 / 2.75:
        return 7.5625 * t * t
    if t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


_NAMED: Dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease": _bezier_function(0.42, 0.0, 1.0, 1.0),
    "ease_in": _bezier_function(0.42, 0.0, 1.0, 1.0),
    "ease_out": _bezier_function(0.0, 0.0, 0.58, 1.0),
    "ease_in_out": _bezier_function(0.42, 0.0, 0.58, 1.0),
    "quad": lambda t: t * t,
    "cubic": lambda t: t * t * t,
    "bounce": _bounce,
}

EASING_NAMES: Tuple[str, ...] = tuple(_NAMED)
"""The easing names ``with_timing`` accepts."""

_SAMPLES = 64


@dataclass(frozen=True)
class EasingSpec:
    """A serializable easing curve.

    Build one through [`Easing`][pythonnative.motion.Easing]
    (``Easing.ease_in_out``, ``Easing.bezier(...)``, ``Easing.custom(fn)``).
    It crosses to the core as data, and evaluates identically in Python.

    Attributes:
        name: A named curve, ``"bezier"``, or ``"samples"``.
        points: The control points of a bezier, or the samples of a custom curve.
    """

    name: str
    points: Optional[Tuple[float, ...]] = None

    def __post_init__(self) -> None:
        if self.name == "bezier":
            if self.points is None or len(self.points) != 4:
                raise ValueError("Easing.bezier() needs exactly four control-point coordinates")
            x1, _y1, x2, _y2 = self.points
            if not (0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0):
                raise ValueError("Easing.bezier() x control points must lie within [0, 1]")
        elif self.name == "samples":
            if self.points is None or len(self.points) < 2:
                raise ValueError("a sampled easing needs at least two samples")
        elif self.name not in _NAMED:
            raise ValueError(f"Unknown easing {self.name!r}; expected one of {', '.join(EASING_NAMES)}")
        elif self.points is not None:
            raise ValueError(f"Easing {self.name!r} doesn't take control points")

    def evaluate(self, progress: float) -> float:
        """The eased value for ``progress`` in ``[0, 1]``."""
        if self.name == "bezier":
            assert self.points is not None
            return _bezier_function(*self.points)(progress)
        if self.name == "samples":
            assert self.points is not None
            position = min(1.0, max(0.0, progress)) * (len(self.points) - 1)
            index = min(len(self.points) - 2, int(position))
            fraction = position - index
            return self.points[index] + (self.points[index + 1] - self.points[index]) * fraction
        return _NAMED[self.name](progress)

    def __pn_wire__(self) -> Any:
        """The core's form: the name, ``[x1, y1, x2, y2]``, or ``{"samples": [...]}``."""
        if self.name == "bezier":
            return [float(p) for p in self.points or ()]
        if self.name == "samples":
            return {"samples": [float(p) for p in self.points or ()]}
        return self.name

    def __repr__(self) -> str:
        if self.name == "bezier":
            return f"Easing.bezier{self.points}"
        if self.name == "samples":
            return "Easing.custom(...)"
        return f"Easing.{self.name}"


class _EasingNamespace:
    """Named easing curves, ``bezier(...)``, and ``custom(fn)``.

    | Name | Curve |
    | --- | --- |
    | ``linear`` | ``t`` |
    | ``ease`` | ``bezier(0.42, 0, 1, 1)`` |
    | ``ease_in`` | ``bezier(0.42, 0, 1, 1)`` |
    | ``ease_out`` | ``bezier(0, 0, 0.58, 1)`` |
    | ``ease_in_out`` | ``bezier(0.42, 0, 0.58, 1)`` (the default) |
    | ``quad`` | ``t * t`` |
    | ``cubic`` | ``t * t * t`` |
    | ``bounce`` | Penner bounce-out |

    Example:
        ```python
        offset.value = pn.with_timing(1, easing=pn.Easing.bezier(0.2, 0.8, 0.2, 1.0))
        ```
    """

    linear = EasingSpec("linear")
    ease = EasingSpec("ease")
    ease_in = EasingSpec("ease_in")
    ease_out = EasingSpec("ease_out")
    ease_in_out = EasingSpec("ease_in_out")
    quad = EasingSpec("quad")
    cubic = EasingSpec("cubic")
    bounce = EasingSpec("bounce")

    @staticmethod
    def bezier(x1: float, y1: float, x2: float, y2: float) -> EasingSpec:
        """A CSS ``cubic-bezier(x1, y1, x2, y2)`` curve; ``y`` values may overshoot."""
        return EasingSpec("bezier", (float(x1), float(y1), float(x2), float(y2)))

    @staticmethod
    def custom(curve: Callable[[float], float]) -> EasingSpec:
        """Sample a Python curve so the core can interpolate it on the UI thread."""
        return EasingSpec("samples", tuple(float(curve(i / (_SAMPLES - 1))) for i in range(_SAMPLES)))


Easing = _EasingNamespace()


def _easing_wire(easing: Union[EasingSpec, str, None]) -> Any:
    if easing is None:
        return None
    if isinstance(easing, str):
        return EasingSpec(easing).__pn_wire__()
    if isinstance(easing, EasingSpec):
        return easing.__pn_wire__()
    raise TypeError("easing must be an Easing curve or its name; wrap a Python function with Easing.custom()")


# ======================================================================
# Animations
# ======================================================================


class Animation:
    """Base class of the descriptors ``with_*`` return."""

    __slots__ = ()

    def __pn_wire__(self) -> Dict[str, Any]:
        raise NotImplementedError


def _callback_wire(on_finish: Any) -> Any:
    if on_finish is None:
        return None
    from .worklets import closure_wire

    return closure_wire(on_finish)


@dataclass(frozen=True)
class Spring:
    """Spring parameters for ``with_spring`` and spring-driven layout animations.

    Pass ``duration`` (milliseconds) and ``damping_ratio`` for a spring that
    settles in about that time (``damping_ratio=1`` doesn't overshoot), or
    the physical ``damping``, ``stiffness``, and ``mass``.
    """

    damping: float = 10
    stiffness: float = 100
    mass: float = 1
    overshoot_clamping: bool = False
    rest_displacement: float = 0.01
    rest_speed: float = 2
    duration: Optional[float] = None
    damping_ratio: Optional[float] = None

    def __pn_wire__(self) -> Dict[str, Any]:
        return {
            "damping": self.damping,
            "stiffness": self.stiffness,
            "mass": self.mass,
            "overshoot_clamping": self.overshoot_clamping,
            "rest_displacement": self.rest_displacement,
            "rest_speed": self.rest_speed,
            "duration": self.duration,
            "damping_ratio": self.damping_ratio,
        }


@dataclass(frozen=True)
class _Timing(Animation):
    to: Any
    duration: float = 300
    easing: Union[EasingSpec, str, None] = None
    reduce_motion: ReduceMotion = "system"
    on_finish: Optional[Callable[[bool], None]] = None

    def __pn_wire__(self) -> Dict[str, Any]:
        return {
            "__animation__": True,
            "type": "timing",
            "to": self.to,
            "duration": self.duration,
            "easing": _easing_wire(self.easing),
            "reduce_motion": self.reduce_motion,
            "on_finish": _callback_wire(self.on_finish),
        }


@dataclass(frozen=True)
class _Spring(Animation):
    to: Any
    damping: float = 10
    stiffness: float = 100
    mass: float = 1
    velocity: float = 0
    overshoot_clamping: bool = False
    rest_displacement: float = 0.01
    rest_speed: float = 2
    duration: Optional[float] = None
    damping_ratio: Optional[float] = None
    reduce_motion: ReduceMotion = "system"
    on_finish: Optional[Callable[[bool], None]] = None

    def __pn_wire__(self) -> Dict[str, Any]:
        return {
            "__animation__": True,
            "type": "spring",
            "to": self.to,
            "damping": self.damping,
            "stiffness": self.stiffness,
            "mass": self.mass,
            "velocity": self.velocity,
            "overshoot_clamping": self.overshoot_clamping,
            "rest_displacement": self.rest_displacement,
            "rest_speed": self.rest_speed,
            "duration": self.duration,
            "damping_ratio": self.damping_ratio,
            "reduce_motion": self.reduce_motion,
            "on_finish": _callback_wire(self.on_finish),
        }


@dataclass(frozen=True)
class _Decay(Animation):
    velocity: float
    deceleration: float = 0.998
    clamp: Optional[Tuple[float, float]] = None
    rubber_band_factor: float = 0.6
    reduce_motion: ReduceMotion = "system"
    on_finish: Optional[Callable[[bool], None]] = None

    def __pn_wire__(self) -> Dict[str, Any]:
        return {
            "__animation__": True,
            "type": "decay",
            "velocity": self.velocity,
            "deceleration": self.deceleration,
            "clamp": list(self.clamp) if self.clamp is not None else None,
            "rubber_band_factor": self.rubber_band_factor,
            "reduce_motion": self.reduce_motion,
            "on_finish": _callback_wire(self.on_finish),
        }


@dataclass(frozen=True)
class _Delay(Animation):
    delay_ms: float
    animation: Animation
    reduce_motion: ReduceMotion = "system"

    def __pn_wire__(self) -> Dict[str, Any]:
        return {
            "__animation__": True,
            "type": "delay",
            "delay": self.delay_ms,
            "animation": self.animation.__pn_wire__(),
            "reduce_motion": self.reduce_motion,
        }


@dataclass(frozen=True)
class _Sequence(Animation):
    animations: Tuple[Animation, ...]

    def __pn_wire__(self) -> Dict[str, Any]:
        return {"__animation__": True, "type": "sequence", "animations": [a.__pn_wire__() for a in self.animations]}


@dataclass(frozen=True)
class _Repeat(Animation):
    animation: Animation
    times: Optional[int] = None
    reverse: bool = False
    on_finish: Optional[Callable[[bool], None]] = None
    reduce_motion: ReduceMotion = "system"

    def __pn_wire__(self) -> Dict[str, Any]:
        return {
            "__animation__": True,
            "type": "repeat",
            "animation": self.animation.__pn_wire__(),
            "times": self.times,
            "reverse": self.reverse,
            "on_finish": _callback_wire(self.on_finish),
            "reduce_motion": self.reduce_motion,
        }


def with_timing(
    to: T,
    *,
    duration: float = 300,
    easing: Union[EasingSpec, str, None] = None,
    reduce_motion: ReduceMotion = "system",
    on_finish: Optional[Callable[[bool], None]] = None,
) -> T:
    """Animate to ``to`` over ``duration`` milliseconds along ``easing`` (ease-in-out by default).

    ``to`` may be a number or a color. ``on_finish`` is a worklet that
    receives whether the animation finished (``False`` when interrupted).

    The return type is ``to``'s type so ``shared.value = with_timing(1)``
    type-checks; the value is a descriptor the core runs.
    """
    return _Timing(to, duration, easing, reduce_motion, on_finish)  # type: ignore[return-value]


def with_spring(
    to: T,
    *,
    damping: float = 10,
    stiffness: float = 100,
    mass: float = 1,
    velocity: float = 0,
    overshoot_clamping: bool = False,
    rest_displacement: float = 0.01,
    rest_speed: float = 2,
    duration: Optional[float] = None,
    damping_ratio: Optional[float] = None,
    reduce_motion: ReduceMotion = "system",
    on_finish: Optional[Callable[[bool], None]] = None,
) -> T:
    """Spring to ``to``.

    ``velocity`` is in units per second (a gesture's ``velocity_x`` carries
    over directly). Give ``duration`` (milliseconds) with ``damping_ratio``
    for a spring that settles in about that time, or the physical
    ``damping``, ``stiffness``, and ``mass``. A spring that's still moving
    when another animation replaces it hands over its velocity.
    """
    return _Spring(  # type: ignore[return-value]
        to,
        damping,
        stiffness,
        mass,
        velocity,
        overshoot_clamping,
        rest_displacement,
        rest_speed,
        duration,
        damping_ratio,
        reduce_motion,
        on_finish,
    )


def with_decay(
    *,
    velocity: float,
    deceleration: float = 0.998,
    clamp: Optional[Tuple[float, float]] = None,
    rubber_band_factor: float = 0.6,
    reduce_motion: ReduceMotion = "system",
    on_finish: Optional[Callable[[bool], None]] = None,
) -> Any:
    """Coast from the current value at ``velocity`` (units per second), slowing by ``deceleration`` per millisecond.

    With ``clamp=(lower, upper)``, the value springs back from a bound it
    crosses when ``rubber_band_factor`` is above zero, or stops at it.
    """
    return _Decay(velocity, deceleration, clamp, rubber_band_factor, reduce_motion, on_finish)


def with_delay(delay_ms: float, animation: T, *, reduce_motion: ReduceMotion = "system") -> T:
    """Start ``animation`` after ``delay_ms`` milliseconds.

    Under reduced motion the delay is skipped; ``reduce_motion="never"``
    keeps it. The inner animation follows its own ``reduce_motion``.
    """
    return _Delay(delay_ms, animation, reduce_motion)  # type: ignore[arg-type,return-value]


def with_sequence(*animations: Any) -> Any:
    """Run animations one after another, each from where the last ended."""
    return _Sequence(tuple(animations))


def with_repeat(
    animation: T,
    *,
    times: Optional[int] = None,
    reverse: bool = False,
    on_finish: Optional[Callable[[bool], None]] = None,
    reduce_motion: ReduceMotion = "system",
) -> T:
    """Repeat ``animation`` ``times`` times, or forever when ``times`` is ``None``.

    With ``reverse``, every other run heads back to where the first began.
    Under reduced motion, a finite repeat jumps to where it would end and an
    endless one stays put; ``reduce_motion="never"`` keeps it running.

    Raises:
        ValueError: If ``times`` is less than 1.
    """
    if times is not None and times < 1:
        raise ValueError(f"with_repeat() needs times of at least 1, or None to repeat forever, not {times!r}")
    return _Repeat(animation, times, reverse, on_finish, reduce_motion)  # type: ignore[arg-type,return-value]


# ======================================================================
# Helpers
# ======================================================================


def interpolate(
    x: float,
    input_range: Sequence[float],
    output_range: Sequence[float],
    extrapolate: Extrapolate = "extend",
) -> float:
    """Map ``x`` from ``input_range`` onto ``output_range`` piecewise linearly.

    Outside the input range, ``"extend"`` continues the nearest segment,
    ``"clamp"`` holds the end value, and ``"identity"`` returns ``x``.
    Pass ``(left, right)`` to choose each side separately.
    """
    inputs = [float(v) for v in input_range]
    outputs = [float(v) for v in output_range]
    if len(inputs) < 2 or len(inputs) != len(outputs):
        raise ValueError("interpolate() needs input and output ranges of the same length, at least 2")
    left, right = (extrapolate, extrapolate) if isinstance(extrapolate, str) else extrapolate
    for mode in (left, right):
        if mode not in ("extend", "clamp", "identity"):
            raise ValueError("extrapolate must be 'extend', 'clamp', or 'identity'")
    x = float(x)
    if x < inputs[0]:
        if left == "identity":
            return x
        if left == "clamp":
            return outputs[0]
    elif x > inputs[-1]:
        if right == "identity":
            return x
        if right == "clamp":
            return outputs[-1]
    index = 0
    while index < len(inputs) - 2 and x >= inputs[index + 1]:
        index += 1
    span = inputs[index + 1] - inputs[index]
    t = 0.0 if span == 0 else (x - inputs[index]) / span
    return outputs[index] + (outputs[index + 1] - outputs[index]) * t


_NAMED_COLORS = {
    "black": 0x000000,
    "white": 0xFFFFFF,
    "red": 0xFF0000,
    "green": 0x008000,
    "blue": 0x0000FF,
    "yellow": 0xFFFF00,
    "orange": 0xFFA500,
    "purple": 0x800080,
    "pink": 0xFFC0CB,
    "gray": 0x808080,
    "grey": 0x808080,
    "cyan": 0x00FFFF,
    "magenta": 0xFF00FF,
    "lime": 0x00FF00,
    "navy": 0x000080,
    "teal": 0x008080,
    "silver": 0xC0C0C0,
    "maroon": 0x800000,
    "olive": 0x808000,
}


def parse_color(text: str) -> Optional[Tuple[float, float, float, float]]:
    """``(r, g, b, a)`` for ``#RGB``, ``#RRGGBB``, ``#AARRGGBB``, ``rgb()``, ``rgba()``, a basic name, or ``None``."""
    value = text.strip().lower()
    if value == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if value in _NAMED_COLORS:
        rgb = _NAMED_COLORS[value]
        return (float(rgb >> 16 & 0xFF), float(rgb >> 8 & 0xFF), float(rgb & 0xFF), 1.0)
    if value.startswith("#"):
        digits = value[1:]
        try:
            int(digits, 16)
        except ValueError:
            return None
        if len(digits) == 3:
            return (int(digits[0], 16) * 17.0, int(digits[1], 16) * 17.0, int(digits[2], 16) * 17.0, 1.0)
        if len(digits) == 6:
            return (float(int(digits[0:2], 16)), float(int(digits[2:4], 16)), float(int(digits[4:6], 16)), 1.0)
        if len(digits) == 8:
            return (
                float(int(digits[2:4], 16)),
                float(int(digits[4:6], 16)),
                float(int(digits[6:8], 16)),
                int(digits[0:2], 16) / 255.0,
            )
        return None
    if value.startswith(("rgb(", "rgba(")) and value.endswith(")"):
        parts = [p.strip() for p in value[value.index("(") + 1 : -1].split(",")]
        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            return None
        if len(numbers) == 3:
            numbers.append(1.0)
        return (numbers[0], numbers[1], numbers[2], numbers[3]) if len(numbers) == 4 else None
    return None


def format_color(rgba: Sequence[float]) -> str:
    """``#AARRGGBB``, the form every renderer reads."""

    def byte(v: float) -> int:
        return int(math.floor(min(255.0, max(0.0, v)) + 0.5))

    r, g, b, a = rgba
    return f"#{byte(a * 255):02X}{byte(r):02X}{byte(g):02X}{byte(b):02X}"


def interpolate_color(x: float, input_range: Sequence[float], colors: Sequence[str]) -> str:
    """Blend between ``colors`` as ``x`` moves through ``input_range`` (clamped at the ends)."""
    inputs = [float(v) for v in input_range]
    if len(inputs) < 2 or len(inputs) != len(colors):
        raise ValueError("interpolate_color() needs an input range and as many colors, at least 2")
    x = min(inputs[-1], max(inputs[0], float(x)))
    index = 0
    while index < len(inputs) - 2 and x >= inputs[index + 1]:
        index += 1
    span = inputs[index + 1] - inputs[index]
    t = 0.0 if span == 0 else (x - inputs[index]) / span
    start, end = parse_color(colors[index]), parse_color(colors[index + 1])
    if start is None or end is None:
        raise ValueError(f"interpolate_color() can't read color {colors[index]!r} or {colors[index + 1]!r}")
    return format_color([a + (b - a) * t for a, b in zip(start, end)])


def clamp(x: float, lower: float, upper: float) -> float:
    """``x`` limited to ``[lower, upper]``."""
    return lower if x < lower else upper if x > upper else x


def snap_point(value: float, velocity: float, points: Sequence[float]) -> float:
    """The point a release at ``value`` moving at ``velocity`` (per second) lands nearest.

    The release is projected a fifth of a second ahead, so a flick carries
    past the nearest point, the way a sheet or carousel settles.
    """
    if not points:
        raise ValueError("snap_point() needs at least one point")
    projected = value + 0.2 * velocity
    return min(points, key=lambda point: abs(point - projected))


def run_on_python(callback: Callable[..., Any], *args: Any) -> None:
    """Call ``callback(*args)`` on the Python thread.

    In a worklet, this queues the call from the UI thread; the callback
    must be a name the worklet captures. Called from Python, it calls the
    callback directly.
    """
    callback(*args)
