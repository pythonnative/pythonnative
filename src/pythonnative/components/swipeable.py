"""``Swipeable``: a row that slides aside to reveal actions (RFC 0009).

The drag, the open-or-close decision, and the spring run as worklets on the
UI thread; Python hears about the result through ``run_on_python``.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Optional, cast

from ..component import component
from ..element import Node
from ..hooks import Ref, use_imperative_handle, use_ref
from ..motion.animations import run_on_python, with_spring
from ..motion.hooks import use_animated_style, use_shared_value
from ..motion.worklets import worklet
from ..style import Style, StyleProp, resolve_style
from ..theme import use_theme
from .layout import View

__all__ = ["Side", "Swipeable", "SwipeableHandle"]

Side = Literal["left", "right"]

_DAMPING = 30.0
_STIFFNESS = 320.0


class SwipeableHandle:
    """What a ``Swipeable``'s ``ref`` holds."""

    def __init__(self, move: Callable[[str], None]) -> None:
        self._move = move

    def open_left(self) -> None:
        """Reveal the left actions."""
        self._move("left")

    def open_right(self) -> None:
        """Reveal the right actions."""
        self._move("right")

    def close(self) -> None:
        """Slide the row back."""
        self._move("")


@component
def Swipeable(
    child: Node,
    *,
    left_actions: Optional[Node] = None,
    right_actions: Optional[Node] = None,
    left_width: float = 80,
    right_width: float = 80,
    threshold: Optional[float] = None,
    friction: float = 1.0,
    overshoot: bool = False,
    on_open: Optional[Callable[[Side], Any]] = None,
    on_close: Optional[Callable[[], Any]] = None,
    style: StyleProp = None,
    ref: Optional[Ref[Any]] = None,
) -> Node:
    """Slide ``child`` aside to reveal ``left_actions`` or ``right_actions`` behind it.

    The pan activates only on horizontal movement and fails on vertical
    movement, so a ``Swipeable`` row works inside a vertical list. On
    release, the row opens when it's past ``threshold`` (half the actions'
    width by default), counting where the release velocity would carry it,
    and springs closed otherwise.

    Example:
        ```python
        pn.Swipeable(
            EntryRow(entry),
            right_actions=pn.Pressable(pn.Icon("trash-2"), on_press=lambda: delete(entry.id)),
            on_open=lambda side: haptics(),
        )
        ```

    Args:
        child: The row's content.
        left_actions: Revealed when the row slides right.
        right_actions: Revealed when the row slides left.
        left_width: Width of the left actions, in points.
        right_width: Width of the right actions, in points.
        threshold: How far the row must travel to open; half the actions'
            width by default.
        friction: Divides the finger's travel; above 1 the row lags behind.
        overshoot: Let the row travel past the actions' width while dragging.
        on_open: Called with ``"left"`` or ``"right"`` when the row settles open.
        on_close: Called when the row settles closed.
        style: Style for the outer container.
        ref: Receives a [`SwipeableHandle`][pythonnative.SwipeableHandle].
    """
    theme = use_theme()
    left = float(left_width) if left_actions is not None else 0.0
    right = float(right_width) if right_actions is not None else 0.0
    open_left = threshold if threshold is not None else left / 2
    open_right = threshold if threshold is not None else right / 2
    drag_factor = 1.0 / max(friction, 0.01)
    x = use_shared_value(0.0)
    start = use_shared_value(0.0)
    on_open_ref = use_ref(on_open)
    on_close_ref = use_ref(on_close)
    on_open_ref.current = on_open
    on_close_ref.current = on_close

    def settled(side: str) -> None:
        if side and on_open_ref.current is not None:
            on_open_ref.current(side)  # type: ignore[arg-type]
        elif not side and on_close_ref.current is not None:
            on_close_ref.current()

    def move(side: str) -> None:
        target = left if side == "left" else -right if side == "right" else 0.0

        # Report the result once the row gets there, as a drag does.
        @worklet
        def landed(finished: bool) -> None:
            if finished:
                run_on_python(settled, side)

        x.value = with_spring(target, damping=_DAMPING, stiffness=_STIFFNESS, on_finish=landed)

    use_imperative_handle(ref, lambda: SwipeableHandle(move), [left, right])

    @worklet
    def begin(event: Any) -> None:
        start.value = x.value

    @worklet
    def drag(event: Any) -> None:
        position = start.value + event.translation_x * drag_factor
        if not overshoot:
            position = max(-right, min(left, position))
        else:
            position = max(-right * 1.5, min(left * 1.5, position))
        x.value = position

    @worklet
    def release(event: Any) -> None:
        projected = x.value + 0.2 * event.velocity_x
        side = ""
        target = 0.0
        if left > 0 and projected > open_left:
            side = "left"
            target = left
        elif right > 0 and projected < -open_right:
            side = "right"
            target = -right
        x.value = with_spring(target, velocity=event.velocity_x, damping=_DAMPING, stiffness=_STIFFNESS)
        run_on_python(settled, side)

    content = use_animated_style(lambda: {"transform": [{"translate_x": x.value}]})

    from .. import gestures

    pan = gestures.Pan(
        active_offset_x=(-10, 10), fail_offset_y=(-10, 10), on_begin=begin, on_change=drag, on_end=release
    )
    behind = {"position": "absolute", "top": 0, "bottom": 0, "flex_direction": "row", "align_items": "stretch"}
    return View(
        View(left_actions, style=cast(Style, {**behind, "left": 0, "width": left})) if left_actions else None,
        View(right_actions, style=cast(Style, {**behind, "right": 0, "width": right})) if right_actions else None,
        # The row covers its actions, so it takes the theme's background.
        View(child, style=[{"background_color": theme.colors.background}, content], gestures=[pan]),
        style=cast(Style, {"overflow": "hidden", **resolve_style(style)}),
    )
