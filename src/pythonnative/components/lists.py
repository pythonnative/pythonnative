"""Keyed virtualized lists with one logical component tree."""

from typing import Any, Callable, Dict, List, Optional

from ..component import component, memo
from ..element import Element
from ..hooks import Ref, use_imperative_handle, use_memo, use_ref, use_state
from ..style import StyleProp, resolve_style
from .layout import Row, View
from .text import Text

_DEFAULT_ROW_EXTENT = 44.0


class _RowSpec:
    """One virtualized row: a stable key, a lazy renderer, and an extent hint."""

    __slots__ = ("key", "make", "extent", "item", "index", "item_count")

    def __init__(
        self,
        key: str,
        make: Callable[[], Element],
        extent: Optional[float],
        item: Any = None,
        index: int = 0,
        item_count: int = 1,
    ) -> None:
        self.key = key
        self.make = make
        self.extent = extent
        self.item = item
        self.index = index
        self.item_count = item_count


class ListController:
    """Imperative scroll handle published on a list's ``ref``.

    [`FlatList`][pythonnative.FlatList] and
    [`SectionList`][pythonnative.SectionList] install a
    ``ListController`` on ``ref.current`` (via
    [`use_imperative_handle`][pythonnative.use_imperative_handle])
    after mount and clear it back to ``None`` on unmount.

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


@memo(equal=lambda old, new: old["revision"] == new["revision"] and old["row"].key == new["row"].key)
@component
def _ListRow(row: _RowSpec, revision: int) -> Element:
    return row.make()


@component
def _NativeList(
    rows: Optional[List[_RowSpec]] = None,
    render_inputs: Any = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: Optional[float] = None,
    on_viewable_items_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
    shows_scroll_indicator: Optional[bool] = None,
    list_style: Optional[Dict[str, Any]] = None,
    controller_ref: Optional[Ref] = None,
    horizontal: bool = False,
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
    from ..hooks import current_hook_state

    owner = current_hook_state().owner

    def dispatch(ref: Any, name: str, args: Dict[str, Any]) -> Any:
        tag = getattr(ref, "_pn_tag", None)
        if tag is not None and owner is not None:
            return getattr(owner, "backend").command(tag, name, args)
        return None

    source = rows or []
    rows = list(source)
    if not rows and empty is not None:
        rows.append(_RowSpec("__empty__", lambda: empty, None, item=empty))
    if header is not None:
        rows.insert(0, _RowSpec("__header__", lambda: header, None, item=header))
    if footer is not None:
        rows.append(_RowSpec("__footer__", lambda: footer, None, item=footer))
    keys = [row.key for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("List keys must be unique")
    previous: Any = use_ref(None)
    signature = [(row.key, row.item, row.index, row.extent, row.item_count) for row in rows]

    def snapshot() -> Any:
        from ..equality import equal

        before = previous.current
        dataset_revision = 1 if before is None else before[0] + 1
        prior: dict[str, Any] = before[1] if before is not None else {}
        render_changed = before is None or not equal(before[2], render_inputs)
        items = {}
        for row in rows:
            inputs = (row.item, row.index, row.extent, row.item_count)
            old = prior.get(row.key)
            changed = render_changed or old is None or not equal(old[0], inputs)
            item_revision = 1 if old is None else old[1] + int(changed)
            items[row.key] = (inputs, item_revision)
        previous.current = (dataset_revision, items, render_inputs)
        return dataset_revision, [items[key][1] for key in keys]

    revision, item_revisions = use_memo(snapshot, [signature, render_inputs, header, footer, empty])
    window, set_window = use_state((0, 800.0))
    center, viewport = window
    visible = max(1, int(viewport / max(1, estimated_row_extent)) + 1)
    first, last = max(0, center - 16), min(len(rows), center + visible + 16)
    internal_ref: Ref = use_ref()
    end_revision = use_ref(-1)

    def bind(info: Dict[str, Any]) -> None:
        if info.get("revision") != revision:
            return
        index = int(info.get("index", -1))
        if not 0 <= index < len(rows) or info.get("key") != keys[index]:
            return
        if index < first + 8 or index >= last - 8:
            set_window((index, float(info.get("extent", viewport))))

    def scroll(info: Dict[str, Any]) -> Any:
        start = int(info.get("first", center))
        extent = float(info.get("extent", viewport))
        if start != center or extent != viewport:
            set_window((start, extent))
        if on_end_reached is not None:
            remaining = info.get("range", 0) - info.get("x" if horizontal else "y", 0) - info.get("extent", 0)
            if (
                remaining <= (on_end_reached_threshold or 0.5) * info.get("extent", 0)
                and end_revision.current != revision
            ):
                end_revision.current = revision
                from ..runtime import invoke

                invoke(on_end_reached)
        if on_viewable_items_changed is not None:
            start, end = int(info.get("first", 0)), int(info.get("last", -1))
            from ..runtime import invoke

            invoke(
                on_viewable_items_changed,
                [
                    {"key": rows[i].key, "index": rows[i].index, "item": rows[i].item}
                    for i in range(max(0, start), min(len(rows), end + 1))
                    if rows[i] in source and rows[i].item_count
                ],
            )
        return on_scroll(info) if on_scroll is not None else None

    def scroll_to_index(index: int, animated: bool) -> None:
        if index < 0:
            raise IndexError("List item index must be nonnegative")
        candidates = [
            i for i, row in enumerate(rows) if row in source and row.index <= index < row.index + row.item_count
        ]
        if not candidates:
            raise IndexError("List has no item at that index")
        dispatch(internal_ref, "scroll_to_index", {"index": candidates[-1], "animated": animated})

    use_imperative_handle(
        controller_ref,
        lambda: ListController(
            lambda offset, animated: dispatch(
                internal_ref, "scroll_to_offset", {"x" if horizontal else "y": offset, "animated": animated}
            ),
            scroll_to_index,
            lambda animated: dispatch(internal_ref, "scroll_to_end", {"animated": animated}),
        ),
        [horizontal, revision],
    )
    props = {
        "flex_grow": 1,
        **(list_style or {}),
        "keys": keys,
        "revision": revision,
        "item_revisions": item_revisions,
        "count": len(rows),
        "row_heights": [r.extent or estimated_row_extent for r in rows],
        "horizontal": horizontal,
        "on_bind_row": bind,
        "on_scroll": scroll,
        "shows_scroll_indicator": shows_scroll_indicator is not False,
        "ref": internal_ref,
    }
    if refresh_control is not None:
        props["refresh_control"] = dict(refresh_control.props)
    children = []
    for index in range(first, last):
        row = rows[index]
        style = dict(content_container_style or {})
        if row.extent is not None:
            style["width" if horizontal else "height"] = row.extent
        if not horizontal:
            style["width"] = "100%"
        child = View(_ListRow(row, item_revisions[index]), style=style, key=row.key)
        child = Element(child.type, {**child.props, "_pn_list_key": row.key}, child.children, child.key)
        children.append(child)
    return Element("VirtualList", props, children)


def FlatList(
    *,
    data: Optional[List[Any]] = None,
    render_item: Optional[Callable[[Any, int], Element]] = None,
    key_extractor: Optional[Callable[[Any, int], str]] = None,
    item_height: Optional[float] = None,
    get_item_height: Optional[Callable[[Any, int], float]] = None,
    estimated_item_height: Optional[float] = None,
    separator_height: float = 0,
    refresh_control: Optional[Element] = None,
    horizontal: bool = False,
    num_columns: int = 1,
    list_header: Optional[Element] = None,
    list_footer: Optional[Element] = None,
    list_empty: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: float = 0.5,
    on_viewable_items_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
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
        data: List of arbitrary item values.
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
        refresh_control: Optional [`RefreshControl`][pythonnative.RefreshControl]
            element for pull-to-refresh.
        horizontal: Scroll horizontally (extents become widths).
        num_columns: Render items in a grid of this many columns.
        list_header: Element rendered once before all rows.
        list_footer: Element rendered once after all rows.
        list_empty: Element rendered when ``data`` is empty.
        on_end_reached: Called when the user scrolls within
            ``on_end_reached_threshold`` viewports of the end (fires
            once per dataset revision).
        on_end_reached_threshold: Distance from the end, in viewport
            multiples, at which ``on_end_reached`` fires.
        on_viewable_items_changed: Called with a list of
            ``{"index", "key", "item"}`` dicts whenever the set of
            visible rows changes.
        on_scroll: Called with the raw scroll payload
            (``{"x": …, "y": …}``).
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
    items_list = list(data or [])
    sep = float(separator_height or 0.0)

    def _row_key(item: Any, index: int) -> str:
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

    def _make_row(item: Any, index: int) -> Callable[[], Element]:
        def _make() -> Element:
            el = render_item(item, index) if render_item else Text(str(item))
            if sep > 0:
                pad_style: Dict[str, Any] = {"padding_end" if horizontal else "padding_bottom": sep}
                return View(el, style=pad_style)
            return el

        return _make

    rows: List[_RowSpec] = []
    if num_columns > 1 and not horizontal:
        for start in range(0, len(items_list), num_columns):
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
                row = Row(*cells)
                if sep > 0:
                    return View(row, style={"padding_bottom": sep})
                return row

            group_key = "__pn_grp_" + "|".join(_row_key(it, start + j) for j, it in enumerate(chunk))
            extent = (float(item_height) + sep) if item_height is not None else None
            rows.append(_RowSpec(group_key, _make_group, extent, item=chunk, index=start, item_count=len(chunk)))
    else:
        for i, item in enumerate(items_list):
            rows.append(_RowSpec(_row_key(item, i), _make_row(item, i), _row_extent(item, i), item=item, index=i))

    estimated = estimated_item_height if estimated_item_height is not None else (item_height or _DEFAULT_ROW_EXTENT)

    return _NativeList(
        rows=rows,
        render_inputs=(render_item, separator_height, horizontal, num_columns),
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_viewable_items_changed=on_viewable_items_changed,
        on_scroll=on_scroll,
        shows_scroll_indicator=shows_scroll_indicator,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
        horizontal=horizontal,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
        content_container_style=resolve_style(content_container_style) or None,
    ).with_key(key)


def SectionList(
    *,
    sections: Optional[List[Dict[str, Any]]] = None,
    render_item: Optional[Callable[[Any, int, int], Element]] = None,
    render_section_header: Optional[Callable[[Dict[str, Any], int], Element]] = None,
    key_extractor: Optional[Callable[[Any, int], str]] = None,
    item_height: Optional[float] = None,
    get_item_height: Optional[Callable[[Any, int, int], float]] = None,
    estimated_item_height: Optional[float] = None,
    section_header_height: Optional[float] = None,
    separator_height: float = 0,
    refresh_control: Optional[Element] = None,
    list_header: Optional[Element] = None,
    list_footer: Optional[Element] = None,
    list_empty: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: float = 0.5,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
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
        sections: Each section is ``{"title": ..., "data": [...]}``.
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
        refresh_control: Optional [`RefreshControl`][pythonnative.RefreshControl] element.
        list_header: Element rendered once before everything.
        list_footer: Element rendered once after everything.
        list_empty: Element rendered when there are no sections.
        on_end_reached: Called near the end of the content.
        on_end_reached_threshold: Distance from the end, in viewport
            multiples, at which ``on_end_reached`` fires.
        on_scroll: Called with the raw scroll payload.
        style: Style for the outer scroll container.
        ref: Optional [`Ref`][pythonnative.Ref]; receives a
            [`ListController`][pythonnative.ListController] on
            ``ref.current`` after mount.
        key: Stable identity for keyed reconciliation of the list.

    Returns:
        A virtualized list element (a function component instance).
    """
    sections_list = list(sections or [])
    sep = float(separator_height or 0.0)

    def _header_el(section: Dict[str, Any], s_idx: int) -> Element:
        if render_section_header is not None:
            return render_section_header(section, s_idx)
        return Text(str(section.get("title", "")), style={"bold": True, "padding": 8})

    def _item_el(item: Any, i_idx: int, s_idx: int) -> Element:
        if render_item is not None:
            return render_item(item, i_idx, s_idx)
        return Text(str(item))

    rows: List[_RowSpec] = []
    flat_index = 0
    for s_idx, section in enumerate(sections_list):

        def _make_header(sec: Dict[str, Any] = section, si: int = s_idx) -> Element:
            return _header_el(sec, si)

        rows.append(
            _RowSpec(
                f"__pn_sec_{s_idx}__",
                _make_header,
                float(section_header_height) if section_header_height is not None else None,
                item=section,
                index=flat_index,
                item_count=0,
            )
        )
        for i_idx, item in enumerate(section.get("data", []) or []):
            if key_extractor is not None:
                try:
                    row_key = f"s{s_idx}:" + str(key_extractor(item, i_idx))
                except Exception:
                    row_key = f"__pn_row_{s_idx}_{i_idx}__"
            else:
                row_key = f"__pn_row_{s_idx}_{i_idx}__"

            def _make_item(it: Any = item, ii: int = i_idx, si: int = s_idx) -> Element:
                el = _item_el(it, ii, si)
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
            rows.append(_RowSpec(row_key, _make_item, extent, item=item, index=flat_index))
            flat_index += 1

    estimated = estimated_item_height if estimated_item_height is not None else (item_height or _DEFAULT_ROW_EXTENT)

    return _NativeList(
        rows=rows,
        render_inputs=(render_item, render_section_header, separator_height),
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_scroll=on_scroll,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
    ).with_key(key)
