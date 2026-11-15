"""Graphics factories: ``LinearGradient`` and ``BlurView`` (``Svg`` is in ``vector``)."""

from typing import Literal, Optional, Sequence, Tuple, Unpack

from ..element import Element, Node
from ..hooks import Ref
from ..style import (
    Color,
    StyleProp,
)
from ._base import _make_element
from .props import CommonProps

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


def LinearGradient(
    *children: Node,
    colors: Sequence[Color],
    locations: Optional[Sequence[float]] = None,
    start_point: Tuple[float, float] = (0.0, 0.0),
    end_point: Tuple[float, float] = (0.0, 1.0),
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
    **props: Unpack[CommonProps],
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
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.
        **props: Shared accessibility and test keywords; see
            [`AccessibilityProps`][pythonnative.AccessibilityProps].

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
        _defaults={"flex_direction": "column"},
        **props,
    )


def BlurView(
    *children: Node,
    blur_type: BlurType = "regular",
    intensity: float = 100.0,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
    **props: Unpack[CommonProps],
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
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity for keyed reconciliation.
        **props: Shared accessibility and test keywords; see
            [`AccessibilityProps`][pythonnative.AccessibilityProps].

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
        _defaults={"flex_direction": "column"},
        **props,
    )
