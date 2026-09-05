"""Unit tests for the pure-Python flexbox layout engine."""

import math
from typing import Tuple

import pytest

from pythonnative.layout import (
    LayoutNode,
    calculate_layout,
    extract_layout_style,
)

# ======================================================================
# Helpers
# ======================================================================


def text_measure(width: float, height: float) -> Tuple[float, float]:
    """Stand-in measure that returns a fixed natural size for a leaf."""
    return (min(80.0, width), 20.0)


# ======================================================================
# Sizing: explicit dimensions
# ======================================================================


def test_explicit_dimensions_are_respected() -> None:
    root = LayoutNode(style={"width": 200, "height": 100})
    calculate_layout(root, 320, 480)
    assert (root.x, root.y, root.width, root.height) == (0, 0, 200, 100)


def test_root_with_children_sizes_to_content_when_unsized() -> None:
    # Without a synthetic outer wrapper the root sizes to its
    # children. The reconciler's layout pass wraps user trees in a
    # synthetic viewport node so apps still fill the screen.
    root = LayoutNode(
        style={"flex_direction": "column"},
        children=[LayoutNode(style={"width": 100, "height": 50})],
    )
    calculate_layout(root, 320, 480)
    assert root.width == 100
    assert root.height == 50


def test_root_explicit_size_wins() -> None:
    root = LayoutNode(style={"width": 100, "height": 50})
    calculate_layout(root, 320, 480)
    assert root.width == 100
    assert root.height == 50


def test_root_fills_viewport_when_wrapped() -> None:
    user_root = LayoutNode(
        style={"flex_direction": "column"},
        children=[LayoutNode(style={"height": 30})],
    )
    viewport = LayoutNode(
        style={"width": 320, "height": 480},
        children=[user_root],
    )
    calculate_layout(viewport, 320, 480)
    # User root stretches to viewport on cross axis (default align_items: stretch),
    # and is positioned at the viewport's origin.
    assert user_root.width == 320
    assert user_root.x == 0
    assert user_root.y == 0


def test_percentage_dimensions_resolve_against_parent() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 100},
        children=[LayoutNode(style={"width": "50%", "height": "25%"})],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert child.width == 100
    assert child.height == 25


def test_percentage_collapses_when_parent_unbounded() -> None:
    root = LayoutNode(
        style={"width": 200},
        children=[LayoutNode(style={"width": "50%", "height": "25%"})],
    )
    calculate_layout(root, 200, math.inf)
    child = root.children[0]
    assert child.width == 100
    assert child.height == 0


def test_min_max_constraints_clamp_size() -> None:
    root = LayoutNode(style={"width": 50, "min_width": 100, "max_height": 30, "height": 200})
    calculate_layout(root, 320, 480)
    assert root.width == 100
    assert root.height == 30


def test_aspect_ratio_with_only_width() -> None:
    root = LayoutNode(style={"width": 100, "aspect_ratio": 2.0})
    calculate_layout(root, 320, 480)
    assert root.width == 100
    assert root.height == 50


def test_aspect_ratio_with_only_height() -> None:
    root = LayoutNode(style={"height": 50, "aspect_ratio": 2.0})
    calculate_layout(root, 320, 480)
    assert root.width == 100
    assert root.height == 50


# ======================================================================
# Leaf measurement callback
# ======================================================================


def test_leaf_measure_callback_used_when_no_explicit_size() -> None:
    leaf = LayoutNode(measure=text_measure)
    calculate_layout(leaf, 320, 480)
    assert leaf.width == 80
    assert leaf.height == 20


def test_leaf_explicit_width_overrides_measure() -> None:
    leaf = LayoutNode(style={"width": 150}, measure=text_measure)
    calculate_layout(leaf, 320, 480)
    assert leaf.width == 150
    assert leaf.height == 20


def test_leaf_measure_receives_max_width() -> None:
    captured: list = []

    def measure(w: float, h: float) -> Tuple[float, float]:
        captured.append((w, h))
        return (40.0, 20.0)

    leaf = LayoutNode(measure=measure)
    parent = LayoutNode(style={"width": 100, "height": 50}, children=[leaf])
    calculate_layout(parent, 320, 480)
    assert captured
    assert captured[0][0] <= 100


