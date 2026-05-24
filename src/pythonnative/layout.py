"""Pure-Python flexbox layout engine.

Computes absolute positions and sizes for every node in a layout tree
based on CSS flexbox-inspired style properties. Inspired by Facebook's
Yoga and React Native's layout system, but implemented entirely in
Python so PythonNative does not depend on a native layout library.

The engine is invoked by the reconciler after each commit pass:

1. The reconciler walks the committed VNode tree and builds a parallel
   [`LayoutNode`][pythonnative.layout.LayoutNode] tree, copying the
   layout-relevant style props onto each node and attaching a
   ``measure`` callback to leaves whose natural size depends on their
   content (text, images).
2. [`calculate_layout`][pythonnative.layout.calculate_layout] is called
   with the viewport size; it recursively determines each node's
   ``(x, y, width, height)`` relative to its parent's coordinate space.
3. The reconciler walks the tree again and applies each computed frame
   to the corresponding native view via the backend's
   ``set_frame`` method.

The algorithm supports:

- **Flex containers**: ``flex_direction`` (``row``/``column`` and their
  reverse variants), ``justify_content`` (``flex_start`` / ``center`` /
  ``flex_end`` / ``space_between`` / ``space_around`` / ``space_evenly``),
  ``align_items`` (``stretch`` / ``flex_start`` / ``center`` /
  ``flex_end``), and ``align_self`` overrides per child.
- **Sizing**: explicit ``width`` / ``height`` (numbers or percentages),
  ``min_width`` / ``max_width`` / ``min_height`` / ``max_height``
  constraints, ``aspect_ratio``, and content-based sizing via the
  optional ``measure`` callback.
- **Flex distribution**: ``flex`` (RN shorthand for grow factor with
  ``flex_basis: 0``), ``flex_grow``, ``flex_shrink``, ``flex_basis``.
- **Absolute positioning**: ``position: "absolute"`` with ``top``,
  ``right``, ``bottom``, ``left`` insets (numbers or percentages).
  Absolute children are positioned relative to the parent's padding box
  and do not participate in flex distribution.
- **Spacing**: ``padding`` (scalar, dict with ``horizontal`` /
  ``vertical`` / ``all`` / per-edge keys, or per-edge keys directly),
  ``margin`` (same shape as ``padding``), and inter-child ``spacing``
  (alias: ``gap``).

Example:
    ```python
    from pythonnative.layout import LayoutNode, calculate_layout

    root = LayoutNode(
        style={"flex_direction": "row", "padding": 8, "spacing": 4},
        children=[
            LayoutNode(style={"width": 80, "height": 40}),
            LayoutNode(style={"flex": 1, "height": 40}),
            LayoutNode(style={"width": 60, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 200)
    # root.children[0].x == 8, .width == 80
    # root.children[1].x == 92, .width == 156  (filled by flex: 1)
    # root.children[2].x == 252, .width == 60
    ```
"""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

# ======================================================================
# Public constants
# ======================================================================

LAYOUT_STYLE_KEYS = frozenset(
    {
        "width",
        "height",
        "min_width",
        "max_width",
        "min_height",
        "max_height",
        "flex",
        "flex_grow",
        "flex_shrink",
        "flex_basis",
        "align_self",
        "position",
        "top",
        "right",
        "bottom",
        "left",
        "margin",
        "margin_top",
        "margin_bottom",
        "margin_left",
        "margin_right",
        "margin_horizontal",
        "margin_vertical",
        "padding",
        "padding_top",
        "padding_bottom",
        "padding_left",
        "padding_right",
        "padding_horizontal",
        "padding_vertical",
        "flex_direction",
        "justify_content",
        "align_items",
        "spacing",
        "gap",
        "aspect_ratio",
    }
)
"""Style keys that affect layout (and are consumed by the layout engine)."""

# Flex direction values
FLEX_DIRECTION_COLUMN = "column"
FLEX_DIRECTION_COLUMN_REVERSE = "column_reverse"
FLEX_DIRECTION_ROW = "row"
FLEX_DIRECTION_ROW_REVERSE = "row_reverse"

# justify_content values
JUSTIFY_FLEX_START = "flex_start"
JUSTIFY_CENTER = "center"
JUSTIFY_FLEX_END = "flex_end"
JUSTIFY_SPACE_BETWEEN = "space_between"
JUSTIFY_SPACE_AROUND = "space_around"
JUSTIFY_SPACE_EVENLY = "space_evenly"

