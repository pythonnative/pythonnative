"""Graphics factories: ``Svg``, ``LinearGradient``, and ``BlurView``."""

from typing import Any, Callable, Literal, Optional, Sequence, Tuple, Union

from ..element import Element
from ..hooks import Ref
from ..style import (
    AccessibilityAction,
    AccessibilityState,
    AccessibilityValue,
    Color,
    ImportantForAccessibility,
    StyleProp,
)
from ..svg import FillRule, LineCap, LineJoin, SvgShape, flatten
from ._base import _accessibility_actions, _accessibility_value, _make_element

PreserveAspectRatio = Literal["meet", "slice", "none"]
"""How an ``Svg`` view box scales into a frame of a different aspect ratio."""

BlurType = Literal[
    "light",
    "dark",
    "regular",
    "prominent",
    "extra_light",
    "system_thin_material",
    "system_material",
    "system_thick_material",
    "system_chrome_material",
]
"""Backdrop material styles for [`BlurView`][pythonnative.BlurView]."""


def Svg(
    *children: Any,
    shapes: Optional[Sequence[SvgShape]] = None,
    view_box: Optional[str] = None,
    preserve_aspect_ratio: PreserveAspectRatio = "meet",
    fill: Optional[Color] = None,
    stroke: Optional[Color] = None,
    stroke_width: Optional[float] = None,
    stroke_linecap: Optional[LineCap] = None,
    stroke_linejoin: Optional[LineJoin] = None,
    fill_rule: Optional[FillRule] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    accessibility_state: Optional[AccessibilityState] = None,
    accessibility_value: Optional[Union[str, AccessibilityValue]] = None,
    accessibility_actions: Optional[Sequence[AccessibilityAction]] = None,
    on_accessibility_action: Optional[Callable[[str], Any]] = None,
    important_for_accessibility: Optional[ImportantForAccessibility] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Draw vector shapes in a single native view.

    Pass shapes from ``pythonnative.svg`` (``Path``,
    ``Circle``, ``Rect``, ``Line``, ``Polyline``, ``Polygon``, ``Ellipse``,
    and ``G`` groups) as children. Coordinates are in ``view_box`` units
    and are scaled into the view's frame. Without an explicit ``width``
    and ``height`` in ``style``, the view measures to the view box size.

    Paint left unset on a shape inherits the root values here, then the
    SVG defaults (black fill, no stroke). Set ``fill="none"`` to draw
    outlines only.

    Args:
        *children: Shapes and groups to draw, in paint order.
        shapes: Pre-flattened shape records (what
            [`pn.svg.load`][pythonnative.svg.load] produces). Combined
            with ``children``.
        view_box: ``"min-x min-y width height"``. Defaults to
            ``"0 0 24 24"``.
        preserve_aspect_ratio: ``"meet"`` letterboxes, ``"slice"`` crops,
            ``"none"`` stretches.
        fill: Default fill color for shapes that don't set one.
        stroke: Default stroke color.
        stroke_width: Default stroke width in view box units.
        stroke_linecap: Default line cap.
        stroke_linejoin: Default line join.
        fill_rule: Default fill rule.
        style: Style dict (or list of dicts). ``width`` and ``height`` set
            the drawn size; ``opacity`` and transforms apply as usual.
        accessibility_label: Spoken description for screen readers.
        accessibility_role: Override the default ``"image"`` role.
        accessible: Override whether the element is exposed to AT.
        accessibility_state: Current widget state for assistive tech.
        accessibility_value: The widget's current value for assistive
            tech (a string or an
            [`AccessibilityValue`][pythonnative.AccessibilityValue]).
        accessibility_actions: Custom screen-reader actions, each an
            [`AccessibilityAction`][pythonnative.AccessibilityAction].
        on_accessibility_action: Callback invoked with the action name.
        important_for_accessibility: Whether AT sees this view and its
            subtree.
        test_id: Stable identifier for UI tests.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Svg"``.

    Example:
        ```python
        from pythonnative import svg

        pn.Svg(
            svg.Circle(cx=12, cy=12, r=10, fill="#0EA5E9"),
            svg.Path(d="M8 12h8", stroke="white", stroke_width=2),
            view_box="0 0 24 24",
            style=pn.style(width=48, height=48),
        )
        ```
    """
    records = flatten(shapes or ()) + flatten(children)
    return _make_element(
        "Svg",
        style=style,
        ref=ref,
        key=key,
        shapes=records,
        view_box=view_box or "0 0 24 24",
        preserve_aspect_ratio=preserve_aspect_ratio if preserve_aspect_ratio != "meet" else None,
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        stroke_linecap=stroke_linecap,
        stroke_linejoin=stroke_linejoin,
        fill_rule=fill_rule,
        accessibility_label=accessibility_label,
        accessibility_role=accessibility_role,
        accessible=accessible,
        accessibility_state=accessibility_state,
        accessibility_value=_accessibility_value(accessibility_value),
        accessibility_actions=_accessibility_actions(accessibility_actions),
        on_accessibility_action=on_accessibility_action,
        important_for_accessibility=important_for_accessibility,
        test_id=test_id,
        _defaults={"accessibility_role": "image"},
    )


def LinearGradient(
    *children: Element,
    colors: Sequence[Color],
    locations: Optional[Sequence[float]] = None,
    start_point: Tuple[float, float] = (0.0, 0.0),
    end_point: Tuple[float, float] = (0.0, 1.0),
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """A container filled with a linear color gradient.

    Lays out ``children`` exactly like [`View`][pythonnative.View]; the
    gradient is the background. ``start_point`` and ``end_point`` are
    unit coordinates in the view's box (``(0, 0)`` top-left, ``(1, 1)``
    bottom-right), so the defaults draw top to bottom.

    Args:
        *children: Content drawn over the gradient.
        colors: Two or more colors, in order from ``start_point`` to
            ``end_point``.
        locations: Optional stop positions in ``[0, 1]``, one per color.
            Evenly spaced when omitted.
        start_point: Unit point where the first color sits.
        end_point: Unit point where the last color sits.
        style: Style dict (or list of dicts); ``border_radius`` clips the
            gradient.
        accessibility_label: Spoken description for screen readers.
        accessible: Override whether the element is exposed to AT.
        test_id: Stable identifier for UI tests.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"LinearGradient"``.

    Raises:
        ValueError: If fewer than two colors are given or ``locations``
            doesn't match ``colors`` in length.

    Example:
        ```python
        pn.LinearGradient(
            pn.Text("Welcome", style=pn.style(color="white", font_size=24)),
            colors=["#6366F1", "#EC4899"],
            start_point=(0, 0),
            end_point=(1, 1),
            style=pn.style(padding=24, border_radius=16),
        )
        ```
    """
    colors = list(colors)
    if len(colors) < 2:
        raise ValueError("LinearGradient needs at least two colors")
    if locations is not None:
        locations = [float(value) for value in locations]
        if len(locations) != len(colors):
            raise ValueError("LinearGradient locations must have one entry per color")
    return _make_element(
        "LinearGradient",
        *children,
        style=style,
        ref=ref,
        key=key,
        colors=colors,
        locations=locations,
        start_point=(float(start_point[0]), float(start_point[1])),
        end_point=(float(end_point[0]), float(end_point[1])),
        accessibility_label=accessibility_label,
        accessible=accessible,
        test_id=test_id,
        _defaults={"flex_direction": "column"},
    )


def BlurView(
    *children: Element,
    blur_type: BlurType = "regular",
    intensity: float = 100.0,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    test_id: Optional[str] = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """A container that blurs whatever is drawn behind it.

    On iOS this is a ``UIVisualEffectView`` (``blur_type`` selects the
    ``UIBlurEffect`` style). In the browser preview it is
    ``backdrop-filter``. Android has no system backdrop blur, so the view
    snapshots the content beneath it at reduced resolution, blurs the
    snapshot, and tints it; it looks right for static backgrounds and
    approximates animated ones.

    Args:
        *children: Content drawn over the blur.
        blur_type: The material style. ``"light"``, ``"dark"``, and
            ``"regular"`` are portable; the ``system_*`` values map to the
            iOS 13 materials and fall back to the closest tint elsewhere.
        intensity: Blur strength from ``0`` (transparent) to ``100``.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessible: Override whether the element is exposed to AT.
        test_id: Stable identifier for UI tests.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"BlurView"``.

    Example:
        ```python
        pn.ImageBackground(
            pn.BlurView(pn.Text("Caption"), blur_type="dark", style=pn.style(padding=12)),
            source=pn.asset("images/hero.jpg"),
            style=pn.style(height=200, justify_content="flex-end"),
        )
        ```
    """
    return _make_element(
        "BlurView",
        *children,
        style=style,
        ref=ref,
        key=key,
        blur_type=blur_type if blur_type != "regular" else None,
        intensity=float(intensity) if intensity != 100 else None,
        accessibility_label=accessibility_label,
        accessible=accessible,
        test_id=test_id,
        _defaults={"flex_direction": "column"},
    )
