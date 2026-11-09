"""``BottomSheet``: a sheet with detents that follows the finger (RFC 0009).

Built only from the public Motion API: the drag, the snap decision, and the
spring all run as worklets on the UI thread, so the sheet keeps up with the
finger while Python is busy, and Python hears about the settled detent
through ``run_on_python``.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple, Union, cast

from ..component import component
from ..element import Element, Node
from ..hooks import Ref, use_effect, use_imperative_handle, use_ref, use_state, use_window_dimensions
from ..motion.animations import clamp, interpolate, run_on_python, snap_point, with_spring
from ..motion.hooks import use_animated_style, use_shared_value
from ..motion.worklets import worklet
from ..style import Style, StyleProp, resolve_style
from ..theme import use_theme
from .layout import View
from .overlays import Portal
from .pressable import Pressable

__all__ = ["BottomSheet", "BottomSheetHandle", "SnapPoint"]

SnapPoint = Union[float, str]
"""A detent: a height in points, or a percentage of the window (``"50%"``)."""

_SPRING_DAMPING = 28.0
_SPRING_STIFFNESS = 260.0
_RUBBER_BAND = 0.35


class BottomSheetHandle:
    """What a ``BottomSheet``'s ``ref`` holds."""

    def __init__(self, snap_to: Callable[[int], None], count: int) -> None:
        self._snap_to = snap_to
        self._count = count

    def snap_to(self, index: int) -> None:
        """Animate to detent ``index`` (``-1`` closes the sheet)."""
        if not -1 <= index < self._count:
            raise IndexError(f"BottomSheet has detents 0 to {self._count - 1} (or -1 to close)")
        self._snap_to(index)

    def expand(self) -> None:
        """Animate to the highest detent."""
        self._snap_to(self._count - 1)

    def collapse(self) -> None:
        """Animate to the lowest detent."""
        self._snap_to(0)

    def close(self) -> None:
        """Animate off screen."""
        self._snap_to(-1)


def _heights(snap_points: Sequence[SnapPoint], window_height: float) -> List[float]:
    heights = []
    for point in snap_points:
        if isinstance(point, str):
            if not point.endswith("%"):
                raise ValueError(f"snap point {point!r} must be a number of points or a percentage like '50%'")
            heights.append(window_height * float(point[:-1]) / 100.0)
        else:
            heights.append(float(point))
    if not heights:
        raise ValueError("BottomSheet needs at least one snap point")
    # Points and percentages compare differently on different windows, so
    # detents are ordered by the height they come to here.
    return sorted(heights)


