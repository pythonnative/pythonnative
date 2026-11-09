"""Layout animations: views entering, exiting, and moving (RFC 0009).

Every view-like component takes ``entering=``, ``exiting=``, and
``layout=``:

- ``entering`` runs when the view is created. Inside a subtree created in
  the same commit, only the outermost entering animation runs, and views
  created along with a list row don't animate, so scrolling never
  triggers them.
- ``exiting`` runs when the view is removed. The component unmounts at
  once; the renderer holds the native view, animates it out, and then
  destroys it with its subtree. Only the outermost removed view animates.
- ``layout`` animates the view from its old frame to its new one when a
  commit moves or resizes it.

```python
from pythonnative.motion import FadeIn, FadeOut, LinearTransition

pn.View(
    *rows,
    entering=FadeIn(duration=200),
    exiting=FadeOut(duration=150),
    layout=LinearTransition(spring=pn.Spring(damping_ratio=0.8, duration=350)),
)
```

``FlatList`` and ``SectionList`` animate their rows natively with
``item_entering``, ``item_exiting``, and ``item_layout``, which take the
presets here (not keyframes or custom worklets).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Literal, Mapping, Optional, Union

from ..element import Element, Node
from ..style import Style, StyleProp
from .animations import EasingSpec, ReduceMotion, Spring, _easing_wire

__all__ = [
    "Edge",
    "FadeIn",
    "FadeOut",
    "FadingTransition",
    "Keyframes",
    "LayoutAnimation",
    "LayoutAnimationConfig",
    "LayoutValues",
    "LinearTransition",
    "SlideIn",
    "SlideOut",
    "ZoomIn",
    "ZoomOut",
]

Edge = Literal["left", "right", "top", "bottom"]


@dataclass(frozen=True)
class LayoutValues:
    """What a custom layout animation worklet receives.

    ``target_*`` is where the view ends (entering and layout), ``current_*``
    where it is (exiting and layout), and ``window_*`` the window's size.
    """

    target_x: float = 0
    target_y: float = 0
    target_width: float = 0
    target_height: float = 0
    current_x: float = 0
    current_y: float = 0
    current_width: float = 0
    current_height: float = 0
    window_width: float = 0
    window_height: float = 0


@dataclass(frozen=True)
class _Preset:
    duration: float = 300
    delay: float = 0
    easing: Union[EasingSpec, str, None] = None
    spring: Optional[Spring] = None
    reduce_motion: ReduceMotion = "system"

    kind = ""

    def __pn_wire__(self) -> Dict[str, Any]:
        wire: Dict[str, Any] = {
            "type": self.kind,
            "duration": self.duration,
            "delay": self.delay,
            "easing": _easing_wire(self.easing),
            "reduce_motion": self.reduce_motion,
        }
        if self.spring is not None:
            wire["spring"] = self.spring.__pn_wire__()
        return wire


@dataclass(frozen=True)
class FadeIn(_Preset):
    """Fade from transparent to the view's opacity."""

    kind = "fade_in"


@dataclass(frozen=True)
class FadeOut(_Preset):
    """Fade to transparent."""

    kind = "fade_out"


@dataclass(frozen=True)
class ZoomIn(_Preset):
    """Grow from nothing to full size."""

    kind = "zoom_in"


@dataclass(frozen=True)
class ZoomOut(_Preset):
    """Shrink to nothing."""

    kind = "zoom_out"


@dataclass(frozen=True)
class SlideIn(_Preset):
    """Slide in from beyond the window's ``edge``."""

    edge: Edge = "right"
    kind = "slide_in"

    def __pn_wire__(self) -> Dict[str, Any]:
        return {**super().__pn_wire__(), "edge": self.edge}


@dataclass(frozen=True)
class SlideOut(_Preset):
    """Slide out past the window's ``edge``."""

    edge: Edge = "right"
    kind = "slide_out"

    def __pn_wire__(self) -> Dict[str, Any]:
        return {**super().__pn_wire__(), "edge": self.edge}


@dataclass(frozen=True)
class LinearTransition(_Preset):
    """Move and resize from the old frame to the new one."""

    kind = "linear"


@dataclass(frozen=True)
class FadingTransition(_Preset):
    """Fade out at the old frame, then fade in at the new one."""

    kind = "fading"


@dataclass(frozen=True)
class Keyframes:
    """Animate through styles at points from 0 to 1 of ``duration``.

    Each key interpolates between the keyframes that set it. Numbers and
    colors blend, and ``transform`` lists blend entry by entry when their
    shapes match.

    Example:
        ```python
        Keyframes(
            {
                0.0: {"opacity": 0, "transform": [{"scale": 0.8}]},
                0.6: {"opacity": 1, "transform": [{"scale": 1.05}]},
                1.0: {"transform": [{"scale": 1.0}]},
            },
            duration=400,
        )
        ```

    Attributes:
        frames: Style at each point of progress.
        duration: Total milliseconds.
        delay: Milliseconds before it starts.
        easings: The curve leading into a keyframe, by its progress point.
    """

    frames: Mapping[float, Style]
    duration: float = 300
    delay: float = 0
    easings: Mapping[float, Union[EasingSpec, str]] = field(default_factory=dict)
    reduce_motion: ReduceMotion = "system"

    def __post_init__(self) -> None:
        if len(self.frames) < 2:
            raise ValueError("Keyframes needs at least two keyframes")
        for point in self.frames:
            if not 0.0 <= float(point) <= 1.0:
                raise ValueError("keyframe points run from 0 to 1")

    def __pn_wire__(self) -> Dict[str, Any]:
        return {
            "type": "keyframes",
            "duration": self.duration,
            "delay": self.delay,
            "reduce_motion": self.reduce_motion,
            "frames": [
                [float(point), dict(style), _easing_wire(self.easings.get(point))]
                for point, style in sorted(self.frames.items())
            ],
        }


LayoutAnimation = Union[
    FadeIn,
    FadeOut,
    ZoomIn,
    ZoomOut,
    SlideIn,
    SlideOut,
    LinearTransition,
    FadingTransition,
    Keyframes,
    Callable[[LayoutValues], Mapping[str, Any]],
]
"""What ``entering``, ``exiting``, and ``layout`` accept.

A custom worklet receives [`LayoutValues`][pythonnative.motion.LayoutValues]
and returns ``{"initial": {...}, "animate": {...}}``: the starting style,
and an animation or value per key. Frame keys are ``x``, ``y``, ``width``,
and ``height``.
"""


def LayoutAnimationConfig(
    *children: Node,
    skip_entering: bool = False,
    skip_exiting: bool = False,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Turn off layout animations for a subtree.

    ``skip_entering`` skips the entering animations of views mounted along
    with this one, such as a list's first rows. ``skip_exiting`` removes
    views inside it at once instead of animating them out. It renders a
    ``View`` that takes ``style``.
    """
    from ..components._base import _make_element

    return _make_element(
        "View",
        *children,
        style=style,
        key=key,
        skip_entering=skip_entering or None,
        skip_exiting=skip_exiting or None,
    )
