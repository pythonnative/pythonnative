"""Logical list ownership under native recycling requests."""

from typing import Any

import pytest

import pythonnative as pn
from pythonnative.testing import render


@pytest.fixture(autouse=True)
def native_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pn.components, "_native_lists_supported", lambda: True)


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
            "inherited",
            pn.FlatList(data=data, key_extractor=lambda item, _: item["id"], render_item=lambda item, _: Row(item)),
        )

    result = render(tree([{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]))
    assert result.get_by_text("A/A/inherited")
    setters["a"]("edited")
    result.rerender(tree([{"id": "b", "label": "B2"}, {"id": "a", "label": "A2"}]))
    assert result.get_by_text("A2/edited/inherited")
    assert result.get_by_text("B2/B/inherited")


def test_same_length_data_edits_advance_native_revision() -> None:
    result = render(pn.FlatList(data=["a", "b"], item_height=44))
    first = result.get_by_type("VirtualList").props["revision"]
    result.rerender(pn.FlatList(data=["z", "b"], item_height=44))
    assert result.get_by_type("VirtualList").props["revision"] > first
    assert result.get_by_text("z")


def test_native_requests_are_bounded_and_stale_requests_are_ignored() -> None:
    result = render(pn.FlatList(data=list(range(10_000)), item_height=44))
    view = result.get_by_type("VirtualList")
    revision = view.props["revision"]
    assert len(result.get_all_by_type("Text")) <= 56
    key = view.props["keys"][5000]
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
