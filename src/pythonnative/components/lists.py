"""Keyed virtualized lists with one logical component tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, TypeVar, Union, cast, overload

from ..bridge.list_store import ListRow
from ..component import component, memo
from ..element import Element
from ..hooks import (
    Ref,
    use_effect,
    use_imperative_handle,
    use_layout_effect,
    use_memo,
    use_ref,
    use_state,
    use_subscription,
)
from ..list_data import ListData, Section, ViewableItem
from ..profiling import count
from ..style import Style, StyleProp, resolve_style
from .events import ScrollEvent
from .layout import Row, View
from .text import Text

T = TypeVar("T")

ItemSeparator = Union[Callable[[], Element], Element, None]
"""``item_separator`` value: an element (reused for every gap) or a zero-argument factory."""


def _separator_element(separator: ItemSeparator) -> Optional[Element]:
    if separator is None:
        return None
    return separator() if callable(separator) else separator


def _inverted_transform(horizontal: bool) -> Dict[str, Any]:
    """The mirror transform applied to an inverted list and each of its rows."""
    return {"scale_x": -1} if horizontal else {"scale_y": -1}


def _scroll_event(info: Dict[str, Any], horizontal: bool) -> ScrollEvent:
    """Turn the native list scroll payload into the public ``ScrollEvent``."""
    extent = float(info.get("extent", 0.0) or 0.0)
    content = float(info.get("range", 0.0) or 0.0)
    return ScrollEvent(
        x=float(info.get("x", 0.0) or 0.0),
        y=float(info.get("y", 0.0) or 0.0),
        content_width=content if horizontal else 0.0,
        content_height=0.0 if horizontal else content,
        viewport_width=extent if horizontal else 0.0,
        viewport_height=0.0 if horizontal else extent,
    )


_DEFAULT_ROW_EXTENT = 44.0


class _Identity:
    """Keep a dependency alive and compare it without traversing its values."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, _Identity) and self.value is other.value


@dataclass(frozen=True)
class _ListSnapshot:
    """Dataset metadata built once, independently of the visible window."""

    rows: Sequence["_RowSpec"]
    keys: Sequence[str]
    heights: Sequence[float]
    item_revisions: Sequence[int]
    inputs: dict[str, Any]
    public_indices: Any
    revision: int
    render_inputs: Any
    packet: dict[str, Any]
    source: Any = None
    source_revision: int = -1


