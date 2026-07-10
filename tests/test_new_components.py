"""Unit tests for the new components: StatusBar, KeyboardAvoidingView, Picker, Sectionlist, etc."""

from __future__ import annotations

from typing import Any, Tuple

from fake_backend import FakeBackend

from pythonnative.components import (
    FlatList,
    KeyboardAvoidingView,
    Picker,
    RefreshControl,
    SectionList,
    StatusBar,
    Text,
)
from pythonnative.element import Element
from pythonnative.reconciler import Reconciler


def _mount(el: Element) -> Tuple[Any, Reconciler, FakeBackend]:
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None
    root = rec.mount(el)
    return root, rec, backend


# ======================================================================
# StatusBar
# ======================================================================


def test_status_bar_default() -> None:
    el = StatusBar()
    assert el.type == "StatusBar"
    assert el.children == []
    assert el.props == {}


def test_status_bar_style_and_hidden() -> None:
    el = StatusBar(bar_style="dark", background_color="#FFFFFF", hidden=False)
    assert el.props["bar_style"] == "dark"
    assert el.props["background_color"] == "#FFFFFF"
    assert el.props["hidden"] is False


# ======================================================================
# KeyboardAvoidingView
# ======================================================================


def test_keyboard_avoiding_default_behavior() -> None:
    el = KeyboardAvoidingView(Text("hi"))
    assert callable(el.type)  # hook-driven composite
    assert el.props["behavior"] == "padding"
    assert len(el.props["children"]) == 1

    _, _, backend = _mount(el)
    inner = [v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView"]
    assert len(inner) == 1


def test_keyboard_avoiding_custom_behavior() -> None:
    el = KeyboardAvoidingView(Text("hi"), behavior="position")
    assert el.props["behavior"] == "position"


def test_keyboard_avoiding_padding_follows_keyboard_height() -> None:
    from pythonnative import platform_metrics

    platform_metrics.reset_keyboard_height()
    try:
        _, rec, backend = _mount(KeyboardAvoidingView(Text("hi"), style={"padding_bottom": 4}))
        view = next(v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView")
        assert view.props.get("padding_bottom") == 4

        platform_metrics.set_keyboard_height(250.0)
        rec.flush_dirty()
        view = next(v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView")
        assert view.props.get("padding_bottom") == 254.0

        platform_metrics.set_keyboard_height(0.0)
        rec.flush_dirty()
        view = next(v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView")
        assert view.props.get("padding_bottom") == 4
    finally:
        platform_metrics.reset_keyboard_height()


def test_keyboard_avoiding_position_translates_upward() -> None:
    from pythonnative import platform_metrics

    platform_metrics.reset_keyboard_height()
    try:
        _, rec, backend = _mount(KeyboardAvoidingView(Text("hi"), behavior="position", keyboard_vertical_offset=50.0))
        platform_metrics.set_keyboard_height(250.0)
        rec.flush_dirty()
        view = next(v for v in backend.views.values() if v.type_name == "KeyboardAvoidingView")
        assert view.props.get("transform") == [{"translate_y": -200.0}]
    finally:
        platform_metrics.reset_keyboard_height()


# ======================================================================
# RefreshControl
# ======================================================================


def test_refresh_control_dict_shape() -> None:
    cb = lambda: None  # noqa: E731
    spec = RefreshControl(refreshing=True, on_refresh=cb, tint_color="#FF0000")
    assert isinstance(spec, dict)
    assert spec["refreshing"] is True
    assert spec["on_refresh"] is cb
    assert spec["tint_color"] == "#FF0000"


def test_refresh_control_minimal() -> None:
    spec = RefreshControl()
    assert spec == {"refreshing": False}


# ======================================================================
# Picker
# ======================================================================


def test_picker_creates_native_picker_element() -> None:
    cb = lambda _: None  # noqa: E731
    el = Picker(
        value="b",
        items=[
            {"value": "a", "label": "Apple"},
            {"value": "b", "label": "Banana"},
        ],
        on_change=cb,
    )
    assert el.type == "Picker"
    assert el.props["value"] == "b"
    assert el.props["on_change"] is cb
    assert el.props["items"] == [
        {"value": "a", "label": "Apple"},
        {"value": "b", "label": "Banana"},
    ]


def test_picker_default_placeholder_in_props() -> None:
    el = Picker(items=[{"value": "a", "label": "Apple"}])
    assert el.props["placeholder"] == "Select…"
    assert el.props["items"] == [{"value": "a", "label": "Apple"}]


def test_picker_empty_when_no_items() -> None:
    el = Picker()
    assert el.props["items"] == []


# ======================================================================
# Virtualized FlatList (Python-windowed over ScrollView)
# ======================================================================


def test_flatlist_small_list_mounts_every_row() -> None:
    items = [{"id": i, "name": f"Item {i}"} for i in range(3)]
    el = FlatList(
        data=items,
        render_item=lambda item, _i: Text(item["name"]),
        key_extractor=lambda item, _i: str(item["id"]),
    )
    rows = el.props["rows"]
    assert [r.key for r in rows] == ["0", "1", "2"]

    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"
    texts = [v.props["text"] for v in root.find_all("Text")]
    assert texts == ["Item 0", "Item 1", "Item 2"]


def test_flatlist_windows_large_lists() -> None:
    items = list(range(1000))
    el = FlatList(
        data=items,
        item_height=44,
        render_item=lambda item, _i: Text(f"row-{item}"),
        key_extractor=lambda item, _i: str(item),
    )
    rows = el.props["rows"]
    assert len(rows) == 1000
    assert rows[0].extent == 44.0

    root, _rec, _backend = _mount(el)
    mounted = root.find_all("Text")
    # Only the initial window (plus overscan) is mounted, not all 1000.
    assert 0 < len(mounted) < 200
    texts = {v.props["text"] for v in mounted}
    assert "row-0" in texts
    assert "row-999" not in texts


def test_flatlist_window_shifts_on_scroll() -> None:
    from pythonnative.events import dispatch_event

    items = list(range(500))
    el = FlatList(
        data=items,
        item_height=44,
        render_item=lambda item, _i: Text(f"row-{item}"),
        key_extractor=lambda item, _i: str(item),
    )
    root, rec, _backend = _mount(el)
    assert "row-0" in {v.props["text"] for v in root.find_all("Text")}

    # Simulate the native scroll event landing deep in the list, then
    # flush the dirty component to re-render the shifted window.
    scroll_tag = rec.root_tag()
    assert dispatch_event(scroll_tag, "on_scroll", {"x": 0.0, "y": 44.0 * 300}) is True
    rec.flush_dirty()

    texts = {v.props["text"] for v in root.find_all("Text")}
    assert "row-300" in texts
    assert "row-0" not in texts, "rows far behind the window must be unmounted"


def test_flatlist_separator_adds_to_row_extent() -> None:
    el = FlatList(
        data=[1, 2, 3],
        item_height=20,
        separator_height=4,
    )
    assert [r.extent for r in el.props["rows"]] == [24.0, 24.0, 24.0]
    assert el.props["estimated_row_extent"] == 24.0


def test_flatlist_with_refresh_control() -> None:
    el = FlatList(
        data=[1, 2],
        item_height=20,
        refresh_control={"refreshing": True, "on_refresh": lambda: None},
    )
    assert el.props["refresh_control"]["refreshing"] is True

    # The spec flows through to the mounted ScrollView (callback hoisted
    # to the event registry, data props kept).
    root, _rec, _backend = _mount(el)
    assert root.props["refresh_control"] == {"refreshing": True}
    assert "on_refresh" in root.props["_pn_events"]


def test_flatlist_scroll_controller_attached_to_ref() -> None:
    from pythonnative.hooks import Ref
    from pythonnative.native_views import set_registry

    ref: Ref = Ref()
    el = FlatList(data=[1, 2, 3], item_height=20, ref=ref)
    _root, _rec, backend = _mount(el)

    controller = ref.current
    assert controller is not None, "mount must publish a ListController on the ref"

    # Imperative scroll commands resolve through the process registry.
    set_registry(backend)  # type: ignore[arg-type]
    try:
        controller.scroll_to_index(2, animated=False)
    finally:
        set_registry(None)
    assert backend.commands, "scroll_to_index must dispatch a native command"
    _tag, name, args = backend.commands[-1]
    assert name == "scroll_to_offset"
    assert args["y"] == 40.0  # two rows of 20pt scrolled past


# ======================================================================
# SectionList
# ======================================================================


def test_section_list_flattens_headers_and_items() -> None:
    sections = [
        {"title": "A", "data": ["a1", "a2"]},
        {"title": "B", "data": ["b1"]},
    ]
    el = SectionList(sections=sections)
    # 2 headers + 3 items = 5 rows.
    assert len(el.props["rows"]) == 5

    root, _rec, _backend = _mount(el)
    texts = [v.props["text"] for v in root.find_all("Text")]
    assert texts == ["A", "a1", "a2", "B", "b1"]


def test_section_list_header_and_item_extents() -> None:
    sections = [
        {"title": "X", "data": list(range(50))},
        {"title": "Y", "data": list(range(50))},
    ]
    el = SectionList(sections=sections, item_height=30, section_header_height=40)
    rows = el.props["rows"]
    # 2 headers + 100 items.
    assert len(rows) == 102
    assert rows[0].extent == 40.0  # header
    assert rows[1].extent == 30.0  # item

    # Large flattened list still windows.
    root, _rec, _backend = _mount(el)
    assert 0 < len(root.find_all("Text")) < 102