# ======================================================================
# Column flex layout
# ======================================================================


def test_column_stacks_children_vertically() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "flex_direction": "column"},
        children=[
            LayoutNode(style={"height": 50}),
            LayoutNode(style={"height": 30}),
            LayoutNode(style={"height": 70}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, b, c = root.children
    assert a.y == 0
    assert b.y == 50
    assert c.y == 80


def test_column_default_align_items_stretch() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200},
        children=[LayoutNode(style={"height": 50})],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].width == 100


def test_column_align_items_center() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "align_items": "center"},
        children=[LayoutNode(style={"width": 40, "height": 50})],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert child.x == 30
    assert child.width == 40


def test_column_align_items_flex_end() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "align_items": "flex_end"},
        children=[LayoutNode(style={"width": 40, "height": 50})],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 60


def test_align_self_overrides_parent_align_items() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "align_items": "flex_start"},
        children=[
            LayoutNode(style={"width": 40, "height": 50}),
            LayoutNode(style={"width": 40, "height": 50, "align_self": "flex_end"}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 0
    assert root.children[1].x == 60


# ======================================================================
# Row flex layout
# ======================================================================


def test_row_lays_out_children_horizontally() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50},
        children=[
            LayoutNode(style={"width": 80, "height": 40}),
            LayoutNode(style={"width": 100, "height": 40}),
            LayoutNode(style={"width": 60, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, b, c = root.children
    assert (a.x, a.y) == (0, 0)
    assert (b.x, b.y) == (80, 0)
    assert (c.x, c.y) == (180, 0)


def test_row_align_items_center() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 100, "align_items": "center"},
        children=[LayoutNode(style={"width": 50, "height": 30})],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].y == 35


# ======================================================================
# Flex distribution
# ======================================================================


def test_flex_one_fills_remaining_space() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50},
        children=[
            LayoutNode(style={"width": 80, "height": 40}),
            LayoutNode(style={"flex": 1, "height": 40}),
            LayoutNode(style={"width": 60, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, b, c = root.children
    assert a.width == 80
    assert b.width == 160
    assert c.width == 60
    assert (a.x, b.x, c.x) == (0, 80, 240)


def test_flex_proportional_distribution() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50},
        children=[
            LayoutNode(style={"flex": 1, "height": 40}),
            LayoutNode(style={"flex": 2, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, b = root.children
    assert a.width == 100
    assert b.width == 200


def test_flex_grow_distributes_like_flex() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 200, "height": 50},
        children=[
            LayoutNode(style={"flex_grow": 1, "height": 40}),
            LayoutNode(style={"flex_grow": 1, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].width == 100
    assert root.children[1].width == 100


def test_flex_zero_uses_natural_size() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50},
        children=[
            LayoutNode(style={"flex": 0, "width": 80, "height": 40}),
            LayoutNode(style={"flex": 0, "width": 80, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].width == 80
    assert root.children[1].width == 80


# ======================================================================
# justify_content
# ======================================================================


def test_justify_flex_start_packs_at_start() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "justify_content": "flex_start"},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 0
    assert root.children[1].x == 50


def test_justify_center() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "justify_content": "center"},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 100
    assert root.children[1].x == 150


def test_justify_flex_end() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "justify_content": "flex_end"},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 200
    assert root.children[1].x == 250


def test_justify_space_between() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "justify_content": "space_between"},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 0
    assert root.children[1].x == 125
    assert root.children[2].x == 250


def test_justify_space_around() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "justify_content": "space_around"},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    # Free space = 200; each child gets 100/2 = 50 padding either side.
    assert root.children[0].x == 50
    assert root.children[1].x == 200


def test_justify_space_evenly() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "justify_content": "space_evenly"},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    # Free space = 200; 3 gaps of 200/3 ≈ 66.67.
    assert root.children[0].x == pytest.approx(66.666, rel=1e-3)
    assert root.children[1].x == pytest.approx(183.333, rel=1e-3)


# ======================================================================
# Padding & spacing
# ======================================================================


def test_padding_offsets_children() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 100, "padding": 10},
        children=[LayoutNode(style={"width": 50, "height": 30})],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 10
    assert root.children[0].y == 10


def test_padding_dict_horizontal_vertical() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 100, "padding": {"horizontal": 20, "vertical": 5}},
        children=[LayoutNode(style={"width": 50, "height": 30})],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 20
    assert root.children[0].y == 5