# align_items / align_self values
ALIGN_AUTO = "auto"
ALIGN_FLEX_START = "flex_start"
ALIGN_CENTER = "center"
ALIGN_FLEX_END = "flex_end"
ALIGN_STRETCH = "stretch"

# position values
POSITION_RELATIVE = "relative"
POSITION_ABSOLUTE = "absolute"

# Friendly aliases on cross-axis alignment props.
_ALIGN_ALIASES = {
    "start": ALIGN_FLEX_START,
    "leading": ALIGN_FLEX_START,
    "top": ALIGN_FLEX_START,
    "end": ALIGN_FLEX_END,
    "trailing": ALIGN_FLEX_END,
    "bottom": ALIGN_FLEX_END,
    "fill": ALIGN_STRETCH,
}

_JUSTIFY_ALIASES = {
    "start": JUSTIFY_FLEX_START,
    "leading": JUSTIFY_FLEX_START,
    "top": JUSTIFY_FLEX_START,
    "end": JUSTIFY_FLEX_END,
    "trailing": JUSTIFY_FLEX_END,
    "bottom": JUSTIFY_FLEX_END,
}

# A measure callback receives ``(max_width, max_height)`` (either may be
# ``math.inf`` to indicate no constraint) and returns the leaf's natural
# ``(width, height)`` in points.
MeasureFn = Callable[[float, float], Tuple[float, float]]


# ======================================================================
# Helpers
# ======================================================================


def _is_row(direction: str) -> bool:
    """Return whether `direction` lays out children along the horizontal axis."""
    return direction in (FLEX_DIRECTION_ROW, FLEX_DIRECTION_ROW_REVERSE)


def _is_reverse(direction: str) -> bool:
    """Return whether `direction` is one of the reverse variants."""
    return direction in (FLEX_DIRECTION_ROW_REVERSE, FLEX_DIRECTION_COLUMN_REVERSE)


