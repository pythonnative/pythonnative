"""Unit tests for natively virtualized lists.

Covers the ``VirtualList`` routing in FlatList / SectionList (gated by
``pythonnative.components._native_lists_supported``), the ``_NativeList``
composite's scroll-derived callbacks and imperative controller, and the
nested-reconciler row subtrees in ``pythonnative.virtual_rows``.
"""

from __future__ import annotations

from typing import Any, List, Tuple

import pytest
from fake_backend import FakeBackend

import pythonnative.components as components
from pythonnative.components import FlatList, SectionList, Text
from pythonnative.element import Element
from pythonnative.events import dispatch_event
from pythonnative.native_views import set_registry
from pythonnative.reconciler import Reconciler
from pythonnative.virtual_rows import RowHostPool, RowSubtree


@pytest.fixture()
def native_lists(monkeypatch: Any) -> None:
    """Force the native list gate open (off-device it is closed)."""
    monkeypatch.setattr(components, "_native_lists_supported", lambda: True)


def _mount(el: Element) -> Tuple[Any, Reconciler, FakeBackend]:
    backend = FakeBackend()
    rec = Reconciler(backend)
    rec._screen_re_render = lambda: None
    root = rec.mount(el)
    return root, rec, backend


# ======================================================================
# Routing
# ======================================================================


def test_flatlist_routes_native_with_fixed_heights(native_lists: None) -> None:
    el = FlatList(
        data=list(range(100)),
        item_height=44,
        render_item=lambda item, _i: Text(f"row-{item}"),
    )
    root, _rec, _backend = _mount(el)
    assert root.type_name == "VirtualList"
    assert root.props["count"] == 100
    assert root.props["row_height"] == 44.0
    assert callable(root.props["render_row"])
    # No rows are mounted eagerly; the platform asks for them lazily.
    assert root.find_all("Text") == []


def test_flatlist_stays_windowed_without_fixed_heights(native_lists: None) -> None:
    el = FlatList(
        data=list(range(10)),
        render_item=lambda item, _i: Text(str(item)),
    )
    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"


def test_flatlist_stays_windowed_with_ornaments(native_lists: None) -> None:
    el = FlatList(
        data=list(range(10)),
        item_height=44,
        list_header=Text("header"),
    )
    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"


def test_flatlist_stays_windowed_with_refresh_control(native_lists: None) -> None:
    el = FlatList(
        data=list(range(10)),
        item_height=44,
        refresh_control={"refreshing": False, "on_refresh": lambda: None},
    )
    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"


def test_flatlist_stays_windowed_for_grids_and_horizontal(native_lists: None) -> None:
    grid = FlatList(data=list(range(10)), item_height=44, num_columns=2)
    root, _rec, _backend = _mount(grid)
    assert root.type_name == "ScrollView"

    horizontal = FlatList(data=list(range(10)), item_height=44, horizontal=True)
    root, _rec, _backend = _mount(horizontal)
    assert root.type_name == "ScrollView"


def test_flatlist_windowed_without_native_support() -> None:
    el = FlatList(data=list(range(10)), item_height=44)
    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"


def test_sectionlist_routes_native_with_per_row_heights(native_lists: None) -> None:
    el = SectionList(
        sections=[
            {"title": "A", "data": [1, 2]},
            {"title": "B", "data": [3]},
        ],
        item_height=40,
        section_header_height=30,
        render_item=lambda item, _i, _s: Text(str(item)),
    )
    root, _rec, _backend = _mount(el)
    assert root.type_name == "VirtualList"
    assert root.props["count"] == 5
    assert root.props["row_heights"] == [30.0, 40.0, 40.0, 30.0, 40.0]


def test_sectionlist_stays_windowed_without_header_height(native_lists: None) -> None:
    el = SectionList(
        sections=[{"title": "A", "data": [1, 2]}],
        item_height=40,
    )
    root, _rec, _backend = _mount(el)
    assert root.type_name == "ScrollView"


# ======================================================================
# render_row and row subtrees
# ======================================================================


def test_render_row_produces_mountable_row_elements(native_lists: None) -> None:
    el = FlatList(
        data=list(range(20)),
        item_height=44,
        render_item=lambda item, _i: Text(f"row-{item}"),
    )
    root, _rec, _backend = _mount(el)
    render_row = root.props["render_row"]

    row_backend = FakeBackend()
    set_registry(row_backend)  # type: ignore[arg-type]
    try:
        subtree = RowSubtree()
        row_root = subtree.mount(render_row(5), 320.0, 44.0)
        assert row_root is not None
        texts = [v.props["text"] for v in row_root.find_all("Text")]
        assert texts == ["row-5"]
        subtree.unmount()
        assert row_backend.live_view_count() == 0
    finally:
        set_registry(None)