def test_padding_per_edge_keys_override_omnibus() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 100, "padding": 5, "padding_left": 25},
        children=[LayoutNode(style={"width": 50, "height": 30})],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 25
    assert root.children[0].y == 5


def test_spacing_between_children_in_column() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "spacing": 8},
        children=[
            LayoutNode(style={"height": 30}),
            LayoutNode(style={"height": 30}),
            LayoutNode(style={"height": 30}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].y == 0
    assert root.children[1].y == 38
    assert root.children[2].y == 76


def test_gap_alias_for_spacing() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "gap": 4},
        children=[
            LayoutNode(style={"height": 30}),
            LayoutNode(style={"height": 30}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[1].y == 34


# ======================================================================
# Margin
# ======================================================================


def test_child_margin_offsets_position() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 100},
        children=[LayoutNode(style={"width": 50, "height": 30, "margin": 10})],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert child.x == 10
    assert child.y == 10


def test_margin_pushes_siblings_in_column() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 300},
        children=[
            LayoutNode(style={"height": 40, "margin": 10}),
            LayoutNode(style={"height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, b = root.children
    assert a.y == 10
    assert b.y == 60  # 10 (margin top) + 40 (height) + 10 (margin bottom)


def test_margin_dict_per_edge() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 100},
        children=[
            LayoutNode(
                style={
                    "width": 50,
                    "height": 30,
                    "margin": {"left": 5, "top": 8, "right": 5, "bottom": 8},
                }
            )
        ],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert child.x == 5
    assert child.y == 8


# ======================================================================
# Absolute positioning
# ======================================================================


def test_absolute_with_top_left() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 200},
        children=[
            LayoutNode(style={"position": "absolute", "top": 10, "left": 20, "width": 30, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert (child.x, child.y, child.width, child.height) == (20, 10, 30, 40)


def test_absolute_with_right_bottom() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 200},
        children=[
            LayoutNode(style={"position": "absolute", "right": 10, "bottom": 20, "width": 30, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert child.x == 160  # 200 - 10 - 30
    assert child.y == 140  # 200 - 20 - 40


def test_absolute_left_and_right_resolves_width() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 200},
        children=[
            LayoutNode(style={"position": "absolute", "left": 20, "right": 30, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert child.x == 20
    assert child.width == 150  # 200 - 20 - 30


def test_absolute_positioning_respects_parent_padding_box() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 100, "padding": {"left": 10, "right": 20, "top": 5, "bottom": 15}},
        children=[
            LayoutNode(style={"position": "absolute", "right": 10, "bottom": 5, "width": 30, "height": 20}),
            LayoutNode(style={"position": "absolute", "left": 0, "top": 0, "width": 10, "height": 10}),
        ],
    )
    calculate_layout(root, 320, 480)
    right_child, left_child = root.children
    assert right_child.x == 140  # padding_left + content_width - right - width
    assert right_child.y == 60  # padding_top + content_height - bottom - height
    assert left_child.x == 10
    assert left_child.y == 5


def test_absolute_does_not_shift_flex_siblings() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200},
        children=[
            LayoutNode(style={"height": 50}),
            LayoutNode(style={"position": "absolute", "top": 0, "right": 0, "width": 20, "height": 20}),
            LayoutNode(style={"height": 50}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, abs_child, c = root.children
    assert a.y == 0
    assert c.y == 50  # Sibling after absolute is still positioned as if absolute weren't there.
    assert abs_child.x == 80
    assert abs_child.y == 0


# ======================================================================
# Reverse directions
# ======================================================================


def test_row_reverse_lays_out_right_to_left() -> None:
    root = LayoutNode(
        style={"flex_direction": "row_reverse", "width": 300, "height": 50},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    # In CSS flexbox, `row-reverse` flips the visual order: the LAST
    # element appears at the visual start (left), the FIRST element
    # appears at the visual end.
    assert root.children[1].x == 0
    assert root.children[0].x == 50
    visual_order = sorted(root.children, key=lambda c: c.x)
    assert visual_order[0] is root.children[1]
    assert visual_order[1] is root.children[0]


def test_column_reverse_lays_out_bottom_to_top() -> None:
    root = LayoutNode(
        style={"flex_direction": "column_reverse", "width": 100, "height": 300},
        children=[
            LayoutNode(style={"height": 50}),
            LayoutNode(style={"height": 50}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[1].y == 0
    assert root.children[0].y == 50


# ======================================================================
# Nested layouts
# ======================================================================


def test_nested_column_in_row() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 100},
        children=[
            LayoutNode(
                style={"flex_direction": "column", "width": 100, "height": 100},
                children=[
                    LayoutNode(style={"height": 30}),
                    LayoutNode(style={"height": 30}),
                ],
            ),
            LayoutNode(style={"flex": 1, "height": 100}),
        ],
    )
    calculate_layout(root, 320, 480)
    nested = root.children[0]
    flex_sib = root.children[1]
    assert nested.x == 0
    assert nested.children[0].y == 0
    assert nested.children[1].y == 30
    assert flex_sib.x == 100
    assert flex_sib.width == 200


def test_nested_padding_compounds_correctly() -> None:
    root = LayoutNode(
        style={"width": 200, "height": 200, "padding": 10},
        children=[
            LayoutNode(
                style={"padding": 5},
                children=[LayoutNode(style={"width": 30, "height": 20})],
            ),
        ],
    )
    calculate_layout(root, 320, 480)
    inner = root.children[0]
    grandchild = inner.children[0]
    # Outer padding 10, inner padding 5 -> grandchild offset by 15 from root.
    # But x/y are relative to the immediate parent's coordinate space.
    assert inner.x == 10
    assert inner.y == 10
    assert grandchild.x == 5
    assert grandchild.y == 5


# ======================================================================
# Flex-shrink
# ======================================================================


def test_flex_shrink_distributes_overflow() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 100, "height": 50},
        children=[
            LayoutNode(style={"width": 80, "height": 40, "flex_shrink": 1}),
            LayoutNode(style={"width": 80, "height": 40, "flex_shrink": 1}),
        ],
    )
    calculate_layout(root, 320, 480)
    # 160 wants to fit in 100; each shrinks proportionally to its size.
    a, b = root.children
    assert a.width == pytest.approx(50)
    assert b.width == pytest.approx(50)


def test_flex_shorthand_shrinks_when_parent_overflows() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 100, "height": 50},
        children=[
            LayoutNode(style={"flex": 1, "flex_basis": 80, "height": 40}),
            LayoutNode(style={"flex": 1, "flex_basis": 80, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, b = root.children
    assert a.width == pytest.approx(50)
    assert b.width == pytest.approx(50)


def test_flex_shrink_zero_does_not_shrink() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 100, "height": 50},
        children=[
            LayoutNode(style={"width": 80, "height": 40}),
            LayoutNode(style={"width": 80, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].width == 80
    assert root.children[1].width == 80


# ======================================================================
# Unbounded main axis (ScrollView-style)
# ======================================================================


def test_unbounded_height_lets_children_overflow() -> None:
    root = LayoutNode(
        style={"width": 100},
        children=[
            LayoutNode(style={"height": 500}),
            LayoutNode(style={"height": 500}),
        ],
    )
    calculate_layout(root, 320, math.inf)
    assert root.height == 1000
    assert root.children[1].y == 500


def test_unbounded_with_flex_basis_uses_basis() -> None:
    root = LayoutNode(
        style={"flex_direction": "column", "width": 100},
        children=[
            LayoutNode(style={"flex_grow": 1, "flex_basis": 50}),
        ],
    )
    calculate_layout(root, 320, math.inf)
    assert root.children[0].height == 50


def test_unbounded_with_pure_flex_collapses_to_zero() -> None:
    root = LayoutNode(
        style={"flex_direction": "column", "width": 100},
        children=[
            LayoutNode(style={"flex": 1}),
            LayoutNode(style={"height": 30}),
        ],
    )
    calculate_layout(root, 320, math.inf)
    # `flex: 1` (RN shorthand) implies flex_basis: 0, so an unbounded
    # parent gives the flex item zero size; non-flex siblings keep
    # their natural size.
    assert root.children[0].height == 0
    assert root.children[1].height == 30
    assert root.height == 30


# ======================================================================
# Scroll-axis clamping (the marker the reconciler stamps on ScrollView)
# ======================================================================


def test_scroll_axis_y_clamps_container_height_to_parent_avail() -> None:
    """Vertical scroll containers fill the parent's height (don't grow with content).

    Without this clamp the container would size itself to ``used_main``
    (the natural content height), making
    ``UIScrollView.frame.height == contentSize.height`` so the native
    scroll view never has any overflow to actually scroll.
    """
    inner = LayoutNode(style={"width": 100, "height": 1000})
    scroll = LayoutNode(children=[inner])
    scroll._pn_scroll_axis = "y"
    root = LayoutNode(
        style={"flex_direction": "column", "width": 200, "height": 400},
        children=[scroll],
    )
    calculate_layout(root, 200, 400)
    assert scroll.height == 400
    assert inner.height == 1000


def test_scroll_axis_y_still_lets_children_measure_unbounded() -> None:
    scroll = LayoutNode(
        children=[LayoutNode(style={"width": 100, "height": 1500})],
    )
    scroll._pn_scroll_axis = "y"
    root = LayoutNode(
        style={"flex_direction": "column", "width": 200, "height": 300},
        children=[scroll],
    )
    calculate_layout(root, 200, 300)
    assert scroll.children[0].height == 1500


def test_scroll_axis_y_respects_explicit_height() -> None:
    scroll = LayoutNode(
        style={"height": 250},
        children=[LayoutNode(style={"width": 100, "height": 900})],
    )
    scroll._pn_scroll_axis = "y"
    root = LayoutNode(
        style={"flex_direction": "column", "width": 200, "height": 800},
        children=[scroll],
    )
    calculate_layout(root, 200, 800)
    assert scroll.height == 250


def test_scroll_axis_y_with_unbounded_parent_falls_back_to_natural() -> None:
    """Nested scroll containers (parent unbounded) fall back to natural size.

    Matches React Native's behavior: an inner ``ScrollView`` whose
    parent doesn't provide a finite height is treated as a normal
    column; it sizes to its content and isn't independently scrollable.
    """
    inner = LayoutNode(style={"width": 100, "height": 600})
    scroll = LayoutNode(children=[inner])
    scroll._pn_scroll_axis = "y"
    root = LayoutNode(style={"width": 200}, children=[scroll])
    calculate_layout(root, 200, math.inf)
    assert scroll.height == 600


def test_scroll_axis_x_clamps_container_width_to_parent_avail() -> None:
    inner = LayoutNode(style={"width": 1000, "height": 100})
    scroll = LayoutNode(style={"flex_direction": "row"}, children=[inner])
    scroll._pn_scroll_axis = "x"
    root = LayoutNode(
        style={"flex_direction": "column", "width": 400, "height": 200},
        children=[scroll],
    )
    calculate_layout(root, 400, 200)
    assert scroll.width == 400
    assert inner.width == 1000


# ======================================================================
# display: none
# ======================================================================


def test_display_none_child_is_skipped_in_row() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "spacing": 10},
        children=[
            LayoutNode(style={"width": 80, "height": 40}),
            LayoutNode(style={"width": 100, "height": 40, "margin": 20, "display": "none"}),
            LayoutNode(style={"width": 60, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    a, hidden, c = root.children
    assert a.x == 0
    # No size, no gap, no margin from the hidden sibling.
    assert c.x == 90
    assert (hidden.x, hidden.y, hidden.width, hidden.height) == (0, 0, 0, 0)


def test_display_none_zeroes_descendant_frames() -> None:
    grandchild = LayoutNode(style={"width": 30, "height": 30})
    hidden = LayoutNode(style={"display": "none", "padding": 10}, children=[grandchild])
    root = LayoutNode(style={"width": 100, "height": 100}, children=[hidden])
    calculate_layout(root, 320, 480)
    assert (hidden.width, hidden.height) == (0, 0)
    assert (grandchild.x, grandchild.y, grandchild.width, grandchild.height) == (0, 0, 0, 0)


def test_display_none_does_not_contribute_to_content_size() -> None:
    root = LayoutNode(
        style={"width": 100},
        children=[
            LayoutNode(style={"height": 30}),
            LayoutNode(style={"height": 500, "display": "none"}),
        ],
    )
    calculate_layout(root, 320, math.inf)
    assert root.height == 30


def test_display_none_absolute_child_is_skipped() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 100},
        children=[
            LayoutNode(
                style={"position": "absolute", "top": 10, "left": 10, "width": 20, "height": 20, "display": "none"},
            ),
        ],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert (child.x, child.y, child.width, child.height) == (0, 0, 0, 0)


def test_display_toggles_back_to_flex_after_relayout() -> None:
    child = LayoutNode(style={"height": 40, "display": "none"})
    root = LayoutNode(style={"width": 100, "height": 100}, children=[child])
    calculate_layout(root, 320, 480)
    assert (child.width, child.height) == (0, 0)
    child.style["display"] = "flex"
    child.dirty = True
    calculate_layout(root, 320, 480)
    assert (child.width, child.height) == (100, 40)


def test_display_none_root_gets_zero_frame() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 100, "display": "none"},
        children=[LayoutNode(style={"height": 10})],
    )
    calculate_layout(root, 320, 480)
    assert (root.width, root.height) == (0, 0)
    assert (root.children[0].width, root.children[0].height) == (0, 0)


# ======================================================================
# Auto margins
# ======================================================================


def test_margin_left_auto_pushes_child_to_end() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50},
        children=[
            LayoutNode(style={"width": 50, "height": 40}),
            LayoutNode(style={"width": 50, "height": 40, "margin_left": "auto"}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 0
    assert root.children[1].x == 250


def test_margin_auto_on_two_children_spaces_them_evenly() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50},
        children=[
            LayoutNode(style={"width": 50, "height": 40, "margin": "auto"}),
            LayoutNode(style={"width": 50, "height": 40, "margin": "auto"}),
        ],
    )
    calculate_layout(root, 320, 480)
    # Free space 200 split across four auto margins: 50 each.
    a, b = root.children
    assert a.x == 50
    assert b.x == 200
    # Vertical auto margins center on the cross axis too.
    assert a.y == 5
    assert b.y == 5


def test_main_axis_auto_margins_override_justify_content() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50, "justify_content": "flex_end"},
        children=[
            LayoutNode(style={"width": 50, "height": 40, "margin_right": "auto"}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 0
    assert root.children[1].x == 250


def test_column_main_axis_auto_margin_pushes_to_bottom() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 300},
        children=[
            LayoutNode(style={"height": 40}),
            LayoutNode(style={"height": 40, "margin_top": "auto"}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[1].y == 260


def test_cross_axis_auto_margins_center_and_disable_stretch() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "align_items": "flex_start"},
        children=[
            LayoutNode(style={"width": 40, "height": 50, "margin_horizontal": "auto"}),
            LayoutNode(style={"height": 50, "margin": {"horizontal": "auto"}}, measure=text_measure),
        ],
    )
    calculate_layout(root, 320, 480)
    centered, measured = root.children
    assert centered.x == 30
    # Auto margins override align_items: stretch is skipped and the leaf
    # keeps its natural 80pt width, centered in the 100pt column.
    assert measured.width == 80
    assert measured.x == 10


def test_single_cross_axis_auto_margin_pushes_to_opposite_edge() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 200, "align_items": "flex_start"},
        children=[LayoutNode(style={"width": 40, "height": 50, "margin_left": "auto"})],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].x == 60

    row = LayoutNode(
        style={"flex_direction": "row", "width": 200, "height": 100, "align_items": "center"},
        children=[LayoutNode(style={"width": 40, "height": 30, "margin_top": "auto"})],
    )
    calculate_layout(row, 320, 480)
    assert row.children[0].y == 70


def test_auto_margin_is_not_parsed_as_zero_when_explicit_edge_overrides() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 50},
        children=[LayoutNode(style={"width": 50, "height": 40, "margin": "auto", "margin_left": 10})],
    )
    calculate_layout(root, 320, 480)
    # Only the right margin stays auto, so the child sits at its explicit left margin.
    assert root.children[0].x == 10


# ======================================================================
# Baseline alignment
# ======================================================================


def test_align_items_baseline_aligns_leaf_bottoms() -> None:
    def measure_short(w: float, h: float) -> Tuple[float, float]:
        return (50.0, 20.0)

    def measure_tall(w: float, h: float) -> Tuple[float, float]:
        return (50.0, 40.0)

    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "align_items": "baseline"},
        children=[
            LayoutNode(measure=measure_short),
            LayoutNode(measure=measure_tall),
        ],
    )
    calculate_layout(root, 320, 480)
    short, tall = root.children
    # A leaf's baseline is its height, so baselines coincide at y == 40.
    assert short.y == 20
    assert tall.y == 0
    assert root.height == 40


def test_baseline_uses_first_child_of_container_and_grows_line() -> None:
    def measure_tall(w: float, h: float) -> Tuple[float, float]:
        return (50.0, 40.0)

    container = LayoutNode(
        style={"width": 60, "height": 60, "padding_top": 5},
        children=[LayoutNode(style={"height": 10}), LayoutNode(style={"height": 30})],
    )
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "align_items": "baseline"},
        children=[LayoutNode(measure=measure_tall), container],
    )
    calculate_layout(root, 320, 480)
    leaf = root.children[0]
    # Container baseline = padding_top (5) + first child's baseline (10) = 15,
    # so it moves down to meet the leaf's baseline at y == 40.
    assert leaf.y == 0
    assert container.y == 25
    # Line height covers the max ascent (40) plus the container's descent (60 - 15).
    assert root.height == 85
    assert container.children[0].y == 5


