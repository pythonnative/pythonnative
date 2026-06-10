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

    A `ViewHandler` knows how to create, update, re-parent, and destroy
    native views of one element type. The reconciler never calls a
    handler directly — it emits a batch of mutation ops
    (`pythonnative.mutations`) that the
    [`NativeViewRegistry`][pythonnative.native_views.NativeViewRegistry]
    applies by dispatching to handlers. Handlers never need to know
    about `Element` or `VNode`.

    Event contract: props delivered to
    [`create`][pythonnative.native_views.base.ViewHandler.create] /
    [`update`][pythonnative.native_views.base.ViewHandler.update]
    contain **no Python callables**. The set of event names wired on
    the element arrives under the ``_pn_events`` key (see
    [`event_names`][pythonnative.events.event_names]); handlers wire
    platform listeners once at create time and forward firings through
    [`dispatch_event`][pythonnative.events.dispatch_event] using the
    tag passed to ``create``.

    Subclasses must override ``create`` and ``update``. Container
    handlers override the child-management methods; leaf handlers can
    leave them as no-ops. Handlers whose intrinsic size depends on
    content (text, buttons, images) override
    [`measure_intrinsic`][pythonnative.native_views.base.ViewHandler.measure_intrinsic].
    """

    def create(self, tag: int, props: Dict[str, Any]) -> Any:
        """Create a fresh native view and apply initial *visual* props.

        Layout-related props (``width``, ``height``, ``flex``, ``padding``,
        etc.) are consumed by the layout engine and applied via
        [`set_frame`][pythonnative.native_views.base.ViewHandler.set_frame],
        so handlers should ignore them here.

        Args:
            tag: The reconciler-assigned identity for this view. Used
                when dispatching events back into Python.
            props: Initial props dict (callable-free; event names under
                ``_pn_events``).

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

    def insert_child(self, parent: Any, child: Any, index: int) -> None:
        """Ensure `child` sits at `index` among `parent`'s children.

        Must be **move-aware**: when `child` is already attached to
        `parent`, reposition it instead of attaching twice. Handlers
        should clamp `index` to the current child count. No-op for
        leaf handlers.
        """

    def remove_child(self, parent: Any, child: Any) -> None:
        """Remove `child` from `parent` without destroying it. No-op for leaf handlers."""

    def destroy(self, native_view: Any) -> None:
        """Release platform resources owned by ``native_view``.

        Called exactly once when the reconciler unmounts the view.
        The default is a no-op; override to detach listeners, cancel
        in-flight work, or destroy widgets that the platform doesn't
        garbage-collect.
        """

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

    def command(self, native_view: Any, name: str, args: Dict[str, Any]) -> Any:
        """Execute an imperative command (e.g. ``"scroll_to_offset"``).

        Commands are the escape hatch for one-shot imperative actions
        that don't fit declarative props — scrolling, focusing,
        flashing indicators. Unknown commands should be ignored.

        Args:
            native_view: The platform-native view.
            name: Command name.
            args: Command arguments.

        Returns:
            An optional command-specific result.
        """
        return None

    def set_animated_property(self, native_view: Any, prop_name: str, value: Any) -> None:
        """Apply one frame of a Python-driven animation immediately.

        This is the fallback path used by the desktop preview and by
        animations the platform cannot drive natively. ``prop_name``
        is one of ``opacity``, ``background_color``, ``translate_x``,
        ``translate_y``, ``scale``, ``scale_x``, ``scale_y``,
        ``rotate``.
        """

    def start_animation(
        self,
        native_view: Any,
        anim_id: int,
        prop_name: str,
        spec: Dict[str, Any],
    ) -> bool:
        """Start a natively-driven animation, if the platform supports it.

        ``spec`` describes the animation::

            {"kind": "timing", "from": 0.0, "to": 1.0,
             "duration_ms": 300.0, "easing": "ease_in_out"}
            {"kind": "spring", "from": ..., "to": ...,
             "stiffness": 100.0, "damping": 10.0, "mass": 1.0,
             "initial_velocity": 0.0}

        Implementations must invoke
        ``pythonnative.animated.native_animation_completed(anim_id, finished)``
        when the animation completes or is cancelled.

        Returns:
            ``True`` when the animation was started natively. ``False``
            tells the caller to fall back to the Python ticker (the
            default).
        """
        return False

    def cancel_animation(self, native_view: Any, anim_id: int) -> Any:
        """Cancel a natively-driven animation.

        Returns:
            The property's current (presentation) value when the
            platform can read it, else ``None``.
        """
        return None


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
