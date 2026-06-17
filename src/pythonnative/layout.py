"""Pure-Python flexbox layout engine.

Computes positions and sizes for every node in a layout tree based on
CSS flexbox-inspired style properties. Inspired by Facebook's Yoga and
React Native's layout system, but implemented entirely in Python so
PythonNative does not depend on a native layout library.

The engine is invoked by the reconciler after each commit pass:

1. The reconciler maintains a parallel
   [`LayoutNode`][pythonnative.layout.LayoutNode] tree (cached across
   passes: clean subtrees keep their nodes, dirty ones are rebuilt).
2. [`calculate_layout`][pythonnative.layout.calculate_layout] is called
   with the viewport size; it recursively determines each node's
   ``(x, y, width, height)`` relative to its parent's coordinate space.
   Nodes that are **not dirty** and are measured under the same
   constraints as the previous pass return their memoized size without
   recursing, which turns full-tree layout into dirty-subtree layout.
3. The reconciler walks the tree again and emits a frame op for each
   native view whose frame actually changed.

The algorithm supports:

- **Flex containers**: ``flex_direction`` (``row``/``column`` and their
  reverse variants), ``justify_content`` (``flex_start`` / ``center`` /
  ``flex_end`` / ``space_between`` / ``space_around`` / ``space_evenly``),
  ``align_items`` (``stretch`` / ``flex_start`` / ``center`` /
  ``flex_end``), and ``align_self`` overrides per child.
- **Wrapping**: ``flex_wrap`` (``nowrap`` / ``wrap`` / ``wrap_reverse``)
  with ``align_content`` controlling how lines share leftover
  cross-axis space (``stretch`` default, plus the justify palette).
- **Direction**: ``direction: "rtl"`` flips row layouts, ``start`` /
  ``end`` edge keys (``margin_start``, ``padding_end``, absolute
  ``start`` / ``end`` insets) resolve against the inherited direction.
- **Sizing**: explicit ``width`` / ``height`` (numbers or percentages),
  ``min_width`` / ``max_width`` / ``min_height`` / ``max_height``
  constraints, ``aspect_ratio``, and content-based sizing via the
  optional ``measure`` callback.
- **Flex distribution**: ``flex`` (RN shorthand for grow factor with
  ``flex_basis: 0``), ``flex_grow``, ``flex_shrink``, ``flex_basis``.
- **Absolute positioning**: ``position: "absolute"`` with ``top``,
  ``right``, ``bottom``, ``left`` (and ``start`` / ``end``) insets.
  Absolute children are positioned relative to the parent's padding box
  and do not participate in flex distribution.
- **Spacing**: ``padding`` / ``margin`` (scalar, dict, or per-edge
  keys), inter-child ``spacing`` (aliases: ``gap``, ``column_gap`` /
  ``row_gap`` per axis).

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
        "flex_wrap",
        "align_self",
        "align_content",
        "position",
        "top",
        "right",
        "bottom",
        "left",
        "start",
        "end",
        "margin",
        "margin_top",
        "margin_bottom",
        "margin_left",
        "margin_right",
        "margin_start",
        "margin_end",
        "margin_horizontal",
        "margin_vertical",
        "padding",
        "padding_top",
        "padding_bottom",
        "padding_left",
        "padding_right",
        "padding_start",
        "padding_end",
        "padding_horizontal",
        "padding_vertical",
        "flex_direction",
        "justify_content",
        "align_items",
        "spacing",
        "gap",
        "row_gap",
        "column_gap",
        "aspect_ratio",
        "direction",
    }
)
"""Style keys that affect layout (and are consumed by the layout engine)."""

# Flex direction values
FLEX_DIRECTION_COLUMN = "column"
FLEX_DIRECTION_COLUMN_REVERSE = "column_reverse"
FLEX_DIRECTION_ROW = "row"
FLEX_DIRECTION_ROW_REVERSE = "row_reverse"

# flex_wrap values
WRAP_NOWRAP = "nowrap"
WRAP_WRAP = "wrap"
WRAP_REVERSE = "wrap_reverse"

# justify_content / align_content values
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

# direction values
DIRECTION_LTR = "ltr"
DIRECTION_RTL = "rtl"

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
    direction: str = DIRECTION_LTR,
) -> Tuple[float, float, float, float]:
    """Resolve padding/margin from `style`, honoring per-edge overrides.

    ``{prefix}_start`` / ``{prefix}_end`` resolve to the left/right
    edge according to ``direction`` and take precedence over the
    physical ``left`` / ``right`` keys (matching React Native).
    """
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

    start = _resolve_value(style.get(f"{prefix}_start"), parent_w)
    end = _resolve_value(style.get(f"{prefix}_end"), parent_w)
    if start is not None:
        if direction == DIRECTION_RTL:
            base_r = start
        else:
            base_l = start
    if end is not None:
        if direction == DIRECTION_RTL:
            base_l = end
        else:
            base_r = end
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
    """Normalize a `justify_content` / `align_content` value, applying aliases."""
    if value is None:
        return JUSTIFY_FLEX_START
    s = str(value)
    return _JUSTIFY_ALIASES.get(s, s)


def _resolve_gaps(style: Dict[str, Any], is_row: bool) -> Tuple[float, float]:
    """Return ``(main_gap, cross_gap)`` for a container.

    ``column_gap`` is the horizontal gap and ``row_gap`` the vertical
    gap (CSS semantics); ``spacing`` / ``gap`` set the main-axis gap
    when the specific key is absent.
    """
    generic = _to_float(style.get("spacing"))
    if generic is None:
        generic = _to_float(style.get("gap"))
    col = _to_float(style.get("column_gap"))
    row = _to_float(style.get("row_gap"))
    if is_row:
        main = col if col is not None else generic
        cross = row
    else:
        main = row if row is not None else generic
        cross = col
    return (main or 0.0, cross or 0.0)


def _wrap_mode(style: Dict[str, Any]) -> str:
    mode = style.get("flex_wrap")
    if mode in (WRAP_WRAP, WRAP_REVERSE):
        return str(mode)
    if mode == "wrap-reverse":
        return WRAP_REVERSE
    return WRAP_NOWRAP


def _resolve_direction(style: Dict[str, Any], inherited: str) -> str:
    own = style.get("direction")
    if own in (DIRECTION_LTR, DIRECTION_RTL):
        return str(own)
    return inherited


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
        dirty: When ``False``, the node may serve repeat measurements
            from its memo (set by the reconciler's incremental-layout
            cache). Fresh nodes start dirty.
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
        "dirty",
        "x",
        "y",
        "width",
        "height",
        "_pn_scroll_axis",
        "_measure_memo",
        "_lines",
        "_direction",
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
        self.dirty: bool = True
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
        # Measurement memo: ``(avail_w, avail_h, forced_w, forced_h,
        # direction, out_w, out_h)`` from the most recent measurement.
        # Served when the node is clean (``dirty == False``) and the
        # inputs match, skipping the entire subtree's flex math.
        self._measure_memo: Optional[Tuple[float, float, Optional[float], Optional[float], str, float, float]] = None
        # Flex lines computed during measurement, consumed by the
        # positioning pass (single-line containers store one line).
        self._lines: Optional[List["_FlexLine"]] = None
        # Resolved direction ("ltr" / "rtl") inherited at measure time.
        self._direction: str = DIRECTION_LTR

    def __repr__(self) -> str:
        return (
            f"LayoutNode(x={self.x:g}, y={self.y:g}, "
            f"w={self.width:g}, h={self.height:g}, "
            f"children={len(self.children)})"
        )


class _FlexLine:
    """One row/column of children produced by line partitioning."""

    __slots__ = ("children", "main_used", "cross_size")

    def __init__(self, children: List[LayoutNode]) -> None:
        self.children = children
        self.main_used: float = 0.0
        self.cross_size: float = 0.0


# ======================================================================
# Public entry point
# ======================================================================


def calculate_layout(
    node: LayoutNode,
    available_width: float,
    available_height: float,
    direction: str = DIRECTION_LTR,
) -> None:
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
        direction: Base writing direction (``"ltr"`` or ``"rtl"``)
            inherited by nodes that don't set their own.
    """
    _measure_node(node, available_width, available_height, direction=direction)
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
    direction: str = DIRECTION_LTR,
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
        direction: Writing direction inherited from the parent.
    """
    style = node.style
    resolved_direction = _resolve_direction(style, direction)

    # Incremental-layout memo: a clean node measured under identical
    # inputs reuses its previous result without recursing; its whole
    # subtree keeps the sizes from the prior pass.
    memo = node._measure_memo
    if (
        memo is not None
        and not node.dirty
        and memo[0] == avail_w
        and memo[1] == avail_h
        and memo[2] == forced_w
        and memo[3] == forced_h
        and memo[4] == resolved_direction
    ):
        node.width = memo[5]
        node.height = memo[6]
        return

    node._direction = resolved_direction

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
    node._measure_memo = (avail_w, avail_h, forced_w, forced_h, resolved_direction, node.width, node.height)


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
    direction = node._direction
    base_w = explicit_w if explicit_w is not None else avail_w
    base_h = explicit_h if explicit_h is not None else avail_h
    pad_l, pad_t, pad_r, pad_b = _resolve_padding_for(style, base_w, base_h, "padding", direction)
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


def _child_margins(
    child: LayoutNode,
    parent_w: float,
    parent_h: float,
    direction: str,
) -> Tuple[float, float, float, float]:
    return _resolve_padding_for(child.style, parent_w, parent_h, "margin", direction)


def _child_outer_main(
    child: LayoutNode,
    is_row: bool,
    parent_w: float,
    parent_h: float,
    direction: str,
) -> float:
    """Main-axis extent including margins."""
    margins = _child_margins(child, parent_w, parent_h, direction)
    margin_main = (margins[0] + margins[2]) if is_row else (margins[1] + margins[3])
    return _child_main_size(child, is_row) + margin_main


def _child_outer_cross(
    child: LayoutNode,
    is_row: bool,
    parent_w: float,
    parent_h: float,
    direction: str,
) -> float:
    margins = _child_margins(child, parent_w, parent_h, direction)
    margin_cross = (margins[1] + margins[3]) if is_row else (margins[0] + margins[2])
    return _child_cross_size(child, is_row) + margin_cross


def _measure_child_flexed(
    child: LayoutNode,
    main_size: Optional[float],
    cross_avail: float,
    cross_force: Optional[float],
    is_row: bool,
    main_bounded: bool,
    direction: str,
) -> None:
    """Re-measure a child with optional forced main-axis size and cross hint."""
    fallback_main = math.inf if not main_bounded else cross_avail
    if is_row:
        avail_w = main_size if main_size is not None else fallback_main
        _measure_node(child, avail_w, cross_avail, forced_w=main_size, forced_h=cross_force, direction=direction)
    else:
        avail_h = main_size if main_size is not None else fallback_main
        _measure_node(child, cross_avail, avail_h, forced_w=cross_force, forced_h=main_size, direction=direction)


def _resolve_cross_force(
    child: LayoutNode,
    parent_align: str,
    cross_avail: float,
    cross_bounded: bool,
    is_row: bool,
    direction: str,
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
    margins = _child_margins(child, cross_avail, cross_avail, direction)
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

    Children are measured, partitioned into flex lines (one line unless
    ``flex_wrap`` is enabled), grown/shrunk per line, and stretched to
    their line's cross size. The computed line structure is stored on
    ``parent._lines`` for the positioning pass.

    Returns ``(used_main, used_cross)``, the total content size used
    by the in-flow children, including inter-child gaps but excluding
    the parent's own padding. The caller adds padding back in for the
    container's outer size.
    """
    style = parent.style
    flex_direction = style.get("flex_direction", FLEX_DIRECTION_COLUMN)
    is_row = _is_row(flex_direction)
    direction = parent._direction

    main_avail = content_w if is_row else content_h
    cross_avail = content_h if is_row else content_w
    main_gap, cross_gap = _resolve_gaps(style, is_row)
    wrap = _wrap_mode(style)
    wrapping = wrap != WRAP_NOWRAP and main_bounded and math.isfinite(main_avail)

    in_flow: List[LayoutNode] = []
    absolute: List[LayoutNode] = []
    for child in parent.children:
        if child.style.get("position") == POSITION_ABSOLUTE:
            absolute.append(child)
        else:
            in_flow.append(child)

    align_items = _resolve_align(style.get("align_items"), default=ALIGN_STRETCH)

    # ------------------------------------------------------------------
    # Pass 1: initial measurement (basis for grow children, natural
    # size otherwise). Single-line containers stretch against the full
    # cross axis here (matching the nowrap fast path); wrapping
    # containers defer stretching until line cross sizes are known.
    # ------------------------------------------------------------------
    for child in in_flow:
        grow = _flex_grow(child.style)
        basis = _flex_basis(child.style, main_avail)
        cross_force = (
            None
            if wrapping
            else _resolve_cross_force(child, align_items, cross_avail, cross_bounded, is_row, direction)
        )

        if grow > 0:
            initial_main = basis if basis is not None else 0.0
            _measure_child_flexed(child, initial_main, cross_avail, cross_force, is_row, main_bounded, direction)
        elif basis is not None:
            _measure_child_flexed(child, basis, cross_avail, cross_force, is_row, main_bounded, direction)
        else:
            avail_for_child_main = math.inf if not main_bounded else main_avail
            if is_row:
                _measure_node(child, avail_for_child_main, cross_avail, forced_h=cross_force, direction=direction)
            else:
                _measure_node(child, cross_avail, avail_for_child_main, forced_w=cross_force, direction=direction)

    # ------------------------------------------------------------------
    # Pass 2: partition children into flex lines.
    # ------------------------------------------------------------------
    lines: List[_FlexLine] = []
    if wrapping:
        current: List[LayoutNode] = []
        current_main = 0.0
        for child in in_flow:
            outer = _child_outer_main(child, is_row, content_w, content_h, direction)
            extra = outer if not current else outer + main_gap
            if current and current_main + extra > main_avail + 1e-9:
                lines.append(_FlexLine(current))
                current = [child]
                current_main = outer
            else:
                current.append(child)
                current_main += extra
        if current:
            lines.append(_FlexLine(current))
    elif in_flow:
        lines.append(_FlexLine(list(in_flow)))

    # ------------------------------------------------------------------
    # Pass 3: per-line grow / shrink along the main axis.
    # ------------------------------------------------------------------
    for line in lines:
        flex_total = 0.0
        fixed_main_total = 0.0
        flex_basis_total = 0.0
        flex_entries: List[Tuple[LayoutNode, float, Optional[float]]] = []
        for child in line.children:
            grow = _flex_grow(child.style)
            if grow > 0:
                basis = _flex_basis(child.style, main_avail) or 0.0
                margins = _child_margins(child, content_w, content_h, direction)
                margin_main = (margins[0] + margins[2]) if is_row else (margins[1] + margins[3])
                flex_total += grow
                flex_basis_total += basis + margin_main
                flex_entries.append((child, grow, basis))
            else:
                fixed_main_total += _child_outer_main(child, is_row, content_w, content_h, direction)
        if len(line.children) > 1:
            fixed_main_total += main_gap * (len(line.children) - 1)

        if flex_total > 0 and main_bounded and math.isfinite(main_avail):
            remaining = max(0.0, main_avail - fixed_main_total - flex_basis_total)
            for child, grow, basis in flex_entries:
                extra = (grow / flex_total) * remaining
                child_main = (basis or 0.0) + extra
                cross_force = (
                    None
                    if wrapping
                    else _resolve_cross_force(child, align_items, cross_avail, cross_bounded, is_row, direction)
                )
                _measure_child_flexed(child, child_main, cross_avail, cross_force, is_row, main_bounded, direction)

        if main_bounded and math.isfinite(main_avail):
            total_main = sum(_child_outer_main(c, is_row, content_w, content_h, direction) for c in line.children)
            if len(line.children) > 1:
                total_main += main_gap * (len(line.children) - 1)
            overflow = total_main - main_avail
            if overflow > 0:
                shrinks = [(c, _flex_shrink(c.style)) for c in line.children]
                total_shrink = sum(s * _child_main_size(c, is_row) for c, s in shrinks)
                if total_shrink > 0:
                    for child, shrink in shrinks:
                        if shrink <= 0:
                            continue
                        take = (shrink * _child_main_size(child, is_row) / total_shrink) * overflow
                        new_main = max(0.0, _child_main_size(child, is_row) - take)
                        cross_force = (
                            None
                            if wrapping
                            else _resolve_cross_force(child, align_items, cross_avail, cross_bounded, is_row, direction)
                        )
                        _measure_child_flexed(
                            child, new_main, cross_avail, cross_force, is_row, main_bounded, direction
                        )

        line.main_used = sum(_child_outer_main(c, is_row, content_w, content_h, direction) for c in line.children)
        if len(line.children) > 1:
            line.main_used += main_gap * (len(line.children) - 1)

    # ------------------------------------------------------------------
    # Pass 4: line cross sizes (+ align_content stretch) and per-line
    # cross stretching for wrapped containers.
    # ------------------------------------------------------------------
    for line in lines:
        line.cross_size = max(
            (_child_outer_cross(c, is_row, content_w, content_h, direction) for c in line.children),
            default=0.0,
        )

    if wrapping and lines:
        align_content = _resolve_justify(style.get("align_content", "stretch"))
        if align_content == ALIGN_STRETCH and cross_bounded and math.isfinite(cross_avail):
            total_cross = sum(line.cross_size for line in lines) + cross_gap * (len(lines) - 1)
            if total_cross < cross_avail:
                extra_each = (cross_avail - total_cross) / len(lines)
                for line in lines:
                    line.cross_size += extra_each
        for line in lines:
            for child in line.children:
                cross_force = _resolve_cross_force(child, align_items, line.cross_size, True, is_row, direction)
                if cross_force is not None and abs(cross_force - _child_cross_size(child, is_row)) > 1e-9:
                    _measure_child_flexed(
                        child,
                        _child_main_size(child, is_row),
                        line.cross_size,
                        cross_force,
                        is_row,
                        main_bounded,
                        direction,
                    )

    for child in absolute:
        _measure_absolute(child, content_w, content_h, direction)

    parent._lines = lines

    if wrapping:
        used_main = max((line.main_used for line in lines), default=0.0)
        used_cross = sum(line.cross_size for line in lines)
        if len(lines) > 1:
            used_cross += cross_gap * (len(lines) - 1)
    else:
        used_main = lines[0].main_used if lines else 0.0
        used_cross = lines[0].cross_size if lines else 0.0
    return used_main, used_cross