def test_align_self_baseline_on_single_child_is_flex_start() -> None:
    root = LayoutNode(
        style={"flex_direction": "row", "width": 300, "height": 100, "align_items": "center"},
        children=[
            LayoutNode(style={"width": 50, "height": 20, "align_self": "baseline"}),
            LayoutNode(style={"width": 50, "height": 40}),
        ],
    )
    calculate_layout(root, 320, 480)
    assert root.children[0].y == 0
    assert root.children[1].y == 30


# ======================================================================
# Borders in the box model
# ======================================================================


def test_border_width_offsets_children_like_padding() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 100, "border_width": 4},
        children=[LayoutNode(style={"height": 30})],
    )
    calculate_layout(root, 320, 480)
    child = root.children[0]
    assert (child.x, child.y) == (4, 4)
    assert child.width == 92


def test_border_and_padding_add_to_content_size() -> None:
    root = LayoutNode(
        style={"padding": 10, "border_width": 2},
        children=[LayoutNode(style={"width": 50, "height": 30})],
    )
    calculate_layout(root, 320, 480)
    assert root.width == 74
    assert root.height == 54
    assert (root.children[0].x, root.children[0].y) == (12, 12)


def test_per_edge_border_width_overrides_uniform() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 100, "border_width": 2, "border_left_width": 10, "border_top_width": 0},
        children=[LayoutNode(style={"width": 20, "height": 20})],
    )
    calculate_layout(root, 320, 480)
    assert (root.children[0].x, root.children[0].y) == (10, 0)