def _to_float(value: Any) -> Optional[float]:
    """Coerce ``value`` to ``float``; return ``None`` if not coercible."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_value(value: Any, parent_size: float) -> Optional[float]:
    """Resolve a dimension value to points.

    Accepts:

    - ``None``: returns ``None``.
    - ``int`` / ``float``: returned as-is.
    - ``str`` ending in ``"%"``: percentage of ``parent_size``. If
      ``parent_size`` is not finite (e.g., inside a vertically
      unbounded ScrollView), percentages collapse to ``None`` so the
      caller can fall back to content-based sizing.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if s.endswith("%"):
            try:
                pct = float(s[:-1])
            except ValueError:
                return None
            if not math.isfinite(parent_size):
                return None
            return parent_size * pct / 100.0
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _padding_edges(value: Any, parent_w: float, parent_h: float) -> Tuple[float, float, float, float]:
    """Resolve a padding/margin value to ``(left, top, right, bottom)``."""
    if value is None:
        return (0.0, 0.0, 0.0, 0.0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        return (v, v, v, v)
    if isinstance(value, dict):
        all_v = _resolve_value(value.get("all"), max(parent_w, parent_h)) or 0.0
        h_v = _resolve_value(value.get("horizontal"), parent_w)
        v_v = _resolve_value(value.get("vertical"), parent_h)
        h = h_v if h_v is not None else all_v
        v = v_v if v_v is not None else all_v
        left = _resolve_value(value.get("left"), parent_w)
        right = _resolve_value(value.get("right"), parent_w)
        top = _resolve_value(value.get("top"), parent_h)
        bottom = _resolve_value(value.get("bottom"), parent_h)
        return (
            left if left is not None else h,
            top if top is not None else v,
            right if right is not None else h,
            bottom if bottom is not None else v,
        )
    if isinstance(value, str):
        v = _resolve_value(value, max(parent_w, parent_h))
        if v is None:
            return (0.0, 0.0, 0.0, 0.0)
        return (v, v, v, v)
    return (0.0, 0.0, 0.0, 0.0)


def _resolve_padding_for(
    style: Dict[str, Any],
    parent_w: float,
    parent_h: float,
    prefix: str,
) -> Tuple[float, float, float, float]:
    """Resolve padding/margin from `style`, honoring per-edge overrides."""
    base_l, base_t, base_r, base_b = _padding_edges(style.get(prefix), parent_w, parent_h)

    h_override = _resolve_value(style.get(f"{prefix}_horizontal"), parent_w)
    v_override = _resolve_value(style.get(f"{prefix}_vertical"), parent_h)
    if h_override is not None:
        base_l = h_override
        base_r = h_override
    if v_override is not None:
        base_t = v_override
        base_b = v_override

    left = _resolve_value(style.get(f"{prefix}_left"), parent_w)
    right = _resolve_value(style.get(f"{prefix}_right"), parent_w)
    top = _resolve_value(style.get(f"{prefix}_top"), parent_h)
    bottom = _resolve_value(style.get(f"{prefix}_bottom"), parent_h)
    if left is not None:
        base_l = left
    if right is not None:
        base_r = right
    if top is not None:
        base_t = top
    if bottom is not None:
        base_b = bottom
    return (base_l, base_t, base_r, base_b)


def _clamp(
    value: Optional[float],
    minimum: Any,
    maximum: Any,
    parent_size: float,
) -> Optional[float]:
    """Clamp `value` to ``[minimum, maximum]``, resolving percentage limits."""
    if value is None:
        return None
    min_v = _resolve_value(minimum, parent_size)
    max_v = _resolve_value(maximum, parent_size)
    if min_v is not None and value < min_v:
        value = min_v
    if max_v is not None and value > max_v:
        value = max_v
    return value


def _flex_grow(style: Dict[str, Any]) -> float:
    """Return the effective `flex_grow` for a child.

    Supports the React Native ``flex`` shorthand: a positive ``flex``
    value implies ``flex_grow = flex``. ``flex_grow`` overrides the
    shorthand if both are set.
    """
    fg = style.get("flex_grow")
    if fg is not None:
        v = _to_float(fg)
        return max(v, 0.0) if v is not None else 0.0
    f = _to_float(style.get("flex"))
    if f is not None and f > 0:
        return f
    return 0.0


def _flex_shrink(style: Dict[str, Any]) -> float:
    """Return the effective `flex_shrink` for a child.

    Defaults to ``0`` for normal children, but a positive React Native
    ``flex`` shorthand implies ``flex_shrink = 1`` unless explicitly
    overridden.
    """
    fs = style.get("flex_shrink")
    if fs is not None:
        v = _to_float(fs)
        return max(v, 0.0) if v is not None else 0.0
    f = _to_float(style.get("flex"))
    if f is not None and f > 0:
        return 1.0
    return 0.0


def _flex_basis(style: Dict[str, Any], main_avail: float) -> Optional[float]:
    """Return the effective `flex_basis` for a child, or ``None`` for ``"auto"``.

    A bare numeric ``flex`` shorthand implies ``flex_basis = 0``
    (matches RN), unless ``flex_basis`` is explicitly set.
    """
    fb = style.get("flex_basis")
    if fb is not None:
        if isinstance(fb, str) and fb.strip().lower() == "auto":
            return None
        return _resolve_value(fb, main_avail)
    f = _to_float(style.get("flex"))
    if f is not None and f > 0:
        return 0.0
    return None


def _resolve_align(value: Any, default: str = ALIGN_STRETCH) -> str:
    """Normalize an `align_items` / `align_self` value, applying aliases."""
    if value is None:
        return default
    s = str(value)
    return _ALIGN_ALIASES.get(s, s)


def _resolve_justify(value: Any) -> str:
    """Normalize a `justify_content` value, applying aliases."""
    if value is None:
        return JUSTIFY_FLEX_START
    s = str(value)
    return _JUSTIFY_ALIASES.get(s, s)


# ======================================================================
# LayoutNode
# ======================================================================


class LayoutNode:
    """A node in the layout tree.

    Holds the layout-relevant style props, child layout nodes, and the
    computed output (``x``, ``y``, ``width``, ``height`` in points
    relative to the parent's coordinate space).

    Attributes:
        style: Dict of layout-relevant style props (a subset of the
            element's full props; usually filtered through
            [`LAYOUT_STYLE_KEYS`][pythonnative.layout.LAYOUT_STYLE_KEYS]).
        children: Ordered list of child `LayoutNode`s.
        measure: Optional measure callback for leaf nodes whose natural
            size depends on their content (e.g., text). Receives
            ``(max_width, max_height)`` and returns ``(width, height)``.
            Either argument may be ``math.inf``.
        user_data: Free-form attribute the caller may use to associate
            each layout node with the corresponding native view; the
            engine itself does not inspect it.
        x: Computed x-coordinate relative to the parent's coordinate
            space.
        y: Computed y-coordinate relative to the parent's coordinate
            space.
        width: Computed width in points.
        height: Computed height in points.
    """

    __slots__ = (
        "style",
        "children",
        "measure",
        "user_data",
        "x",
        "y",
        "width",
        "height",
        "_pn_scroll_axis",
    )

    def __init__(
        self,
        style: Optional[Dict[str, Any]] = None,
        children: Optional[List["LayoutNode"]] = None,
        measure: Optional[MeasureFn] = None,
        user_data: Any = None,
    ) -> None:
        self.style = style or {}
        self.children = list(children) if children else []
        self.measure = measure
        self.user_data = user_data
        self.x: float = 0.0
        self.y: float = 0.0
        self.width: float = 0.0
        self.height: float = 0.0
        # ``"x"``/``"y"`` for scroll containers; ``None`` for everything
        # else. Consumed by ``_measure_container`` to clamp the node's
        # own main-axis size to the parent's available space while still
        # measuring children unbounded on the scroll axis (which is what
        # makes the native ``UIScrollView`` / Android ``ScrollView``
        # actually scroll). The reconciler stamps this when building the
        # layout tree for ``ScrollView`` elements.
        self._pn_scroll_axis: Optional[str] = None

    def __repr__(self) -> str:
        return (
            f"LayoutNode(x={self.x:g}, y={self.y:g}, "
            f"w={self.width:g}, h={self.height:g}, "
            f"children={len(self.children)})"
        )


# ======================================================================
# Public entry point
# ======================================================================


def calculate_layout(node: LayoutNode, available_width: float, available_height: float) -> None:
    """Compute layout for `node` and all descendants, in place.

    Sizes the root from its own style and content. Callers that want
    the root to fill its viewport should wrap it in a synthetic outer
    node with explicit ``width`` / ``height`` (the
    [`Reconciler`][pythonnative.reconciler.Reconciler] does this when
    running the layout pass after a commit).

    Args:
        node: Root of the layout tree.
        available_width: Available width in points. Pass
            ``math.inf`` for unbounded (e.g., horizontal scroll).
        available_height: Available height in points. Pass
            ``math.inf`` for unbounded (e.g., vertical scroll).
    """
    _measure_node(node, available_width, available_height)
    node.x = 0.0
    node.y = 0.0
    _position_children(node)


# ======================================================================
# Measurement: top-down sizing
# ======================================================================


def _measure_node(
    node: LayoutNode,
    avail_w: float,
    avail_h: float,
    forced_w: Optional[float] = None,
    forced_h: Optional[float] = None,
) -> None:
    """Compute ``node.width`` / ``node.height`` and recursively size children.

    Args:
        node: Node to measure.
        avail_w: Available width (constraint, never a forced value).
        avail_h: Available height (constraint, never a forced value).
        forced_w: If set, overrides any width computed from style or
            content. Used by parents to enforce flex distribution or
            cross-axis stretch.
        forced_h: As ``forced_w`` but for height.
    """
    style = node.style

    explicit_w = forced_w if forced_w is not None else _resolve_value(style.get("width"), avail_w)
    explicit_h = forced_h if forced_h is not None else _resolve_value(style.get("height"), avail_h)

    aspect = _to_float(style.get("aspect_ratio"))
    if aspect is not None and aspect > 0:
        if explicit_w is not None and explicit_h is None:
            explicit_h = explicit_w / aspect
        elif explicit_h is not None and explicit_w is None:
            explicit_w = explicit_h * aspect

    explicit_w = _clamp(explicit_w, style.get("min_width"), style.get("max_width"), avail_w)
    explicit_h = _clamp(explicit_h, style.get("min_height"), style.get("max_height"), avail_h)

    if node.children:
        width, height = _measure_container(node, avail_w, avail_h, explicit_w, explicit_h)
    elif node.measure is not None:
        width, height = _measure_leaf(node, avail_w, avail_h, explicit_w, explicit_h, aspect)
    else:
        width = explicit_w if explicit_w is not None else 0.0
        height = explicit_h if explicit_h is not None else 0.0

    if aspect is not None and aspect > 0:
        if explicit_w is None and explicit_h is not None and width <= 0:
            width = height * aspect
        elif explicit_h is None and explicit_w is not None and height <= 0:
            height = width / aspect

    width_clamped = _clamp(width, style.get("min_width"), style.get("max_width"), avail_w)
    height_clamped = _clamp(height, style.get("min_height"), style.get("max_height"), avail_h)
    width = width_clamped if width_clamped is not None else 0.0
    height = height_clamped if height_clamped is not None else 0.0

    node.width = max(width, 0.0)
    node.height = max(height, 0.0)


def _measure_leaf(
    node: LayoutNode,
    avail_w: float,
    avail_h: float,
    explicit_w: Optional[float],
    explicit_h: Optional[float],
    aspect: Optional[float],
) -> Tuple[float, float]:
    """Measure a leaf node by invoking its `measure` callback."""
    assert node.measure is not None
    max_w = explicit_w if explicit_w is not None else avail_w
    max_h = explicit_h if explicit_h is not None else avail_h
    try:
        mw, mh = node.measure(max_w, max_h)
    except Exception:
        mw, mh = 0.0, 0.0
    width = explicit_w if explicit_w is not None else float(mw)
    height = explicit_h if explicit_h is not None else float(mh)
    if aspect is not None and aspect > 0:
        if explicit_w is None and explicit_h is None:
            height = width / aspect
    return width, height


def _measure_container(
    node: LayoutNode,
    avail_w: float,
    avail_h: float,
    explicit_w: Optional[float],
    explicit_h: Optional[float],
) -> Tuple[float, float]:
    """Layout flex children and determine the container's own size."""
    style = node.style
    base_w = explicit_w if explicit_w is not None else avail_w
    base_h = explicit_h if explicit_h is not None else avail_h
    pad_l, pad_t, pad_r, pad_b = _resolve_padding_for(style, base_w, base_h, "padding")
    pad_x = pad_l + pad_r
    pad_y = pad_t + pad_b

    content_w = (explicit_w - pad_x) if explicit_w is not None else max(0.0, avail_w - pad_x)
    content_h = (explicit_h - pad_y) if explicit_h is not None else max(0.0, avail_h - pad_y)

    is_row = _is_row(style.get("flex_direction", FLEX_DIRECTION_COLUMN))
    main_bounded = (explicit_w is not None) if is_row else (explicit_h is not None)
    cross_bounded = (explicit_h is not None) if is_row else (explicit_w is not None)

    used_main, used_cross = _layout_flex_children(
        node,
        content_w,
        content_h,
        main_bounded=main_bounded,
        cross_bounded=cross_bounded,
    )

    if is_row:
        used_w, used_h = used_main, used_cross
    else:
        used_w, used_h = used_cross, used_main

    width = explicit_w if explicit_w is not None else (used_w + pad_x)
    height = explicit_h if explicit_h is not None else (used_h + pad_y)

    # Scroll containers: clamp the container's own main-axis size to the
    # parent's available space when no explicit size was provided. The
    # children are still measured against an unbounded main-axis (handled
    # via the wrapper inserted in ``Reconciler._build_layout_tree``) so the
    # overflow becomes the scrollable region. Without this clamp, the
    # container would grow to fit its content and there would be no
    # overflow for the native ScrollView to scroll. Skipped when the
    # parent is itself unbounded, so nested scroll views still fall back
    # to natural sizing (the inner scroll is unscrollable in that case,
    # which matches the behavior in React Native).
    scroll_axis = getattr(node, "_pn_scroll_axis", None)
    if scroll_axis == "y" and explicit_h is None and math.isfinite(avail_h):
        height = avail_h
    elif scroll_axis == "x" and explicit_w is None and math.isfinite(avail_w):
        width = avail_w
    return width, height


# ======================================================================
# Flex algorithm
# ======================================================================


def _child_main_size(child: LayoutNode, is_row: bool) -> float:
    return child.width if is_row else child.height


def _child_cross_size(child: LayoutNode, is_row: bool) -> float:
    return child.height if is_row else child.width


def _child_outer_main(child: LayoutNode, is_row: bool, parent_w: float, parent_h: float) -> float:
    """Main-axis extent including margins."""
    margins = _resolve_padding_for(child.style, parent_w, parent_h, "margin")
    margin_main = (margins[0] + margins[2]) if is_row else (margins[1] + margins[3])
    return _child_main_size(child, is_row) + margin_main


def _child_outer_cross(child: LayoutNode, is_row: bool, parent_w: float, parent_h: float) -> float:
    margins = _resolve_padding_for(child.style, parent_w, parent_h, "margin")
    margin_cross = (margins[1] + margins[3]) if is_row else (margins[0] + margins[2])
    return _child_cross_size(child, is_row) + margin_cross


def _measure_child_flexed(
    child: LayoutNode,
    main_size: Optional[float],
    cross_avail: float,
    cross_force: Optional[float],
    is_row: bool,
    main_bounded: bool,
) -> None:
    """Re-measure a child with optional forced main-axis size and cross hint."""
    fallback_main = math.inf if not main_bounded else cross_avail
    if is_row:
        avail_w = main_size if main_size is not None else fallback_main
        _measure_node(child, avail_w, cross_avail, forced_w=main_size, forced_h=cross_force)
    else:
        avail_h = main_size if main_size is not None else fallback_main
        _measure_node(child, cross_avail, avail_h, forced_w=cross_force, forced_h=main_size)


def _resolve_cross_force(
    child: LayoutNode,
    parent_align: str,
    cross_avail: float,
    cross_bounded: bool,
    is_row: bool,
) -> Optional[float]:
    """Compute the cross-axis size to force on a child, or ``None`` to let it size naturally.

    Cross-axis stretch only applies when:

    1. The child's effective alignment is ``stretch``.
    2. The parent's cross axis is bounded (so we have a target size).
    3. The child does not have its own explicit cross-axis dimension.
    """
    if not cross_bounded or not math.isfinite(cross_avail):
        return None
    align = _resolve_align(child.style.get("align_self"), default=parent_align)
    if align != ALIGN_STRETCH:
        return None
    cross_key = "height" if is_row else "width"
    if cross_key in child.style and child.style.get(cross_key) is not None:
        return None
    margins = _resolve_padding_for(child.style, cross_avail, cross_avail, "margin")
    margin_cross = (margins[1] + margins[3]) if is_row else (margins[0] + margins[2])
    return max(0.0, cross_avail - margin_cross)


def _layout_flex_children(
    parent: LayoutNode,
    content_w: float,
    content_h: float,
    main_bounded: bool,
    cross_bounded: bool,
) -> Tuple[float, float]:
    """Layout the in-flow children of `parent` along the flex axes.

    Returns ``(used_main, used_cross)`` — the total content size used
    by the in-flow children, including inter-child spacing but
    excluding the parent's own padding. The caller adds padding back
    in for the container's outer size.
    """
    style = parent.style
    direction = style.get("flex_direction", FLEX_DIRECTION_COLUMN)
    is_row = _is_row(direction)

    main_avail = content_w if is_row else content_h
    cross_avail = content_h if is_row else content_w
    spacing_v = _to_float(style.get("spacing"))
    if spacing_v is None:
        spacing_v = _to_float(style.get("gap"))
    spacing = spacing_v or 0.0

    in_flow: List[LayoutNode] = []
    absolute: List[LayoutNode] = []
    for child in parent.children:
        if child.style.get("position") == POSITION_ABSOLUTE:
            absolute.append(child)
        else:
            in_flow.append(child)

    align_items = _resolve_align(style.get("align_items"), default=ALIGN_STRETCH)

    flex_total = 0.0
    flex_entries: List[Tuple[LayoutNode, float, Optional[float]]] = []

    for child in in_flow:
        grow = _flex_grow(child.style)
        basis = _flex_basis(child.style, main_avail)
        cross_force = _resolve_cross_force(child, align_items, cross_avail, cross_bounded, is_row)

        if grow > 0:
            initial_main = basis if basis is not None else 0.0
            _measure_child_flexed(child, initial_main, cross_avail, cross_force, is_row, main_bounded)
            flex_total += grow
            flex_entries.append((child, grow, basis))
        elif basis is not None:
            _measure_child_flexed(child, basis, cross_avail, cross_force, is_row, main_bounded)
        else:
            avail_for_child_main = math.inf if not main_bounded else main_avail
            if is_row:
                _measure_node(child, avail_for_child_main, cross_avail, forced_h=cross_force)
            else:
                _measure_node(child, cross_avail, avail_for_child_main, forced_w=cross_force)

    fixed_main_total = 0.0
    flex_basis_total = 0.0
    for child in in_flow:
        if _flex_grow(child.style) > 0:
            basis = _flex_basis(child.style, main_avail) or 0.0
            margins = _resolve_padding_for(child.style, content_w, content_h, "margin")
            margin_main = (margins[0] + margins[2]) if is_row else (margins[1] + margins[3])
            flex_basis_total += basis + margin_main
        else:
            fixed_main_total += _child_outer_main(child, is_row, content_w, content_h)

    if len(in_flow) > 1:
        fixed_main_total += spacing * (len(in_flow) - 1)

    if flex_total > 0 and main_bounded and math.isfinite(main_avail):
        remaining = max(0.0, main_avail - fixed_main_total - flex_basis_total)
        for child, grow, basis in flex_entries:
            extra = (grow / flex_total) * remaining
            child_main = (basis or 0.0) + extra
            cross_force = _resolve_cross_force(child, align_items, cross_avail, cross_bounded, is_row)
            _measure_child_flexed(child, child_main, cross_avail, cross_force, is_row, main_bounded)

    if main_bounded and math.isfinite(main_avail):
        total_main = sum(_child_outer_main(c, is_row, content_w, content_h) for c in in_flow)
        if len(in_flow) > 1:
            total_main += spacing * (len(in_flow) - 1)
        overflow = total_main - main_avail
        if overflow > 0:
            shrinks = [(c, _flex_shrink(c.style)) for c in in_flow]
            total_shrink = sum(s * _child_main_size(c, is_row) for c, s in shrinks)
            if total_shrink > 0:
                for child, shrink in shrinks:
                    if shrink <= 0:
                        continue
                    take = (shrink * _child_main_size(child, is_row) / total_shrink) * overflow
                    new_main = max(0.0, _child_main_size(child, is_row) - take)
                    cross_force = _resolve_cross_force(child, align_items, cross_avail, cross_bounded, is_row)
                    _measure_child_flexed(child, new_main, cross_avail, cross_force, is_row, main_bounded)

    for child in absolute:
        _measure_absolute(child, content_w, content_h)

    used_main = sum(_child_outer_main(c, is_row, content_w, content_h) for c in in_flow)
    if len(in_flow) > 1:
        used_main += spacing * (len(in_flow) - 1)
    used_cross = max(
        (_child_outer_cross(c, is_row, content_w, content_h) for c in in_flow),
        default=0.0,
    )
    return used_main, used_cross


def _measure_absolute(child: LayoutNode, parent_w: float, parent_h: float) -> None:
    """Measure an absolutely-positioned child using `top` / `left` / etc."""
    style = child.style
    explicit_w = _resolve_value(style.get("width"), parent_w)
    explicit_h = _resolve_value(style.get("height"), parent_h)
    left = _resolve_value(style.get("left"), parent_w)
    right = _resolve_value(style.get("right"), parent_w)
    top = _resolve_value(style.get("top"), parent_h)
    bottom = _resolve_value(style.get("bottom"), parent_h)

    if explicit_w is None and left is not None and right is not None:
        explicit_w = max(0.0, parent_w - left - right)
    if explicit_h is None and top is not None and bottom is not None:
        explicit_h = max(0.0, parent_h - top - bottom)

    avail_w = explicit_w if explicit_w is not None else parent_w
    avail_h = explicit_h if explicit_h is not None else parent_h
    _measure_node(child, avail_w, avail_h, forced_w=explicit_w, forced_h=explicit_h)


# ======================================================================
# Positioning: bottom-up placement after sizing
# ======================================================================


def _position_children(parent: LayoutNode) -> None:
    """Assign ``x`` / ``y`` to every descendant.

    Sizes are already computed by [`_measure_node`][pythonnative.layout._measure_node];
    this pass walks the same tree and applies ``justify_content`` /
    ``align_items`` / absolute positioning to determine concrete
    coordinates relative to each parent's coordinate space.
    """
    if not parent.children:
        return

    style = parent.style
    direction = style.get("flex_direction", FLEX_DIRECTION_COLUMN)
    is_row = _is_row(direction)
    reverse = _is_reverse(direction)
    pad_l, pad_t, pad_r, pad_b = _resolve_padding_for(style, parent.width, parent.height, "padding")
    spacing_v = _to_float(style.get("spacing"))
    if spacing_v is None:
        spacing_v = _to_float(style.get("gap"))
    spacing = spacing_v or 0.0
    align_items = _resolve_align(style.get("align_items"), default=ALIGN_STRETCH)
    justify = _resolve_justify(style.get("justify_content"))

    in_flow: List[LayoutNode] = []
    absolute: List[LayoutNode] = []
    for child in parent.children:
        if child.style.get("position") == POSITION_ABSOLUTE:
            absolute.append(child)
        else:
            in_flow.append(child)

    content_w = max(0.0, parent.width - pad_l - pad_r)
    content_h = max(0.0, parent.height - pad_t - pad_b)
    main_size = content_w if is_row else content_h
    cross_size = content_h if is_row else content_w

    used_main = sum(_child_outer_main(c, is_row, content_w, content_h) for c in in_flow)
    if len(in_flow) > 1:
        used_main += spacing * (len(in_flow) - 1)
    free_main = max(0.0, main_size - used_main)

    main_offset, between = _justify_offsets(justify, free_main, len(in_flow))

    cursor = main_offset
    ordered = list(reversed(in_flow)) if reverse else in_flow
    for i, child in enumerate(ordered):
        cm_l, cm_t, cm_r, cm_b = _resolve_padding_for(child.style, content_w, content_h, "margin")
        margin_main_start = cm_l if is_row else cm_t
        margin_cross_start = cm_t if is_row else cm_l
        margin_cross_end = cm_b if is_row else cm_r

        cross_pos = _align_offset(
            child,
            align_items,
            cross_size,
            is_row,
            margin_cross_start,
            margin_cross_end,
        )

        if is_row:
            child.x = pad_l + cursor + margin_main_start
            child.y = pad_t + cross_pos
        else:
            child.x = pad_l + cross_pos
            child.y = pad_t + cursor + margin_main_start

        cursor += _child_outer_main(child, is_row, content_w, content_h)
        if i < len(ordered) - 1:
            cursor += spacing + between

        _position_children(child)

    for child in absolute:
        _position_absolute(child, content_w, content_h, pad_l, pad_t)
        _position_children(child)


def _justify_offsets(justify: str, free_main: float, n: int) -> Tuple[float, float]:
    """Return ``(leading_offset, between_children)`` for `justify_content`."""
    if n <= 0:
        return 0.0, 0.0
    if justify == JUSTIFY_CENTER:
        return free_main / 2.0, 0.0
    if justify == JUSTIFY_FLEX_END:
        return free_main, 0.0
    if justify == JUSTIFY_SPACE_BETWEEN and n > 1:
        return 0.0, free_main / (n - 1)
    if justify == JUSTIFY_SPACE_BETWEEN:
        return 0.0, 0.0
    if justify == JUSTIFY_SPACE_AROUND:
        each = free_main / n if n > 0 else 0.0
        return each / 2.0, each
    if justify == JUSTIFY_SPACE_EVENLY:
        each = free_main / (n + 1)
        return each, each
    return 0.0, 0.0


def _align_offset(
    child: LayoutNode,
    parent_align: str,
    cross_size: float,
    is_row: bool,
    margin_start: float,
    margin_end: float,
) -> float:
    """Return the cross-axis offset for ``child`` inside its parent."""
    align = _resolve_align(child.style.get("align_self"), default=parent_align)
    if align == ALIGN_AUTO:
        align = parent_align

    child_cross = _child_cross_size(child, is_row)
    margin_cross = margin_start + margin_end
    if align == ALIGN_CENTER:
        return margin_start + max(0.0, (cross_size - child_cross - margin_cross) / 2.0)
    if align == ALIGN_FLEX_END:
        return max(0.0, cross_size - child_cross - margin_end)
    return margin_start


def _position_absolute(
    child: LayoutNode,
    content_w: float,
    content_h: float,
    pad_l: float,
    pad_t: float,
) -> None:
    """Position an absolutely-positioned child via `top` / `left` / etc."""
    style = child.style
    left = _resolve_value(style.get("left"), content_w)
    right = _resolve_value(style.get("right"), content_w)
    top = _resolve_value(style.get("top"), content_h)
    bottom = _resolve_value(style.get("bottom"), content_h)

    if left is not None:
        child.x = pad_l + left
    elif right is not None:
        child.x = pad_l + content_w - right - child.width
    else:
        child.x = pad_l

    if top is not None:
        child.y = pad_t + top
    elif bottom is not None:
        child.y = pad_t + content_h - bottom - child.height
    else:
        child.y = pad_t


# ======================================================================
# Helpers used by the reconciler / native_views layer
# ======================================================================


def extract_layout_style(props: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dict of the layout-relevant entries in ``props``.

    Used by the reconciler when building a `LayoutNode` from an element
    so the layout engine doesn't have to scan unrelated visual props.
    """
    return {k: v for k, v in props.items() if k in LAYOUT_STYLE_KEYS}
