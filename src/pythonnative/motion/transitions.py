"""Shared-element transitions between stack screens (RFC 0009).

Give a view on the screen you push from and a view on the screen you push
to the same ``shared_tag``. During the push (and the pop back), the
platform lifts the destination view into a transition overlay at the
source's place on screen, hides the source, and flies the destination to
where it belongs while the screens slide, blending corner radius,
background color, and opacity. On iOS the back swipe drives the flight
interactively.

```python
# The journal row
pn.Image(photo, shared_tag=f"photo-{entry.id}", style=styles.thumbnail)

# The entry screen
pn.Image(photo, shared_tag=f"photo-{entry.id}", style=styles.hero,
         shared_transition=SharedTransition(spring=pn.Spring(damping_ratio=0.9, duration=450)))
```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union

from .animations import EasingSpec, Spring, _easing_wire

__all__ = ["SharedTransition"]

_DEFAULT_PROPS = ("border_radius", "background_color", "opacity")


@dataclass(frozen=True)
class SharedTransition:
    """How a shared element flies between screens.

    Set it on the destination view's ``shared_transition`` (or the
    source's). Without one, the flight matches the platform's push.

    Attributes:
        duration: Milliseconds, for a timed flight.
        easing: The timed flight's curve (ease-in-out by default).
        spring: A spring instead of a timed flight.
        props: Paint properties that blend from the source to the destination.
    """

    duration: Optional[float] = None
    easing: Union[EasingSpec, str, None] = None
    spring: Optional[Spring] = None
    props: Tuple[str, ...] = _DEFAULT_PROPS

    def __pn_wire__(self) -> Dict[str, Any]:
        wire: Dict[str, Any] = {"props": list(self.props)}
        if self.duration is not None:
            wire["duration"] = self.duration
        if self.easing is not None:
            wire["easing"] = _easing_wire(self.easing)
        if self.spring is not None:
            wire["spring"] = self.spring.__pn_wire__()
        return wire