def test_absolute_children_position_inside_border() -> None:
    root = LayoutNode(
        style={"width": 100, "height": 100, "border_width": 4},
        children=[
            LayoutNode(style={"position": "absolute", "top": 0, "left": 0, "width": 10, "height": 10}),
            LayoutNode(style={"position": "absolute", "bottom": 0, "right": 0, "width": 10, "height": 10}),
        ],
    )
    calculate_layout(root, 320, 480)
    top_left, bottom_right = root.children
    assert (top_left.x, top_left.y) == (4, 4)
    assert (bottom_right.x, bottom_right.y) == (86, 86)


# ======================================================================
# extract_layout_style helper
# ======================================================================


def test_extract_layout_style_keeps_only_layout_keys() -> None:
    props = {
        "width": 100,
        "height": 50,
        "color": "#FF0000",
        "text": "Hello",
        "padding": 8,
        "background_color": "#EEE",
        "flex": 1,
    }
    style = extract_layout_style(props)
    assert style == {"width": 100, "height": 50, "padding": 8, "flex": 1}


def test_extract_layout_style_includes_display_and_border_widths() -> None:
    props = {"display": "none", "border_width": 2, "border_left_width": 4, "border_color": "#000"}
    assert extract_layout_style(props) == {"display": "none", "border_width": 2, "border_left_width": 4}