@component
def BottomSheet(
    *children: Node,
    snap_points: Sequence[SnapPoint] = ("50%",),
    index: int = 0,
    on_change: Optional[Callable[[int], Any]] = None,
    on_close: Optional[Callable[[], Any]] = None,
    backdrop: bool = True,
    close_on_drag_down: bool = True,
    handle: bool = True,
    style: StyleProp = None,
    ref: Optional[Ref[Any]] = None,
) -> Node:
    """A sheet that rises from the bottom of the window and snaps to detents.

    The sheet presents in a [`Portal`][pythonnative.Portal] above the screen.
    Dragging it follows the finger; on release it settles on the detent the
    release projects to (``snap_point``), rubber-banding past the highest one
    and closing below the lowest when ``close_on_drag_down``. Content that
    scrolls scrolls only at the highest detent; drag the sheet by its handle.

    Example:
        ```python
        sheet = pn.use_ref()
        pn.BottomSheet(
            FilterPanel(),
            snap_points=(240, "50%", "90%"),
            on_change=set_detent,
            ref=sheet,  # sheet.current.snap_to(2), .close()
        )
        ```

    Args:
        *children: The sheet's content.
        snap_points: Detents, in points or as a percentage of the window's
            height. They're ordered by height on this window, and indexes
            count from the lowest.
        index: The detent to show first; ``-1`` starts closed. Changing it
            animates to the new detent.
        on_change: Called with the settled detent's index after a drag or
            a ``snap_to``.
        on_close: Called when the sheet settles closed.
        backdrop: Dim the screen behind the sheet; tapping it closes the
            sheet (or collapses it when ``close_on_drag_down`` is off).
        close_on_drag_down: Whether dragging below the lowest detent closes it.
        handle: Show a grab handle at the top.
        style: Style for the sheet's surface.
        ref: Receives a [`BottomSheetHandle`][pythonnative.BottomSheetHandle].
    """
    theme = use_theme()
    window = use_window_dimensions()
    heights = _heights(snap_points, window.height)
    tallest = heights[-1]
    # A detent's offset is how far the sheet sits below its fully open position.
    offsets: Tuple[float, ...] = tuple(tallest - height for height in heights)
    closed = tallest + 48.0  # far enough down that the shadow is hidden too
    stops = offsets + ((closed,) if close_on_drag_down else ())
    lowest = offsets[0]

    def offset_for(position: int) -> float:
        return closed if position < 0 else offsets[min(position, len(offsets) - 1)]

    current, set_current = use_state(index)
    translate = use_shared_value(offset_for(index))
    start = use_shared_value(0.0)
    on_change_ref = use_ref(on_change)
    on_close_ref = use_ref(on_close)
    on_change_ref.current = on_change
    on_close_ref.current = on_close

    def settled(position: int) -> None:
        set_current(position)
        if position < 0:
            if on_close_ref.current is not None:
                on_close_ref.current()
        elif on_change_ref.current is not None:
            on_change_ref.current(position)

    def snap_to(position: int) -> None:
        set_current(position)

        # Report the detent once the sheet gets there, as a drag does.
        @worklet
        def landed(finished: bool) -> None:
            if finished:
                run_on_python(settled, position)

        translate.value = with_spring(
            offset_for(position), damping=_SPRING_DAMPING, stiffness=_SPRING_STIFFNESS, on_finish=landed
        )

    def follow_index() -> None:
        if index != current:
            snap_to(index)

    use_effect(follow_index, [index])  # pn: ignore[PN103] follows the controlled index only

    def follow_window() -> None:
        # The window's height (and so every detent's offset) can change after
        # the first render, as safe areas settle or the device rotates.
        translate.value = offset_for(current)

    use_effect(follow_window, [offsets, closed])  # pn: ignore[PN103] re-places the sheet when the detents move
    use_imperative_handle(ref, lambda: BottomSheetHandle(snap_to, len(offsets)), [offsets, closed])

    @worklet
    def begin(event: Any) -> None:
        start.value = translate.value

    @worklet
    def drag(event: Any) -> None:
        position = start.value + event.translation_y
        if position < 0:
            position = position * _RUBBER_BAND
        translate.value = position

    @worklet
    def release(event: Any) -> None:
        target = snap_point(translate.value, event.velocity_y, stops)
        translate.value = with_spring(
            target, velocity=event.velocity_y, damping=_SPRING_DAMPING, stiffness=_SPRING_STIFFNESS
        )
        position = -1
        for i in range(len(offsets)):
            if offsets[i] == target:
                position = i
        run_on_python(settled, position)

    sheet_motion = use_animated_style(lambda: {"transform": [{"translate_y": translate.value}]})
    dim = use_animated_style(
        lambda: {"opacity": interpolate(clamp(translate.value, 0, closed), (lowest, closed), (1, 0), "clamp")}
    )

    from .. import gestures

    pan = gestures.Pan(active_offset_y=(-6, 6), on_begin=begin, on_change=drag, on_end=release)
    surface: dict[str, Any] = {
        "position": "absolute",
        "left": 0,
        "right": 0,
        "bottom": 0,
        "height": tallest,
        "background_color": theme.colors.surface,
        "border_top_left_radius": 16,
        "border_top_right_radius": 16,
        "shadow_color": "#000000",
        "shadow_opacity": 0.15,
        "shadow_radius": 12,
        "elevation": 12,
        **resolve_style(style),
    }
    grab: Optional[Element] = (
        View(
            View(style={"width": 36, "height": 5, "border_radius": 2.5, "background_color": theme.colors.border}),
            style={"align_items": "center", "padding_vertical": 8},
            gestures=[pan],
            accessibility_role="adjustable",
            accessibility_label="Sheet handle",
        )
        if handle
        else None
    )
    shade = (
        Pressable(
            on_press=lambda: snap_to(-1 if close_on_drag_down else 0),
            accessibility_label="Close sheet",
            style=[
                {
                    "position": "absolute",
                    "top": 0,
                    "left": 0,
                    "right": 0,
                    "bottom": 0,
                    "background_color": "#66000000",
                    "pointer_events": "none" if current < 0 else "auto",
                },
                dim,
            ],
        )
        if backdrop
        else None
    )
    return Portal(
        View(
            shade,
            View(
                grab,
                View(*children, style={"flex_grow": 1}),
                style=[cast(Style, surface), sheet_motion],
                gestures=None if handle else [pan],
            ),
            style={"position": "absolute", "top": 0, "left": 0, "right": 0, "bottom": 0, "pointer_events": "box_none"},
        )
    )