def _prepare_snapshot(
    source: Sequence["_RowSpec"],
    before: Optional[_ListSnapshot],
    render_inputs: Any,
    header: Optional[Element],
    footer: Optional[Element],
    empty: Optional[Element],
    estimated: float,
) -> _ListSnapshot:
    from ..equality import equal

    count("list.snapshot_rows", len(source))
    rows = list(source)
    if not rows and empty is not None:
        rows.append(_RowSpec("__empty__", lambda: empty, None, item=empty, item_count=0))
    if header is not None:
        rows.insert(0, _RowSpec("__header__", lambda: header, None, item=header, item_count=0))
    if footer is not None:
        rows.append(_RowSpec("__footer__", lambda: footer, None, item=footer, item_count=0))
    keys = [row.key for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("List keys must be unique")
    prior = before.inputs if before is not None else {}
    render_changed = before is None or not equal(before.render_inputs, render_inputs)
    inputs, revisions, public = {}, [], {}
    for native_index, row in enumerate(rows):
        values = (row.item, row.index, row.extent, row.item_count, row.sticky, row.is_last)
        old = prior.get(row.key)
        changed = render_changed or old is None or not equal(old[0], values)
        revision = 1 if old is None else old[1] + int(changed)
        inputs[row.key] = (values, revision)
        revisions.append(revision)
        for public_index in range(row.index, row.index + row.item_count):
            public[public_index] = native_index
    heights = [row.extent if row.extent is not None else estimated for row in rows]
    incremental_before = before is not None and before.source is not None
    changed = (
        before is None
        or incremental_before
        or keys != before.keys
        or revisions != before.item_revisions
        or heights != before.heights
    )
    revision = 1 if before is None else before.revision + int(changed)
    metadata = [ListRow(row.key, version, height, row.sticky) for row, version, height in zip(rows, revisions, heights)]
    if before is not None and not changed:
        return before
    # Incremental snapshots contain live indexed views, not a historical copy
    # of every row. Switching adapters must replace the native metadata rather
    # than diffing against a source that may already have changed again.
    packet = (
        {"base": before.revision, "revision": revision, "changes": [["reset", [row.wire() for row in metadata]]]}
        if before is not None and incremental_before
        else _metadata_patch(before, metadata, revision)
    )
    return _ListSnapshot(rows, keys, heights, revisions, inputs, public, revision, render_inputs, packet)


def _metadata_patch(before: Optional[_ListSnapshot], rows: list[ListRow], revision: int) -> dict[str, Any]:
    changes: list[list[Any]]
    if before is None:
        changes = [["reset", [row.wire() for row in rows]]]
    else:
        old = {
            key: (before.item_revisions[i], before.heights[i], before.rows[i].sticky)
            for i, key in enumerate(before.keys)
        }
        keys = [row.key for row in rows]
        if keys == list(before.keys):
            changes = [["u", row.wire()] for row in rows if old[row.key] != (row.revision, row.extent, row.sticky)]
        else:
            wanted = set(keys)
            if len(wanted.symmetric_difference(old)) > 128:
                return {
                    "base": before.revision,
                    "revision": revision,
                    "changes": [["reset", [row.wire() for row in rows]]],
                }
            changes = [["d", key] for key in before.keys if key not in wanted]
            order = [key for key in before.keys if key in wanted]
            moves = 0
            for i, row in enumerate(rows):
                if row.key not in old:
                    changes.append(["i", i, row.wire()])
                    order.insert(i, row.key)
                else:
                    if order[i] != row.key:
                        order.remove(row.key)
                        order.insert(i, row.key)
                        changes.append(["m", row.key, i])
                        moves += 1
                    if old[row.key] != (row.revision, row.extent, row.sticky):
                        changes.append(["u", row.wire()])
                if moves > 128:
                    changes = [["reset", [item.wire() for item in rows]]]
                    break
    return {"base": before.revision if before else 0, "revision": revision, "changes": changes}


class _Indexed(Sequence[T], Generic[T]):
    """A bounded view of a live indexed source, read only during a render."""

    def __init__(self, length: int, get: Callable[[int], T]) -> None:
        self.length, self.get = length, get

    def __len__(self) -> int:
        return self.length

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> list[T]: ...

    def __getitem__(self, index: int | slice) -> T | list[T]:
        if isinstance(index, slice):
            return [self.get(i) for i in range(*index.indices(self.length))]
        if index < 0:
            index += self.length
        if not 0 <= index < self.length:
            raise IndexError(index)
        return self.get(index)


class _IncrementalRows(Sequence["_RowSpec"]):
    def __init__(self, data: ListData[Any], make: Callable[[Any, int], Element], extent: Optional[float]) -> None:
        self.data, self.make, self.extent = data, make, extent

    def __len__(self) -> int:
        return len(self.data)

    @overload
    def __getitem__(self, index: int) -> "_RowSpec": ...

    @overload
    def __getitem__(self, index: slice) -> list["_RowSpec"]: ...

    def __getitem__(self, index: int | slice) -> "_RowSpec" | list["_RowSpec"]:
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        entry = self.data._entries[self.data._keys[index]]
        count("list.row_specs")
        return _RowSpec(
            entry.key,
            lambda: self.make(entry.item, index),
            self.extent,
            item=entry.item,
            index=index,
            is_last=index == len(self.data) - 1,
        )


def _prepare_incremental(
    source: _IncrementalRows,
    before: Optional[_ListSnapshot],
    render_inputs: Any,
    header: Optional[Element],
    footer: Optional[Element],
    empty: Optional[Element],
    estimated: float,
) -> _ListSnapshot:
    from ..equality import equal

    data = source.data
    # Decorations have their own keys and don't enter the application's source.
    leading = [_RowSpec("__header__", lambda: header, None, item=header, item_count=0)] if header is not None else []
    trailing = [_RowSpec("__footer__", lambda: footer, None, item=footer, item_count=0)] if footer is not None else []
    vacant = (
        [_RowSpec("__empty__", lambda: empty, None, item=empty, item_count=0)] if not data and empty is not None else []
    )
    offset, size = len(leading), len(data)
    total = offset + size + len(vacant) + len(trailing)

    def at(index: int) -> _RowSpec:
        if index < offset:
            return leading[index]
        if index < offset + size:
            return source[index - offset]
        return (vacant + trailing)[index - offset - size]

    rows = _Indexed(total, at)

    def version(index: int) -> int:
        return data._entries[data._keys[index - offset]].revision if offset <= index < offset + size else 1

    revisions = _Indexed(total, version)
    keys = _Indexed(total, lambda i: data._keys[i - offset] if offset <= i < offset + size else at(i).key)
    heights = _Indexed(total, lambda i: source.extent or estimated if offset <= i < offset + size else estimated)
    source_revision = data.revision
    reusable = before is not None and before.source is data and equal(before.render_inputs, render_inputs)
    edits = data._changes_since(before.source_revision) if reusable else None
    # Decoration changes or an empty/nonempty transition need a fresh snapshot.
    if before is not None and (
        before.inputs != {"decorations": (header, footer, empty)} or bool(before.public_indices) != bool(size)
    ):
        edits = None
    if edits == [] and before is not None:
        return before
    revision = before.revision + 1 if before else 1

    def wire(entry: Any) -> list[Any]:
        return [entry.key, entry.revision, source.extent or estimated, False]

    changes: list[list[Any]]
    if edits is None:
        changes = [["reset", [[keys[i], revisions[i], heights[i], False] for i in range(total)]]]
        count("list.snapshot_rows", total)
    else:
        changes = []
        for edit in edits:
            if edit[0] == "i":
                changes.append(["i", cast(int, edit[1]) + offset, wire(edit[2])])
            elif edit[0] == "u":
                changes.append(["u", wire(edit[1])])
            elif edit[0] == "m":
                changes.append(["m", edit[1], cast(int, edit[2]) + offset])
            else:
                changes.append(["d", edit[1]])
        count("list.incremental_changes", len(changes))
    packet = {"base": before.revision if before else 0, "revision": revision, "changes": changes}
    # A range maps public indices without allocating one entry per item.
    public = _PublicIndices(size, offset)
    return _ListSnapshot(
        rows,
        keys,
        heights,
        revisions,
        {"decorations": (header, footer, empty)},
        public,
        revision,
        render_inputs,
        packet,
        data,
        source_revision,
    )


class _PublicIndices:
    def __init__(self, size: int, offset: int) -> None:
        self.size, self.offset = size, offset

    def __bool__(self) -> bool:
        return bool(self.size)

    def get(self, index: int) -> Optional[int]:
        return index + self.offset if 0 <= index < self.size else None


class _RowSpec:
    """One virtualized row: a stable key, a lazy renderer, and an extent hint."""

    __slots__ = ("key", "make", "extent", "item", "index", "item_count", "section", "sticky", "is_last")

    def __init__(
        self,
        key: str,
        make: Callable[[], Element],
        extent: Optional[float],
        item: Any = None,
        index: int = 0,
        item_count: int = 1,
        section: Optional[int] = None,
        sticky: bool = False,
        is_last: bool = False,
    ) -> None:
        self.key = key
        self.make = make
        self.extent = extent
        self.item = item
        self.index = index
        self.item_count = item_count
        self.section = section
        self.sticky = sticky
        self.is_last = is_last


class ListController:
    """Imperative scroll handle published on a list's ``ref``.

    [`FlatList`][pythonnative.FlatList] and
    [`SectionList`][pythonnative.SectionList] install a
    ``ListController`` on ``ref.current`` (via
    [`use_imperative_handle`][pythonnative.use_imperative_handle])
    after mount and clear it back to ``None`` on unmount. Commands go
    through the inner ``VirtualList``'s
    [`ViewHandle`][pythonnative.ViewHandle].

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def Chat(messages):
            list_ref = pn.use_ref()
            pn.use_layout_effect(
                lambda: list_ref.current and list_ref.current.scroll_to_end(animated=False),
                [len(messages)],
            )
            return pn.FlatList(data=messages, render_item=Bubble, ref=list_ref)
        ```
    """

    __slots__ = ("_scroll_to_offset", "_scroll_to_index", "_scroll_to_end")

    def __init__(
        self,
        scroll_to_offset: Callable[[float, bool], None],
        scroll_to_index: Callable[[int, bool], None],
        scroll_to_end: Callable[[bool], None],
    ) -> None:
        self._scroll_to_offset = scroll_to_offset
        self._scroll_to_index = scroll_to_index
        self._scroll_to_end = scroll_to_end

    def scroll_to_offset(self, offset: float, animated: bool = True) -> None:
        """Scroll to an absolute content offset in points."""
        self._scroll_to_offset(offset, animated)

    def scroll_to_index(self, index: int, animated: bool = True) -> None:
        """Scroll so the row at ``index`` sits at the top of the viewport."""
        self._scroll_to_index(index, animated)

    def scroll_to_end(self, animated: bool = True) -> None:
        """Scroll to the end of the content."""
        self._scroll_to_end(animated)


@memo(
    equal=lambda old, new: old["revision"] == new["revision"]
    and old["row"].key == new["row"].key
    and old["row"].index == new["row"].index
    and old["row"].is_last == new["row"].is_last
    and old["inputs"] == new["inputs"]
)
@component
def _ListRow(row: _RowSpec, revision: int, inputs: Any) -> Element:
    return row.make()


@component
def _NativeList(
    rows: Optional[Sequence[_RowSpec]] = None,
    render_inputs: Any = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: Optional[float] = None,
    on_viewable_items_changed: Optional[Callable[[List[ViewableItem[T]]], None]] = None,
    on_scroll: Optional[Callable[[ScrollEvent], Any]] = None,
    shows_scroll_indicator: Optional[bool] = None,
    list_style: Optional[Dict[str, Any]] = None,
    controller_ref: Optional[Ref] = None,
    horizontal: bool = False,
    inverted: bool = False,
    initial_index: Optional[int] = None,
    estimated_row_extent: float = 44,
    header: Optional[Element] = None,
    footer: Optional[Element] = None,
    empty: Optional[Element] = None,
    refresh_control: Optional[Element] = None,
    content_container_style: Optional[Dict[str, Any]] = None,
) -> Element:
    """Prepare a bounded set of logical rows for native recycled containers.

    Keys own hooks. Native container identities never enter the component
    tree. Every data snapshot has a revision, including same-length edits.
    """
    source = rows if rows is not None else ()
    previous: Any = use_ref(None)

    def prepare() -> _ListSnapshot:
        if isinstance(source, _IncrementalRows):
            return _prepare_incremental(
                source, previous.current, render_inputs, header, footer, empty, estimated_row_extent
            )
        return _prepare_snapshot(source, previous.current, render_inputs, header, footer, empty, estimated_row_extent)

    dataset = use_memo(
        prepare,
        [
            _Identity(source),
            render_inputs,
            _Identity(header),
            _Identity(footer),
            _Identity(empty),
            estimated_row_extent,
        ],
    )
    use_layout_effect(lambda: setattr(previous, "current", dataset), [dataset.revision])
    rows, keys = dataset.rows, dataset.keys
    revision, item_revisions = dataset.revision, dataset.item_revisions
    window, set_window = use_state((0, 800.0, -1))
    center, viewport, sticky_index = window
    visible = max(1, int(viewport / max(1, estimated_row_extent)) + 1)
    first, last = max(0, center - 16), min(len(rows), center + visible + 16)
    internal_ref: Ref = use_ref()
    end_revision = use_ref(-1)

    def source_is_current() -> bool:
        # Events can arrive between a source mutation and its next commit.
        # Never interpret old native indices through the source's new order.
        return dataset.source is None or dataset.source.revision == dataset.source_revision

    def dispatch(name: str, args: Dict[str, Any]) -> Any:
        # ``internal_ref.current`` is the VirtualList's ViewHandle once mounted.
        handle = internal_ref.current
        return handle.command(name, **args) if handle is not None else None

    def bind(info: Dict[str, Any]) -> None:
        if info.get("revision") != revision or not source_is_current():
            return
        index = int(info.get("index", -1))
        if not 0 <= index < len(rows) or info.get("key") != keys[index]:
            return
        if index < first + 8 or index >= last - 8:
            set_window((index, float(info.get("extent", viewport)), int(info.get("sticky", -1))))

    def scroll(info: Dict[str, Any]) -> Any:
        if info.get("revision", revision) != revision or not source_is_current():
            return None
        start = int(info.get("first", center))
        extent = float(info.get("extent", viewport))
        if (
            start < first + 8
            and first > 0
            or start + visible > last - 8
            and last < len(rows)
            or extent != viewport
            or int(info.get("sticky", -1)) != sticky_index
        ):
            set_window((start, extent, int(info.get("sticky", -1))))
        if on_end_reached is not None:
            remaining = info.get("range", 0) - info.get("x" if horizontal else "y", 0) - info.get("extent", 0)
            if (
                remaining
                <= (0.5 if on_end_reached_threshold is None else on_end_reached_threshold) * info.get("extent", 0)
                and end_revision.current != revision
            ):
                end_revision.current = revision
                from ..runtime import invoke

                invoke(on_end_reached)
        if on_viewable_items_changed is not None:
            start_index, end_index = int(info.get("first", 0)), int(info.get("last", -1))
            from ..runtime import invoke

            invoke(
                on_viewable_items_changed,
                [
                    ViewableItem(key=rows[i].key, index=rows[i].index, item=rows[i].item)
                    for i in range(max(0, start_index), min(len(rows), end_index + 1))
                    if rows[i].item_count
                ],
            )
        return None

    def scroll_to_index(index: int, animated: bool) -> None:
        if index < 0:
            raise IndexError("List item index must be nonnegative")
        native_index = dataset.public_indices.get(index)
        if native_index is None:
            raise IndexError("List has no item at that index")
        dispatch("scroll_to_index", {"index": native_index, "animated": animated})

    use_imperative_handle(
        controller_ref,
        lambda: ListController(
            lambda offset, animated: dispatch(
                "scroll_to_offset", {"x" if horizontal else "y": offset, "animated": animated}
            ),
            scroll_to_index,
            lambda animated: dispatch("scroll_to_end", {"animated": animated}),
        ),
        [horizontal, revision],
    )

    def scroll_to_initial() -> None:
        if initial_index is not None and dataset.public_indices.get(initial_index) is not None:
            scroll_to_index(initial_index, False)

    use_effect(scroll_to_initial, [])
    props = {
        "flex_grow": 1,
        **(list_style or {}),
        "dataset": dataset.packet,
        "horizontal": horizontal,
        "on_bind_row": bind,
        "on_window": scroll,
        "shows_scroll_indicator": shows_scroll_indicator is not False,
        "ref": internal_ref,
    }
    if inverted:
        props["transform"] = [*(props.get("transform") or []), _inverted_transform(horizontal)]
    if on_scroll is not None:
        props["on_scroll"] = lambda info: on_scroll(_scroll_event(info, horizontal))
    if refresh_control is not None:
        props["refresh_control"] = dict(refresh_control.props)
    children = []
    mounted_indices = sorted(set(range(first, last)) | ({sticky_index} if 0 <= sticky_index < len(rows) else set()))
    for index in mounted_indices:
        row = rows[index]
        style: Dict[str, Any] = dict(content_container_style or {})
        if row.extent is not None:
            style["width" if horizontal else "height"] = row.extent
        if not horizontal:
            style["width"] = "100%"
        if inverted:
            style["transform"] = [*(style.get("transform") or []), _inverted_transform(horizontal)]
        child = View(
            _ListRow(row, item_revisions[index], (render_inputs, _Identity(dataset.source))),
            style=cast(Style, style),
            key=row.key,
        )
        child = Element(child.type, {**child.props, "_pn_list_key": row.key}, child.children, child.key)
        children.append(child)
    return Element("VirtualList", props, children)


@component
def FlatList(
    *,
    data: Optional[Sequence[T]] = None,
    data_revision: int = 0,
    render_item: Optional[Callable[[T, int], Element]] = None,
    key_extractor: Optional[Callable[[T, int], str]] = None,
    item_height: Optional[float] = None,
    get_item_height: Optional[Callable[[T, int], float]] = None,
    estimated_item_height: Optional[float] = None,
    separator_height: float = 0,
    item_separator: ItemSeparator = None,
    refresh_control: Optional[Element] = None,
    horizontal: bool = False,
    inverted: bool = False,
    num_columns: int = 1,
    initial_scroll_index: Optional[int] = None,
    list_header: Optional[Element] = None,
    list_footer: Optional[Element] = None,
    list_empty: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: float = 0.5,
    on_viewable_items_changed: Optional[Callable[[List[ViewableItem[T]]], None]] = None,
    on_scroll: Optional[Callable[[ScrollEvent], Any]] = None,
    shows_scroll_indicator: bool = True,
    content_container_style: StyleProp = None,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized scrollable list that renders items from ``data`` lazily.

    A bounded window of keyed row components supplies content to the
    renderer. UIKit collection views and Android recycler views own native
    cells; the browser implements the same row-request protocol.
    Headless backends simulate the same row requests.
    Rows may have **variable heights**: pass ``item_height`` when rows are uniform,
    ``get_item_height`` for exact per-item extents, or nothing at all;
    unknown rows start at ``estimated_item_height`` and are corrected
    with their measured extent once they've been on screen.

    Pass a [`Ref`][pythonnative.Ref] (from
    [`use_ref`][pythonnative.use_ref]) to receive a
    [`ListController`][pythonnative.ListController] on ``ref.current``:
    ``ref.current.scroll_to_index(i)``,
    ``ref.current.scroll_to_offset(pts)``, and
    ``ref.current.scroll_to_end()``.

    Args:
        data: A ``ListData`` source or a sequence of arbitrary item values.
            Use explicit mutations on ``ListData``; replace ordinary sequences
            when they change.
        data_revision: Increment after changing a sequence in place. Unchanged
            sequence identity and revision reuse the indexed dataset.
        render_item: ``render_item(item, index) -> Element``. Defaults
            to wrapping each item in a [`Text`][pythonnative.Text].
        key_extractor: Function returning a stable key per item
            (recommended whenever ``data`` can reorder).
        item_height: Uniform row extent in points, when known.
        get_item_height: ``get_item_height(item, index) -> float`` for
            exact variable extents without measurement.
        estimated_item_height: Starting extent estimate for rows whose
            true size isn't known yet (default 44).
        separator_height: Gap below each row, in points.
        item_separator: An element, or a zero-argument function
            returning one, rendered after every row except the last
            (React Native's ``ItemSeparatorComponent``).
        refresh_control: Optional [`RefreshControl`][pythonnative.RefreshControl]
            element for pull-to-refresh.
        horizontal: Scroll horizontally (extents become widths).
        inverted: Render the list bottom-up (or right-to-left when
            ``horizontal``), so new rows appended to ``data`` appear at
            the visible end, as in a chat transcript. Implemented with
            a mirror transform on the list and on each row.
        num_columns: Render items in a grid of this many columns.
        initial_scroll_index: Item index scrolled to, without
            animation, once the list mounts.
        list_header: Element rendered once before all rows.
        list_footer: Element rendered once after all rows.
        list_empty: Element rendered when ``data`` is empty.
        on_end_reached: Called when the user scrolls within
            ``on_end_reached_threshold`` viewports of the end (fires
            once per dataset revision).
        on_end_reached_threshold: Distance from the end, in viewport
            multiples, at which ``on_end_reached`` fires.
        on_viewable_items_changed: Called with a list of
            frozen ``ViewableItem`` records whenever the set of
            visible rows changes.
        on_scroll: Called with a [`ScrollEvent`][pythonnative.ScrollEvent]
            as the list scrolls.
        shows_scroll_indicator: When ``False``, hides the scroll bar.
        content_container_style: Style applied to the inner content
            wrapper.
        style: Style for the outer scroll container.
        ref: Optional [`Ref`][pythonnative.Ref]; receives a
            [`ListController`][pythonnative.ListController] on
            ``ref.current`` after mount.
        key: Stable identity for keyed reconciliation of the list.

    Returns:
        A virtualized list element (a function component instance).

    Example:
        ```python
        import pythonnative as pn

        items = [{"id": i, "name": f"Item {i}"} for i in range(10000)]

        pn.FlatList(
            data=items,
            item_height=44,
            render_item=lambda item, _: pn.Text(item["name"]),
            key_extractor=lambda item, _: str(item["id"]),
        )
        ```
    """
    sep = float(separator_height or 0.0)
    source_version = use_subscription(
        data.subscribe if isinstance(data, ListData) else lambda callback: lambda: None,
        lambda: data.revision if isinstance(data, ListData) else data_revision,
    )
    if isinstance(data, ListData) and key_extractor is not None:
        raise ValueError("ListData owns its keys; omit key_extractor")

    def prepare_rows() -> Sequence[_RowSpec]:
        if isinstance(data, ListData) and num_columns == 1 and get_item_height is None:

            def make(item: Any, index: int) -> Element:
                el = render_item(item, index) if render_item else Text(str(item))
                separator = _separator_element(item_separator) if index < len(data) - 1 else None
                if separator is not None:
                    el = View(el, separator, style={"flex_direction": "row" if horizontal else "column"})
                if sep > 0:
                    el = View(el, style={"padding_end": sep} if horizontal else {"padding_bottom": sep})
                return el

            return _IncrementalRows(data, make, float(item_height) + sep if item_height is not None else None)
        items_list = list(data or [])
        count = len(items_list)

        def _row_key(item: Any, index: int) -> str:
            if isinstance(data, ListData):
                return data._keys[index]
            if key_extractor is not None:
                return str(key_extractor(item, index))
            return f"__pn_row_{index}__"

        def _row_extent(item: Any, index: int) -> Optional[float]:
            if get_item_height is not None:
                try:
                    return float(get_item_height(item, index)) + sep
                except Exception:
                    return None
            if item_height is not None:
                return float(item_height) + sep
            return None

        def _decorate(el: Element, is_last: bool) -> Element:
            separator = None if is_last else _separator_element(item_separator)
            if separator is not None:
                el = View(el, separator, style={"flex_direction": "row" if horizontal else "column"})
            if sep > 0:
                pad_style: Style = {"padding_end": sep} if horizontal else {"padding_bottom": sep}
                return View(el, style=pad_style)
            return el

        def _make_row(item: Any, index: int) -> Callable[[], Element]:
            def _make() -> Element:
                el = render_item(item, index) if render_item else Text(str(item))
                return _decorate(el, index == count - 1)

            return _make

        rows: List[_RowSpec] = []
        if num_columns > 1 and not horizontal:
            for start in range(0, count, num_columns):
                chunk = items_list[start : start + num_columns]

                def _make_group(group: List[Any] = chunk, base: int = start) -> Element:
                    cells = [
                        View(
                            render_item(it, base + j) if render_item else Text(str(it)),
                            style={"flex": 1},
                            key=_row_key(it, base + j),
                        )
                        for j, it in enumerate(group)
                    ]
                    return _decorate(Row(*cells), base + len(group) >= count)

                group_key = "__pn_grp_" + "|".join(_row_key(it, start + j) for j, it in enumerate(chunk))
                extent = (float(item_height) + sep) if item_height is not None else None
                rows.append(_RowSpec(group_key, _make_group, extent, item=chunk, index=start, item_count=len(chunk)))
        else:
            for i, item in enumerate(items_list):
                rows.append(
                    _RowSpec(
                        _row_key(item, i),
                        _make_row(item, i),
                        _row_extent(item, i),
                        item=item,
                        index=i,
                        is_last=i == count - 1,
                    )
                )

        return rows

    rows = use_memo(
        prepare_rows,
        [
            _Identity(data),
            data_revision,
            source_version,
            render_item,
            key_extractor,
            item_height,
            get_item_height,
            separator_height,
            _Identity(item_separator),
            horizontal,
            num_columns,
        ],
    )

    estimated = estimated_item_height if estimated_item_height is not None else (item_height or _DEFAULT_ROW_EXTENT)

    return _NativeList(
        rows=rows,
        render_inputs=(render_item, separator_height, item_separator, horizontal, num_columns, data_revision),
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_viewable_items_changed=on_viewable_items_changed,
        on_scroll=on_scroll,
        shows_scroll_indicator=shows_scroll_indicator,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
        horizontal=horizontal,
        inverted=inverted,
        initial_index=initial_scroll_index,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
        content_container_style=resolve_style(content_container_style) or None,
    ).with_key(key)


_SECTION_HEADER_PREFIX = "__pn_sec_"


def _default_section_header(section: Section[Any], _index: int) -> Element:
    return Text(section.title, style={"bold": True, "padding": 8})


@component
def SectionList(
    *,
    sections: Optional[Sequence[Section[T]]] = None,
    data_revision: int = 0,
    render_item: Optional[Callable[[T, int, int], Element]] = None,
    render_section_header: Optional[Callable[[Section[T], int], Element]] = None,
    key_extractor: Optional[Callable[[Any, int], str]] = None,
    item_height: Optional[float] = None,
    get_item_height: Optional[Callable[[Any, int, int], float]] = None,
    estimated_item_height: Optional[float] = None,
    section_header_height: Optional[float] = None,
    separator_height: float = 0,
    item_separator: ItemSeparator = None,
    sticky_section_headers: bool = False,
    inverted: bool = False,
    refresh_control: Optional[Element] = None,
    list_header: Optional[Element] = None,
    list_footer: Optional[Element] = None,
    list_empty: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: float = 0.5,
    on_viewable_items_changed: Optional[Callable[[List[ViewableItem[T]]], None]] = None,
    on_scroll: Optional[Callable[[ScrollEvent], Any]] = None,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized list with section headers interleaved between row groups.

    Flattens ``sections`` into a single virtualized sequence where each
    entry is either a header or an item, then reuses the same windowing
    engine as [`FlatList`][pythonnative.FlatList]; headers and items
    may have different (and variable) heights.

    Args:
        data_revision: Increment after changing sections in place to rebuild the indexed dataset.
        sections: Each section is a ``Section(key=..., data=..., title=...)`` record.
        render_item: ``render_item(item, item_index, section_index) ->
            Element``.
        render_section_header: ``render_section_header(section,
            section_index) -> Element``. Defaults to a bold
            [`Text`][pythonnative.Text] of the section title.
        key_extractor: Stable key per item: ``key_extractor(item,
            item_index) -> str``.
        item_height: Uniform item extent in points, when known.
        get_item_height: ``get_item_height(item, item_index,
            section_index) -> float`` for exact variable extents.
        estimated_item_height: Starting estimate for unmeasured rows.
        section_header_height: Header extent in points, when known.
        separator_height: Gap below each item, in points.
        item_separator: An element, or a zero-argument function
            returning one, rendered between the items of each section.
        sticky_section_headers: Keep the current section's header
            pinned at the top of the list while its items scroll by.
            Native layout pins the existing header and lets the next
            header push it away, without Python scroll callbacks.
        inverted: Render the list bottom-up (see
            [`FlatList`][pythonnative.FlatList]).
        refresh_control: Optional [`RefreshControl`][pythonnative.RefreshControl] element.
        list_header: Element rendered once before everything.
        list_footer: Element rendered once after everything.
        list_empty: Element rendered when there are no sections.
        on_end_reached: Called near the end of the content.
        on_end_reached_threshold: Distance from the end, in viewport
            multiples, at which ``on_end_reached`` fires.
        on_viewable_items_changed: Called with a list of
            frozen ``ViewableItem`` records (items only, with flat
            indices) whenever the set of visible rows changes.
        on_scroll: Called with a [`ScrollEvent`][pythonnative.ScrollEvent]
            as the list scrolls.
        style: Style for the outer scroll container.
        ref: Optional [`Ref`][pythonnative.Ref]; receives a
            [`ListController`][pythonnative.ListController] on
            ``ref.current`` after mount.
        key: Stable identity for keyed reconciliation of the list.

    Returns:
        A virtualized list element (a function component instance).
    """
    sep = float(separator_height or 0.0)
    header_renderer = render_section_header or _default_section_header

    def prepare_rows() -> List[_RowSpec]:
        sections_list = list(sections or [])
        if any(not isinstance(s.key, str) or not s.key for s in sections_list) or len(
            {s.key for s in sections_list}
        ) != len(sections_list):
            raise ValueError("Section keys must be unique, nonempty strings")

        def _item_el(item: Any, i_idx: int, s_idx: int) -> Element:
            if render_item is not None:
                return render_item(item, i_idx, s_idx)
            return Text(str(item))

        rows: List[_RowSpec] = []
        flat_index = 0
        for s_idx, section in enumerate(sections_list):

            def _make_header(sec: Section[T] = section, si: int = s_idx) -> Element:
                return header_renderer(sec, si)

            rows.append(
                _RowSpec(
                    f"{_SECTION_HEADER_PREFIX}{len(section.key)}:{section.key}",
                    _make_header,
                    float(section_header_height) if section_header_height is not None else None,
                    item=section,
                    index=flat_index,
                    item_count=0,
                    section=s_idx,
                    sticky=sticky_section_headers,
                )
            )
            items = list(section.data)
            for i_idx, item in enumerate(items):
                if key_extractor is not None:
                    try:
                        row_key = f"s{len(section.key)}:{section.key}:" + str(key_extractor(item, i_idx))
                    except Exception:
                        row_key = f"s{len(section.key)}:{section.key}:i{i_idx}"
                else:
                    row_key = f"s{len(section.key)}:{section.key}:i{i_idx}"

                def _make_item(
                    it: Any = item, ii: int = i_idx, si: int = s_idx, is_last: bool = i_idx == len(items) - 1
                ) -> Element:
                    el = _item_el(it, ii, si)
                    separator = None if is_last else _separator_element(item_separator)
                    if separator is not None:
                        el = View(el, separator)
                    if sep > 0:
                        return View(el, style={"padding_bottom": sep})
                    return el

                extent: Optional[float] = None
                if get_item_height is not None:
                    try:
                        extent = float(get_item_height(item, i_idx, s_idx)) + sep
                    except Exception:
                        extent = None
                elif item_height is not None:
                    extent = float(item_height) + sep
                rows.append(_RowSpec(row_key, _make_item, extent, item=item, index=flat_index, section=s_idx))
                flat_index += 1

        return rows

    rows = use_memo(
        prepare_rows,
        [
            _Identity(sections),
            data_revision,
            render_item,
            render_section_header,
            key_extractor,
            item_height,
            get_item_height,
            separator_height,
            _Identity(item_separator),
            section_header_height,
            sticky_section_headers,
        ],
    )

    estimated = estimated_item_height if estimated_item_height is not None else (item_height or _DEFAULT_ROW_EXTENT)

    native = _NativeList(
        rows=rows,
        render_inputs=(
            render_item,
            render_section_header,
            separator_height,
            item_separator,
            data_revision,
            sticky_section_headers,
        ),
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_viewable_items_changed=on_viewable_items_changed,
        on_scroll=on_scroll,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
        inverted=inverted,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
    )
    return native.with_key(key)
