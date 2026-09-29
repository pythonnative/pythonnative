"""Logical list ownership under native recycling requests."""

from typing import Any

import pytest

import pythonnative as pn
from pythonnative.testing import render


def test_rows_inherit_provider_and_keep_state_by_key() -> None:
    theme = pn.create_context("default")
    setters = {}

    @pn.component
    def Row(item: Any) -> pn.Element:
        value, setter = pn.use_state(item["label"])
        setters[item["id"]] = setter
        return pn.Text(f"{item['label']}/{value}/{pn.use_context(theme)}")

    def tree(data: list[dict[str, str]]) -> pn.Element:
        return theme.Provider(
            pn.FlatList(data=data, key_extractor=lambda item, _: item["id"], render_item=lambda item, _: Row(item)),
            value="inherited",
        )

    result = render(tree([{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]))
    assert result.get_by_text("A/A/inherited")
    setters["a"]("edited")
    result.rerender(tree([{"id": "b", "label": "B2"}, {"id": "a", "label": "A2"}]))
    assert result.get_by_text("A2/edited/inherited")
    assert result.get_by_text("B2/B/inherited")


def test_same_length_data_edits_advance_native_revision() -> None:
    result = render(pn.FlatList(data=["a", "b"], item_height=44))
    first = result.backend.list_stores[result.get_by_type("VirtualList").tag].revision
    result.rerender(pn.FlatList(data=["z", "b"], item_height=44))
    assert result.backend.list_stores[result.get_by_type("VirtualList").tag].revision > first
    assert result.get_by_text("z")


def test_native_requests_are_bounded_and_stale_requests_are_ignored() -> None:
    result = render(pn.FlatList(data=list(range(10_000)), item_height=44))
    view = result.get_by_type("VirtualList")
    store = result.backend.list_stores[view.tag]
    revision = store.revision
    assert len(result.get_all_by_type("Text")) <= 56
    key = store.keys[5000]
    result.fire(view, "on_bind_row", {"index": 5000, "key": key, "revision": revision - 1})
    assert result.query_by_text("5000") is None
    result.fire(view, "on_bind_row", {"index": 5000, "key": key, "revision": revision})
    assert result.get_by_text("5000")
    assert len(result.get_all_by_type("Text")) <= 56
    result.unmount()
    assert result.backend.live_view_count() == 0


def test_rows_do_not_move_state_to_different_keys() -> None:
    @pn.component
    def Row(item: Any) -> pn.Element:
        original, _ = pn.use_state(item)
        return pn.Text(f"{item}/{original}")

    result = render(pn.FlatList(data=["a"], key_extractor=lambda item, _: item, render_item=lambda item, _: Row(item)))
    result.rerender(pn.FlatList(data=["b"], key_extractor=lambda item, _: item, render_item=lambda item, _: Row(item)))
    assert result.get_by_text("b/b")


def test_duplicate_keys_fail_before_native_commit() -> None:
    with pytest.raises(ValueError, match="unique"):
        render(pn.FlatList(data=[1, 2], key_extractor=lambda *_: "duplicate"))


def test_fixed_list_height_survives_an_unbounded_scroll_parent() -> None:
    result = render(
        pn.ScrollView(
            pn.Column(pn.FlatList(data=list(range(40)), item_height=44, style={"height": 400}), pn.Text("After"))
        )
    )
    assert result.get_by_type("VirtualList").frame[3] == 400
    result.unmount()


def test_parent_renders_keep_dataset_revision_and_only_changed_items_advance() -> None:
    def row(item: str, _: int) -> pn.Element:
        return pn.Text(item)

    result = render(pn.FlatList(data=["a", "b"], render_item=row))
    view = result.get_by_type("VirtualList")
    store = result.backend.list_stores[view.tag]
    revision, items = store.revision, [store.rows[key].revision for key in store.keys]
    result.rerender(pn.FlatList(data=["a", "b"], render_item=row))
    assert store.revision == revision
    assert [store.rows[key].revision for key in store.keys] == items
    result.rerender(pn.FlatList(data=["changed", "b"], render_item=row))
    assert [store.rows[key].revision for key in store.keys] == [items[0] + 1, items[1]]
    result.unmount()


def test_public_indices_exclude_global_and_section_headers() -> None:
    reference: pn.Ref[Any] = pn.Ref()
    result = render(
        pn.SectionList(
            sections=[pn.Section(key="A", title="A", data=["a", "b"]), pn.Section(key="B", title="B", data=["c"])],
            list_header=pn.Text("Global header"),
            ref=reference,
        )
    )
    reference.current.scroll_to_index(2, animated=False)
    assert result.backend.commands[-1][-1]["index"] == 5
    with pytest.raises(IndexError):
        reference.current.scroll_to_index(3)
    result.unmount()


def test_viewport_changes_reuse_dataset_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    import pythonnative.components.lists as lists

    original = lists._prepare_snapshot
    prepared = []

    def prepare(*args: Any, **kwargs: Any) -> Any:
        prepared.append(len(args[0]))
        return original(*args, **kwargs)

    monkeypatch.setattr(lists, "_prepare_snapshot", prepare)
    result = render(pn.FlatList(data=range(100_000), item_height=44), viewport=None, settle_first=False)
    view = result.get_by_type("VirtualList")
    store = result.backend.list_stores[view.tag]
    keys, metadata = store.keys, store.rows
    for first in range(50, 500, 25):
        result.fire(view, "on_window", {"first": first, "last": first + 18, "extent": 800, "y": first * 44})
        assert store.keys is keys
        assert store.rows is metadata
        assert len(result.get_all_by_type("Text")) <= 56
    assert prepared == [100_000]
    result.unmount()


def test_parent_updates_reuse_indexed_sequence_and_revision_refreshes_in_place_edits() -> None:
    calls = []
    data = [{"id": index, "title": str(index)} for index in range(10_000)]

    def key(item: Any, index: int) -> str:
        calls.append(index)
        return str(item["id"])

    def row(item: Any, _: int) -> pn.Element:
        return pn.Text(item["title"])

    result = render(pn.FlatList(data=data, key_extractor=key, render_item=row), viewport=None)
    assert len(calls) == len(data)
    result.rerender(pn.FlatList(data=data, key_extractor=key, render_item=row))
    assert len(calls) == len(data)
    data[0]["title"] = "Edited in place"
    result.rerender(pn.FlatList(data=data, data_revision=1, key_extractor=key, render_item=row))
    assert result.get_by_text("Edited in place")
    assert len(calls) == 2 * len(data)
    result.unmount()
