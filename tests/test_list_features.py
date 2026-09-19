"""Unit tests for the Python-implemented list features: inverted lists, separators, initial index, sticky headers."""

from __future__ import annotations

from typing import Any, List

import pythonnative as pn
from pythonnative.testing import FakeView, render


def _row_wrappers(view: FakeView) -> List[FakeView]:
    """The per-row wrapper views of a mounted ``VirtualList``."""
    return [child for child in view.children if "_pn_list_key" in child.props]


# ======================================================================
# inverted
# ======================================================================


def test_inverted_flat_list_mirrors_the_container_and_every_row() -> None:
    result = render(pn.FlatList(data=["a", "b"], item_height=20, inverted=True, style={"transform": [{"scale": 1}]}))
    view = result.get_by_type("VirtualList")
    assert view.props["transform"] == [{"scale": 1}, {"scale_y": -1}]
    rows = _row_wrappers(view)
    assert len(rows) == 2
    assert all(row.props["transform"] == [{"scale_y": -1}] for row in rows)
    result.unmount()


def test_inverted_horizontal_list_mirrors_the_x_axis() -> None:
    result = render(pn.FlatList(data=["a"], horizontal=True, inverted=True))
    view = result.get_by_type("VirtualList")
    assert view.props["transform"] == [{"scale_x": -1}]
    assert _row_wrappers(view)[0].props["transform"] == [{"scale_x": -1}]
    result.unmount()


def test_non_inverted_list_has_no_transform() -> None:
    result = render(pn.FlatList(data=["a"]))
    view = result.get_by_type("VirtualList")
    assert "transform" not in view.props
    assert "transform" not in _row_wrappers(view)[0].props
    result.unmount()


# ======================================================================
# item_separator
# ======================================================================


def test_item_separator_element_is_appended_after_every_row_except_the_last() -> None:
    result = render(
        pn.FlatList(
            data=["a", "b", "c"],
            render_item=lambda item, _i: pn.Text(item),
            item_separator=pn.View(test_id="sep", style={"height": 1}),
        )
    )
    view = result.get_by_type("VirtualList")
    rows = _row_wrappers(view)
    separators = [row.find_all(lambda v: v.test_id == "sep") for row in rows]
    assert [len(found) for found in separators] == [1, 1, 0]
    # The separator follows the item inside each row.
    first = rows[0].find_first("View")
    assert first is not None
    labels = [child.type_name for child in rows[0].find_all(lambda v: v.test_id == "sep" or v.type_name == "Text")]
    assert labels == ["Text", "View"]
    result.unmount()


def test_item_separator_factory_is_called_per_gap() -> None:
    calls: List[int] = []

    def separator() -> pn.Element:
        calls.append(1)
        return pn.View(test_id="sep")

    result = render(pn.FlatList(data=[1, 2, 3, 4], item_separator=separator))
    assert len(calls) == 3
    assert len(result.get_all_by_test_id("sep")) == 3
    result.unmount()


def test_section_list_separators_stay_inside_each_section() -> None:
    result = render(
        pn.SectionList(
            sections=[{"title": "A", "data": ["a1", "a2"]}, {"title": "B", "data": ["b1"]}],
            item_separator=lambda: pn.View(test_id="sep"),
        )
    )
    # Only between a1 and a2: never after a section's last item, never after a header.
    assert len(result.get_all_by_test_id("sep")) == 1
    view = result.get_by_type("VirtualList")
    rows = _row_wrappers(view)
    with_sep = [row.props["_pn_list_key"] for row in rows if row.find_first(lambda v: v.test_id == "sep")]
    assert with_sep == ["__pn_row_0_0__"]
    result.unmount()


# ======================================================================
# initial_scroll_index
# ======================================================================


def test_initial_scroll_index_scrolls_once_after_mount() -> None:
    result = render(pn.FlatList(data=list(range(500)), item_height=44, initial_scroll_index=300))
    view = result.get_by_type("VirtualList")
    scrolls = [(name, args) for _tag, name, args in result.backend.commands if name == "scroll_to_index"]
    assert scrolls == [("scroll_to_index", {"index": 300, "animated": False})]
    texts = {v.props["text"] for v in view.find_all("Text")}
    assert "300" in texts
    assert "0" not in texts
    result.rerender(pn.FlatList(data=list(range(500)), item_height=44, initial_scroll_index=300))
    assert len([c for c in result.backend.commands if c[1] == "scroll_to_index"]) == 1
    result.unmount()


def test_initial_scroll_index_accounts_for_a_list_header() -> None:
    result = render(pn.FlatList(data=["a", "b", "c"], list_header=pn.Text("H"), initial_scroll_index=1))
    (command,) = [c for c in result.backend.commands if c[1] == "scroll_to_index"]
    assert command[2]["index"] == 2  # header row sits at native index 0
    result.unmount()