def _measure_absolute(child: LayoutNode, parent_w: float, parent_h: float, direction: str) -> None:
    """Measure an absolutely-positioned child using `top` / `left` / `start` / etc."""
    style = child.style
    explicit_w = _resolve_value(style.get("width"), parent_w)
    explicit_h = _resolve_value(style.get("height"), parent_h)
    left, right = _absolute_horizontal_insets(style, parent_w, direction)
    top = _resolve_value(style.get("top"), parent_h)
    bottom = _resolve_value(style.get("bottom"), parent_h)

    if explicit_w is None and left is not None and right is not None:
        explicit_w = max(0.0, parent_w - left - right)
    if explicit_h is None and top is not None and bottom is not None:
        explicit_h = max(0.0, parent_h - top - bottom)

    avail_w = explicit_w if explicit_w is not None else parent_w
    avail_h = explicit_h if explicit_h is not None else parent_h
    _measure_node(child, avail_w, avail_h, forced_w=explicit_w, forced_h=explicit_h, direction=direction)


def _absolute_horizontal_insets(
    style: Dict[str, Any],
    parent_w: float,
    direction: str,
) -> Tuple[Optional[float], Optional[float]]:
    """Resolve ``left`` / ``right``, honoring ``start`` / ``end`` overrides."""
    left = _resolve_value(style.get("left"), parent_w)
    right = _resolve_value(style.get("right"), parent_w)
    start = _resolve_value(style.get("start"), parent_w)
    end = _resolve_value(style.get("end"), parent_w)
    if start is not None:
        if direction == DIRECTION_RTL:
            right = start
        else:
            left = start
    if end is not None:
        if direction == DIRECTION_RTL:
            left = end
        else:
            right = end
    return left, right


