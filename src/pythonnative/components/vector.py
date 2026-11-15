"""The ``Svg`` factory.

It lives apart from the other graphics factories so that
``pythonnative.svg`` (and the XML parser it uses) loads on first use
rather than with ``import pythonnative``.
"""

from typing import Any, Literal, Optional, Sequence, Unpack

from ..element import Element
from ..hooks import Ref
from ..style import (
    Color,
    StyleProp,
)
from ..svg import FillRule, LineCap, LineJoin, SvgShape, flatten
from ._base import _make_element
from .props import CommonProps

PreserveAspectRatio = Literal["meet", "slice", "none"]
"""How an ``Svg`` view box scales into a frame of a different aspect ratio."""


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
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
    **props: Unpack[CommonProps],
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
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.
        **props: Shared accessibility and test keywords; see
            [`AccessibilityProps`][pythonnative.AccessibilityProps].

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
        _defaults={"accessibility_role": "image"},
        **props,
    )