def test_out_of_range_initial_scroll_index_is_ignored() -> None:
    result = render(pn.FlatList(data=["a"], initial_scroll_index=5))
    assert not [c for c in result.backend.commands if c[1] == "scroll_to_index"]
    result.unmount()


# ======================================================================
# on_scroll delivers ScrollEvent
# ======================================================================


def test_list_on_scroll_delivers_a_scroll_event() -> None:
    events: List[Any] = []
    result = render(pn.FlatList(data=list(range(100)), item_height=30, on_scroll=events.append))
    view = result.get_by_type("VirtualList")
    result.backend.request_list(view.tag, 10, extent=600.0)
    assert events, "on_scroll must fire from the native request"
    event = events[-1]
    assert isinstance(event, pn.ScrollEvent)
    assert event.y == 300.0
    assert event.x == 0.0
    assert event.content_height == 3000.0
    assert event.viewport_height == 600.0
    assert event.content_width == 0.0
    result.unmount()


def test_horizontal_list_on_scroll_reports_x_axis_geometry() -> None:
    events: List[Any] = []
    result = render(pn.FlatList(data=list(range(50)), item_height=100, horizontal=True, on_scroll=events.append))
    view = result.get_by_type("VirtualList")
    result.backend.request_list(view.tag, 5, extent=400.0)
    event = events[-1]
    assert event.x == 500.0 and event.y == 0.0
    assert event.content_width == 5000.0 and event.viewport_width == 400.0
    assert event.content_height == 0.0 and event.viewport_height == 0.0
    result.unmount()


# ======================================================================
# SectionList: sticky headers and viewable items
# ======================================================================

_SECTIONS = [
    {"title": "A", "data": [f"a{i}" for i in range(30)]},
    {"title": "B", "data": [f"b{i}" for i in range(30)]},
]


def _sticky(result: Any) -> List[FakeView]:
    return result.get_all_by_test_id("sticky")


def _overlay_texts(result: Any) -> List[str]:
    return [h.props["text"] for h in _sticky(result) if h.parent and h.parent.props.get("position") == "absolute"]


def _section_list(**kwargs: Any) -> pn.Element:
    return pn.SectionList(
        sections=_SECTIONS,
        item_height=40,
        section_header_height=40,
        render_section_header=lambda section, _i: pn.Text(f"Header {section['title']}", test_id="sticky"),
        sticky_section_headers=True,
        **kwargs,
    )


def test_sticky_header_overlay_shows_the_current_section_while_scrolled_into_it() -> None:
    result = render(_section_list())
    # Mounted at the top: section A's real header is the first row, so no overlay.
    view = result.get_by_type("VirtualList")
    assert view.parent is not None
    assert _overlay_texts(result) == []
    result.backend.request_list(view.tag, 5, extent=400.0)  # a4 at the top
    result.settle()
    assert _overlay_texts(result) == ["Header A"]
    overlay = next(h.parent for h in _sticky(result) if h.parent and h.parent.props.get("position") == "absolute")
    assert overlay.props["top"] == 0 and overlay.props["left"] == 0 and overlay.props["right"] == 0
    assert overlay.parent is view.parent, "the overlay sits beside the list in the wrapper"
    result.unmount()


def test_sticky_header_switches_sections_and_hides_at_a_real_header() -> None:
    result = render(_section_list())
    view = result.get_by_type("VirtualList")
    result.backend.request_list(view.tag, 40, extent=400.0)  # inside section B
    result.settle()
    assert _overlay_texts(result) == ["Header B"]
    result.backend.request_list(view.tag, 31, extent=400.0)  # B's real header at the top
    result.settle()
    assert _overlay_texts(result) == []
    result.unmount()


def test_section_list_without_sticky_headers_renders_the_bare_list() -> None:
    result = render(pn.SectionList(sections=_SECTIONS, item_height=40, style={"height": 300}))
    view = result.get_by_type("VirtualList")
    assert view.props["height"] == 300
    assert not [v for v in result.backend.views.values() if v.props.get("position") == "absolute"]
    result.unmount()


def test_section_list_reports_viewable_items_without_headers() -> None:
    seen: List[Any] = []
    result = render(
        pn.SectionList(
            sections=_SECTIONS, item_height=40, section_header_height=40, on_viewable_items_changed=seen.append
        )
    )
    view = result.get_by_type("VirtualList")
    result.backend.request_list(view.tag, 0, extent=120.0)
    assert seen
    visible = seen[-1]
    assert [entry["item"] for entry in visible] == ["a0", "a1"]
    assert [entry["index"] for entry in visible] == [0, 1]
    result.unmount()


def test_inverted_section_list_mirrors_rows() -> None:
    result = render(pn.SectionList(sections=_SECTIONS[:1], item_height=40, inverted=True))
    view = result.get_by_type("VirtualList")
    assert view.props["transform"] == [{"scale_y": -1}]
    assert all(row.props["transform"] == [{"scale_y": -1}] for row in _row_wrappers(view))
    result.unmount()
