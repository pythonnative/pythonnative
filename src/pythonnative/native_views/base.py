"""Shared base classes and utilities for native-view handlers.

Provides the [`ViewHandler`][pythonnative.native_views.base.ViewHandler]
protocol implemented by Android and iOS handlers, plus the
[`parse_color_int`][pythonnative.native_views.base.parse_color_int]
helper shared across platforms.

Layout itself is *not* a handler responsibility. The pure-Python flex
engine in ``pythonnative.layout`` owns sizing and positioning;
handlers receive computed frames via
[`set_frame`][pythonnative.native_views.base.ViewHandler.set_frame] and
optionally expose an intrinsic-size hook via
[`measure_intrinsic`][pythonnative.native_views.base.ViewHandler.measure_intrinsic]
for content-sized leaves (text, buttons, images).
"""

import math
from typing import Any, Dict, Tuple, Union


class ViewHandler:
    """Protocol implemented by every native-view handler.

    A `ViewHandler` knows how to create, update, and re-parent native
    views of one element type. The reconciler dispatches through the
    [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry];
    handlers never need to know about `Element` or `VNode`.

    Subclasses must override [`create`][pythonnative.native_views.base.ViewHandler.create]
    and [`update`][pythonnative.native_views.base.ViewHandler.update].
    Container handlers override the child-management methods; leaf
    handlers can leave them as no-ops. Handlers whose intrinsic size
    depends on content (text, buttons, images) override
    [`measure_intrinsic`][pythonnative.native_views.base.ViewHandler.measure_intrinsic].
    """

    def create(self, props: Dict[str, Any]) -> Any:
        """Create a fresh native view and apply initial *visual* props.

        Layout-related props (``width``, ``height``, ``flex``, ``padding``,
        etc.) are consumed by the layout engine and applied via
        [`set_frame`][pythonnative.native_views.base.ViewHandler.set_frame],
        so handlers should ignore them here.

        Args:
            props: Initial props dict.

        Returns:
            The platform-native view object.

        Raises:
            NotImplementedError: Subclasses must override.
        """
        raise NotImplementedError

    def update(self, native_view: Any, changed_props: Dict[str, Any]) -> None:
        """Apply only the *visual* props that changed since the last render.

        Args:
            native_view: The platform-native view to mutate.
            changed_props: Props whose values changed (a value of
                `None` indicates the prop was removed).

        Raises:
            NotImplementedError: Subclasses must override.
        """
        raise NotImplementedError

    def add_child(self, parent: Any, child: Any) -> None:
        """Append `child` to `parent`. No-op for leaf handlers."""

    def remove_child(self, parent: Any, child: Any) -> None:
        """Remove `child` from `parent`. No-op for leaf handlers."""

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        """Insert `child` at `index`. Defaults to appending."""
        self.add_child(parent, child)

    def set_frame(self, native_view: Any, x: float, y: float, width: float, height: float) -> None:
        """Position and size ``native_view`` relative to its parent.

        Coordinates are in points and relative to the parent's content
        origin. Default no-op so handlers that don't need explicit
        positioning (e.g., `Modal`) can opt out.

        Args:
            native_view: The platform-native view.
            x: X-coordinate (points) of the view's top-left corner
                relative to its parent's content origin.
            y: Y-coordinate (points) of the view's top-left corner.
            width: View width in points.
            height: View height in points.
        """

    def measure_intrinsic(
        self,
        native_view: Any,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        """Return the natural ``(width, height)`` of a content-sized view.

        Used by the layout engine for leaves whose size depends on
        their content (text, buttons, images). Either ``max_width`` or
        ``max_height`` may be `math.inf` to indicate no constraint.

        The default implementation returns ``(0, 0)``; override for
        leaves whose size depends on their content. Container handlers
        leave this alone — the engine sizes containers by laying out
        their children.

        Args:
            native_view: The platform-native view to measure.
            max_width: Maximum width in points (or `math.inf`).
            max_height: Maximum height in points (or `math.inf`).

        Returns:
            ``(width, height)`` in points.
        """
        return (0.0, 0.0)


# ======================================================================
# Color parsing
# ======================================================================


def parse_color_int(color: Union[str, int]) -> int:
    """Parse a color value into a signed 32-bit ARGB int.

    Accepts `"#RRGGBB"`, `"#AARRGGBB"`, or a raw integer. Java APIs
    such as `setBackgroundColor` expect a signed 32-bit int, so values
    with a high alpha byte (e.g., `0xFF......`) must be converted to
    their negative two's-complement equivalent.

    Args:
        color: Hex string (with or without leading `#`) or an int.

    Returns:
        Signed 32-bit ARGB int suitable for Android's color APIs.
    """
    if isinstance(color, int):
        val = color
    else:
        c = color.strip().lstrip("#")
        if len(c) == 6:
            c = "FF" + c
        val = int(c, 16)
    if val > 0x7FFFFFFF:
        val -= 0x100000000
    return val


# ======================================================================
# Helpers shared by Android and iOS measure callbacks
# ======================================================================


def _safe_max(value: float, fallback: float = 1e6) -> float:
    """Clamp ``math.inf`` to a large finite value for native measure calls."""
    if not math.isfinite(value):
        return fallback
    return max(0.0, value)