def test_row_host_pool_bind_rebind_release() -> None:
    backend = FakeBackend()
    set_registry(backend)  # type: ignore[arg-type]
    try:
        pool = RowHostPool()
        root_a = pool.bind(1, lambda: Text("a"), 320.0, 44.0)
        assert root_a.props["text"] == "a"
        assert len(pool) == 1

        # Rebinding the same container reconciles in place: the row's
        # native view survives with updated props.
        root_b = pool.bind(1, lambda: Text("b"), 320.0, 44.0)
        assert root_b is root_a
        assert root_b.props["text"] == "b"
        assert len(pool) == 1

        pool.bind(2, lambda: Text("c"), 320.0, 44.0)
        assert len(pool) == 2

        pool.release(1)
        assert len(pool) == 1
        pool.release_all()
        assert len(pool) == 0
        assert backend.live_view_count() == 0
    finally:
        set_registry(None)


def test_row_subtree_state_re_renders_row() -> None:
    from pythonnative.hooks import component, use_state

    setters: List[Any] = []

    @component
    def Counter(**_props: Any) -> Element:
        count, set_count = use_state(0)
        setters.append(set_count)
        return Text(f"count-{count}")

    backend = FakeBackend()
    set_registry(backend)  # type: ignore[arg-type]
    try:
        subtree = RowSubtree()
        row_root = subtree.mount(Counter(), 320.0, 44.0)
        assert row_root.props["text"] == "count-0"

        setters[-1](1)
        assert row_root.props["text"] == "count-1"
        subtree.unmount()
    finally:
        set_registry(None)


# ======================================================================
# Scroll-derived callbacks
# ======================================================================


def test_native_list_end_reached_fires_once(native_lists: None) -> None:
    calls: List[int] = []
    el = FlatList(
        data=list(range(100)),  # 100 rows x 44pt = 4400pt total
        item_height=44,
        on_end_reached=lambda: calls.append(1),
    )
    _root, rec, _backend = _mount(el)
    tag = rec.root_tag()

    # Far from the end: no callback.
    assert dispatch_event(tag, "on_scroll", {"y": 0.0, "extent": 800.0, "range": 4400.0}) is True
    assert calls == []

    # Within half a viewport of the end: fires exactly once, even for
    # repeated scroll events in the same region.
    dispatch_event(tag, "on_scroll", {"y": 3400.0, "extent": 800.0, "range": 4400.0})
    dispatch_event(tag, "on_scroll", {"y": 3500.0, "extent": 800.0, "range": 4400.0})
    assert calls == [1]


def test_native_list_viewable_items_changed(native_lists: None) -> None:
    seen: List[List[int]] = []
    el = FlatList(
        data=list(range(100)),
        item_height=44,
        key_extractor=lambda item, _i: str(item),
        on_viewable_items_changed=lambda infos: seen.append([i["index"] for i in infos]),
    )
    _root, rec, _backend = _mount(el)
    tag = rec.root_tag()

    dispatch_event(tag, "on_scroll", {"y": 0.0, "extent": 440.0, "range": 4400.0})
    assert seen, "initial scroll must report the visible rows"
    assert seen[-1][0] == 0

    dispatch_event(tag, "on_scroll", {"y": 2200.0, "extent": 440.0, "range": 4400.0})
    assert seen[-1][0] == 50


def test_native_list_forwards_user_on_scroll(native_lists: None) -> None:
    payloads: List[Any] = []
    el = FlatList(
        data=list(range(100)),
        item_height=44,
        on_scroll=lambda payload: payloads.append(payload),
    )
    _root, rec, _backend = _mount(el)
    dispatch_event(rec.root_tag(), "on_scroll", {"y": 123.0, "extent": 800.0, "range": 4400.0})
    assert payloads == [{"x": 0.0, "y": 123.0}]


# ======================================================================
# Imperative controller
# ======================================================================


def test_native_list_controller_dispatches_commands(native_lists: None) -> None:
    ref: dict = {"current": None}
    el = FlatList(data=list(range(50)), item_height=20, ref=ref)
    _root, _rec, backend = _mount(el)

    assert callable(ref["scroll_to_index"])
    assert callable(ref["scroll_to_offset"])
    assert callable(ref["scroll_to_end"])

    set_registry(backend)  # type: ignore[arg-type]
    try:
        ref["scroll_to_index"](3, animated=False)
        ref["scroll_to_offset"](120.0)
        ref["scroll_to_end"]()
    finally:
        set_registry(None)

    names = [(name, args) for _tag, name, args in backend.commands]
    assert names[0] == ("scroll_to_index", {"index": 3, "animated": False})
    assert names[1] == ("scroll_to_offset", {"y": 120.0, "animated": True})
    assert names[2] == ("scroll_to_end", {"animated": True})
