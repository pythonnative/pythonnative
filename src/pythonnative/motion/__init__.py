"""Motion: worklets, shared values, animations, layout animations, and shared elements (RFC 0009).

Interaction logic that has to keep up with a finger runs on the UI thread,
inside the renderer core, as a **worklet**: an ordinary Python function in
a subset the core compiles, verifies, and interprets. Python never sees the
per-frame work, so a drag keeps tracking while the Python thread is busy.

```python
import pythonnative as pn
from pythonnative import gestures


@pn.component
def Card() -> pn.Node:
    x = pn.use_shared_value(0.0)

    @pn.worklet
    def drag(event: gestures.GestureEvent) -> None:
        x.value = event.translation_x

    @pn.worklet
    def release(event: gestures.GestureEvent) -> None:
        x.value = pn.with_spring(0, velocity=event.velocity_x)

    moved = pn.use_animated_style(lambda: {"transform": [{"translate_x": x.value}]})
    return pn.View(style=[CARD, moved], gestures=[gestures.Pan(on_change=drag, on_end=release)])
```

The everyday names are exported from ``pythonnative`` itself; this module
also holds the layout animation presets, ``Keyframes``,
``SharedTransition``, ``LayoutAnimationConfig``, and ``WorkletError``.
"""

from __future__ import annotations

from ..style import AnimatedStyle
from .animations import (
    Animation,
    Easing,
    EasingSpec,
    Extrapolate,
    ReduceMotion,
    Spring,
    clamp,
    interpolate,
    interpolate_color,
    run_on_python,
    snap_point,
    with_decay,
    with_delay,
    with_repeat,
    with_sequence,
    with_spring,
    with_timing,
)
from .compiler import WorkletError
from .hooks import (
    FrameInfo,
    use_animated_reaction,
    use_animated_style,
    use_derived_value,
    use_frame_callback,
    use_shared_value,
)
from .layout import (
    Edge,
    FadeIn,
    FadeOut,
    FadingTransition,
    Keyframes,
    LayoutAnimation,
    LayoutAnimationConfig,
    LayoutValues,
    LinearTransition,
    SlideIn,
    SlideOut,
    ZoomIn,
    ZoomOut,
)
from .shared import SharedValue
from .transitions import SharedTransition
from .worklets import is_worklet, worklet

__all__ = [
    "AnimatedStyle",
    "Animation",
    "Easing",
    "EasingSpec",
    "Edge",
    "Extrapolate",
    "FadeIn",
    "FadeOut",
    "FadingTransition",
    "FrameInfo",
    "Keyframes",
    "LayoutAnimation",
    "LayoutAnimationConfig",
    "LayoutValues",
    "LinearTransition",
    "ReduceMotion",
    "SharedTransition",
    "SharedValue",
    "SlideIn",
    "SlideOut",
    "Spring",
    "WorkletError",
    "ZoomIn",
    "ZoomOut",
    "clamp",
    "interpolate",
    "interpolate_color",
    "is_worklet",
    "run_on_python",
    "snap_point",
    "use_animated_reaction",
    "use_animated_style",
    "use_derived_value",
    "use_frame_callback",
    "use_shared_value",
    "with_decay",
    "with_delay",
    "with_repeat",
    "with_sequence",
    "with_spring",
    "with_timing",
    "worklet",
]