# ======================================================================
# Positioning: bottom-up placement after sizing
# ======================================================================


def _position_children(parent: LayoutNode) -> None:
    """Assign ``x`` / ``y`` to every descendant.

    Sizes are already computed by [`_measure_node`][pythonnative.layout._measure_node];
    this pass walks the same tree and applies ``justify_content`` /
    ``align_items`` / ``align_content`` / absolute positioning to
    determine concrete coordinates relative to each parent's
    coordinate space.
    """
    if not parent.children:
        return

    style = parent.style
    flex_direction = style.get("flex_direction", FLEX_DIRECTION_COLUMN)
    is_row = _is_row(flex_direction)
    direction = parent._direction
    rtl = direction == DIRECTION_RTL
    # In RTL, rows flip their visual order; ``row_reverse`` flips back.
    reverse = _is_reverse(flex_direction) != (rtl and is_row)
    pad_l, pad_t, pad_r, pad_b = _resolve_padding_for(style, parent.width, parent.height, "padding", direction)
    main_gap, cross_gap = _resolve_gaps(style, is_row)
    wrap = _wrap_mode(style)
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

    lines = parent._lines
    if not lines:
        lines = [_FlexLine(list(in_flow))] if in_flow else []
        for line in lines:
            line.main_used = sum(_child_outer_main(c, is_row, content_w, content_h, direction) for c in line.children)
            if len(line.children) > 1:
                line.main_used += main_gap * (len(line.children) - 1)
            line.cross_size = cross_size

    multi_line = wrap != WRAP_NOWRAP and len(lines) >= 1 and parent._lines is not None

    # Cross-axis placement of the lines themselves.
    if multi_line:
        total_lines_cross = sum(line.cross_size for line in lines) + cross_gap * max(0, len(lines) - 1)
        align_content = _resolve_justify(style.get("align_content", "stretch"))
        if align_content == ALIGN_STRETCH:
            align_content = JUSTIFY_FLEX_START
        free_cross = max(0.0, cross_size - total_lines_cross)
        cross_offset, cross_between = _justify_offsets(align_content, free_cross, len(lines))
    else:
        cross_offset, cross_between = 0.0, 0.0

    ordered_lines = list(lines)
    if wrap == WRAP_REVERSE and multi_line:
        ordered_lines.reverse()

    cross_cursor = cross_offset
    for line_index, line in enumerate(ordered_lines):
        line_cross = line.cross_size if multi_line else cross_size
        free_main = max(0.0, main_size - line.main_used)
        main_offset, between = _justify_offsets(justify, free_main, len(line.children))

        cursor = main_offset
        ordered = list(reversed(line.children)) if reverse else list(line.children)
        for i, child in enumerate(ordered):
            cm_l, cm_t, cm_r, cm_b = _child_margins(child, content_w, content_h, direction)
            margin_main_start = (cm_r if rtl else cm_l) if is_row else cm_t
            margin_cross_start = cm_t if is_row else (cm_r if rtl else cm_l)
            margin_cross_end = cm_b if is_row else (cm_l if rtl else cm_r)

            cross_pos = _align_offset(
                child,
                align_items,
                line_cross,
                is_row,
                margin_cross_start,
                margin_cross_end,
                rtl,
            )

            if is_row:
                child.x = pad_l + cursor + margin_main_start
                child.y = pad_t + cross_cursor + cross_pos
            else:
                child.x = pad_l + cross_cursor + cross_pos
                child.y = pad_t + cursor + margin_main_start

            cursor += _child_outer_main(child, is_row, content_w, content_h, direction)
            if i < len(ordered) - 1:
                cursor += main_gap + between

            _position_children(child)

        cross_cursor += line_cross
        if line_index < len(ordered_lines) - 1:
            cross_cursor += cross_gap + cross_between

    for child in absolute:
        _position_absolute(child, content_w, content_h, pad_l, pad_t, direction)
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
    rtl: bool = False,
) -> float:
    """Return the cross-axis offset for ``child`` inside its line."""
    align = _resolve_align(child.style.get("align_self"), default=parent_align)
    if align == ALIGN_AUTO:
        align = parent_align
    # A column's cross axis is horizontal, so RTL flips start/end.
    if rtl and not is_row:
        if align == ALIGN_FLEX_START:
            align = ALIGN_FLEX_END
        elif align == ALIGN_FLEX_END:
            align = ALIGN_FLEX_START

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
    direction: str,
) -> None:
    """Position an absolutely-positioned child via `top` / `left` / `start` / etc."""
    style = child.style
    left, right = _absolute_horizontal_insets(style, content_w, direction)
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
