"""Virtualized lists: ``FlatList`` and ``SectionList``.

FlatList and SectionList pick between two engines:

1. **Native virtualization** (`_NativeList` -> the ``VirtualList``
   element): on Android and iOS, when every row extent is known up
   front and no windowed-only feature is requested, the list is
   backed by a real ``RecyclerView`` / ``UITableView``. The platform
   owns row recycling; each visible row hosts a nested-reconciler
   subtree (see ``pythonnative.virtual_rows``).
2. **Python windowing** (`_VirtualizedList`): a windowed slice of
   rows rendered into a ScrollView (leading spacer, visible rows,
   trailing spacer), the window shifting from scroll events (the
   same architecture as React Native's VirtualizedList). Because
   every windowed row lives in the *main* layout tree, rows may be
   any height: estimates steer the spacer sizes and measured extents
   correct them over time. This is the browser preview path and the fallback
   for variable-height rows, grids, horizontal lists, ornaments, and
   pull-to-refresh.
"""

import bisect
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..component import component
from ..element import Element
from ..hooks import Ref, use_imperative_handle, use_ref, use_state
from ..style import StyleProp, resolve_style
from .layout import Column, Row, ScrollView, View
from .text import Text

_DEFAULT_ROW_EXTENT = 44.0


class _RowSpec:
    """One virtualized row: a stable key, a lazy renderer, and an extent hint."""

    __slots__ = ("key", "make", "extent", "item", "index")

    def __init__(
        self,
        key: str,
        make: Callable[[], Element],
        extent: Optional[float],
        item: Any = None,
        index: int = 0,
    ) -> None:
        self.key = key
        self.make = make
        self.extent = extent
        self.item = item
        self.index = index


def _dispatch_scroll_command(scroll_ref: Any, name: str, args: Dict[str, Any]) -> Any:
    """Send an imperative command to the ScrollView under ``scroll_ref``."""
    tag = getattr(scroll_ref, "_pn_tag", None)
    if tag is None:
        return None
    from ..native_views import get_registry

    try:
        return get_registry().command(tag, name, args)
    except Exception:
        return None


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


@component
def _VirtualizedList(
    rows: Optional[List[_RowSpec]] = None,
    horizontal: bool = False,
    estimated_row_extent: Optional[float] = None,
    overscan_extent: Optional[float] = None,
    initial_window_extent: Optional[float] = None,
    header: Optional[Element] = None,
    footer: Optional[Element] = None,
    empty: Optional[Element] = None,
    refresh_control: Optional[Element] = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: Optional[float] = None,
    on_viewable_items_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    on_scroll: Optional[Callable[[Any], Any]] = None,
    shows_scroll_indicator: bool = True,
    content_container_style: Optional[Dict[str, Any]] = None,
    list_style: Optional[Dict[str, Any]] = None,
    controller_ref: Optional[Ref] = None,
) -> Element:
    """Shared windowing engine behind FlatList and SectionList."""
    rows = rows or []
    n = len(rows)
    horizontal = bool(horizontal)
    estimated: float = float(estimated_row_extent or _DEFAULT_ROW_EXTENT)
    overscan: float = float(overscan_extent or 0.0)
    initial_extent: float = float(initial_window_extent or 800.0)

    window, set_window = use_state((0, -1))
    measured: Ref[Dict[str, float]] = use_ref({})  # row key -> measured extent (points)
    row_refs: Ref[Dict[str, Ref]] = use_ref({})  # row key -> Ref for live rows
    end_latch = use_ref({"fired_for": -1})
    viewable_ref: Ref[Dict[str, Tuple[str, ...]]] = use_ref({"keys": ()})
    scroll_pos = use_ref({"offset": 0.0})
    sv_ref: Ref = use_ref(None)

    # ------------------------------------------------------------------
    # Extent model: measured > per-row hint > estimate. ``starts`` are
    # prefix sums; ``starts[n]`` is the total content extent.
    # ------------------------------------------------------------------
    measured_map: Dict[str, float] = measured.current
    starts: List[float] = [0.0] * (n + 1)
    acc = 0.0
    for i, spec in enumerate(rows):
        starts[i] = acc
        extent = measured_map.get(spec.key)
        if extent is None:
            extent = spec.extent if spec.extent is not None else estimated
        acc += max(0.0, float(extent))
    starts[n] = acc
    total_extent = acc

    def _viewport_extent() -> float:
        frame = sv_ref._pn_frame
        if frame:
            extent = frame[2] if horizontal else frame[3]
            if extent and extent > 0:
                return float(extent)
        return initial_extent

    def _window_for(offset: float, viewport: float) -> Tuple[int, int]:
        if n == 0:
            return (0, -1)
        pad = overscan if overscan > 0 else viewport
        lo = max(0.0, offset - pad)
        hi = offset + viewport + pad
        first = max(0, bisect.bisect_right(starts, lo, 0, n) - 1)
        last = min(n - 1, bisect.bisect_left(starts, hi, 0, n))
        return (first, last)

    first, last = window
    if last < 0 or first >= n:
        first, last = _window_for(scroll_pos.current["offset"], _viewport_extent())
    last = min(last, n - 1)
    first = max(0, min(first, max(0, n - 1)))

    # ------------------------------------------------------------------
    # Scroll handling: sweep measured extents, shift the window, fire
    # end-reached / viewability callbacks. State only changes when the
    # window actually moves, so steady scrolling inside the overscan
    # region costs no re-render.
    # ------------------------------------------------------------------
    end_threshold = float(on_end_reached_threshold or 0.5)
    on_viewable = on_viewable_items_changed
    user_on_scroll = on_scroll

    def _sweep_measured() -> None:
        for row_key, row_ref in row_refs.current.items():
            frame = getattr(row_ref, "_pn_frame", None)
            if frame:
                extent = frame[2] if horizontal else frame[3]
                if extent and extent > 0:
                    measured_map[row_key] = float(extent)

    def _handle_scroll(payload: Any) -> None:
        if isinstance(payload, dict):
            offset = float(payload.get("x" if horizontal else "y", 0.0) or 0.0)
        else:
            offset = float(payload or 0.0)
        scroll_pos.current["offset"] = offset
        _sweep_measured()
        viewport = _viewport_extent()

        new_window = _window_for(offset, viewport)
        if new_window != (first, last):
            set_window(new_window)

        if on_end_reached is not None and total_extent > 0:
            remaining = total_extent - (offset + viewport)
            if remaining <= end_threshold * viewport:
                if end_latch.current["fired_for"] != n:
                    end_latch.current["fired_for"] = n
                    on_end_reached()
            elif remaining > end_threshold * viewport + viewport:
                end_latch.current["fired_for"] = -1

        if on_viewable is not None and n > 0:
            v_first = max(0, bisect.bisect_right(starts, offset, 0, n) - 1)
            v_last = min(n - 1, bisect.bisect_left(starts, offset + viewport, 0, n))
            keys = tuple(rows[i].key for i in range(v_first, v_last + 1))
            if keys != viewable_ref.current["keys"]:
                viewable_ref.current["keys"] = keys
                on_viewable(
                    [
                        {"index": rows[i].index, "key": rows[i].key, "item": rows[i].item}
                        for i in range(v_first, v_last + 1)
                    ]
                )

        if user_on_scroll is not None:
            user_on_scroll(payload)

    # ------------------------------------------------------------------
    # Imperative controller (scroll_to_index / offset / end) published
    # on the user's ref. Rebuilt every render (deps=None) so the
    # closures see fresh extents.
    # ------------------------------------------------------------------
    def _scroll_to_offset(offset: float, animated: bool = True) -> None:
        axis = "x" if horizontal else "y"
        _dispatch_scroll_command(sv_ref, "scroll_to_offset", {axis: float(offset), "animated": animated})

    def _scroll_to_index(index: int, animated: bool = True) -> None:
        idx = max(0, min(int(index), n - 1)) if n else 0
        _scroll_to_offset(starts[idx], animated)

    def _scroll_to_end(animated: bool = True) -> None:
        _scroll_to_offset(max(0.0, total_extent - _viewport_extent()), animated)

    use_imperative_handle(
        controller_ref,
        lambda: ListController(_scroll_to_offset, _scroll_to_index, _scroll_to_end),
        None,
    )

    # ------------------------------------------------------------------
    # Children: header, leading spacer, windowed rows, trailing spacer,
    # footer. Rows keep per-key refs so their measured extents survive
    # recycling.
    # ------------------------------------------------------------------
    spacer_key = "width" if horizontal else "height"
    children: List[Element] = []
    if header is not None:
        children.append(View(header, key="__pn_header__"))

    if n == 0:
        if empty is not None:
            children.append(View(empty, key="__pn_empty__"))
    else:
        live_refs: Dict[str, Ref] = {}
        lead = starts[first]
        if lead > 0:
            lead_style: Dict[str, Any] = {spacer_key: lead}
            children.append(View(style=lead_style, key="__pn_lead__"))
        for i in range(first, last + 1):
            spec = rows[i]
            row_ref = row_refs.current.get(spec.key) or Ref()
            live_refs[spec.key] = row_ref
            children.append(View(spec.make(), ref=row_ref, key=spec.key))
        row_refs.current = live_refs
        trail = total_extent - starts[last + 1]
        if trail > 0:
            trail_style: Dict[str, Any] = {spacer_key: trail}
            children.append(View(style=trail_style, key="__pn_trail__"))

    if footer is not None:
        children.append(View(footer, key="__pn_footer__"))

    wrapper = Row if horizontal else Column
    inner = wrapper(*children, style=content_container_style)
    return ScrollView(
        inner,
        scroll_axis="horizontal" if horizontal else "vertical",
        on_scroll=_handle_scroll,
        refresh_control=refresh_control,
        shows_scroll_indicator=shows_scroll_indicator,
        style=list_style,
        ref=sv_ref,
    )


def _native_lists_supported() -> bool:
    """Whether the natively virtualized list path is available.

    Android (RecyclerView) and iOS (UITableView) have native handlers;
    the browser preview and off-device tests use the Python-windowed
    engine. Patchable in tests to exercise the native routing.
    """
    from ..utils import IS_ANDROID, IS_IOS

    return IS_ANDROID or IS_IOS


def _use_native_lists() -> bool:
    """Resolve ``_native_lists_supported`` through the package at call time.

    Looking the function up on ``pythonnative.components`` (rather than
    this module's globals) keeps
    ``monkeypatch.setattr(pythonnative.components, "_native_lists_supported", ...)``
    effective now that the implementation lives in a submodule.
    """
    from . import _native_lists_supported as supported

    return supported()


@component
def _NativeList(
    rows: Optional[List[_RowSpec]] = None,
    on_end_reached: Optional[Callable[[], Any]] = None,
    on_end_reached_threshold: Optional[float] = None,
    on_viewable_items_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    on_scroll: Optional[Callable[[Dict[str, float]], None]] = None,
    shows_scroll_indicator: Optional[bool] = None,
    list_style: Optional[Dict[str, Any]] = None,
    controller_ref: Optional[Ref] = None,
) -> Element:
    """Platform-virtualized list: emits a ``VirtualList`` native element.

    The native side (RecyclerView / UITableView) owns row windowing and
    recycling; each visible row hosts a nested-reconciler subtree (see
    ``pythonnative.virtual_rows``). This composite adapts the FlatList /
    SectionList surface onto that element: it forwards ``render_row``,
    derives ``on_end_reached`` and ``on_viewable_items_changed`` from
    native scroll reports, and wires the imperative scroll controller.

    Requires every row's extent to be known up front (the native
    virtualizers need exact heights before rows are rendered); callers
    fall back to the Python-windowed engine otherwise.
    """
    rows = rows or []
    n = len(rows)
    heights: List[float] = [float(spec.extent or 0.0) for spec in rows]
    uniform = len(set(heights)) <= 1

    internal_ref: Ref = use_ref(None)
    end_latch = use_ref({"fired_for": -1})
    viewable_ref: Ref[Dict[str, Tuple[str, ...]]] = use_ref({"keys": ()})

    starts: List[float] = [0.0] * (n + 1)
    acc = 0.0
    for i, extent in enumerate(heights):
        starts[i] = acc
        acc += max(0.0, extent)
    starts[n] = acc
    total_extent = acc

    def _render_row(index: int) -> Element:
        if 0 <= index < n:
            return rows[index].make()
        return View()

    end_threshold = float(on_end_reached_threshold or 0.5)
    on_viewable = on_viewable_items_changed
    user_on_scroll = on_scroll

    def _handle_scroll(payload: Any) -> None:
        offset = float(payload.get("y", 0.0) or 0.0) if isinstance(payload, dict) else float(payload or 0.0)
        viewport = float(payload.get("extent", 0.0) or 0.0) if isinstance(payload, dict) else 0.0
        if viewport <= 0:
            viewport = 800.0

        if on_end_reached is not None and total_extent > 0:
            remaining = total_extent - (offset + viewport)
            if remaining <= end_threshold * viewport:
                if end_latch.current["fired_for"] != n:
                    end_latch.current["fired_for"] = n
                    on_end_reached()
            elif remaining > end_threshold * viewport + viewport:
                end_latch.current["fired_for"] = -1

        if on_viewable is not None and n > 0:
            v_first = max(0, bisect.bisect_right(starts, offset, 0, n) - 1)
            v_last = min(n - 1, bisect.bisect_left(starts, offset + viewport, 0, n))
            keys = tuple(rows[i].key for i in range(v_first, v_last + 1))
            if keys != viewable_ref.current["keys"]:
                viewable_ref.current["keys"] = keys
                on_viewable(
                    [
                        {"index": rows[i].index, "key": rows[i].key, "item": rows[i].item}
                        for i in range(v_first, v_last + 1)
                    ]
                )

        if user_on_scroll is not None:
            user_on_scroll({"x": 0.0, "y": offset})

    def _scroll_to_offset(offset: float, animated: bool = True) -> None:
        _dispatch_scroll_command(internal_ref, "scroll_to_offset", {"y": float(offset), "animated": animated})

    def _scroll_to_index(index: int, animated: bool = True) -> None:
        _dispatch_scroll_command(internal_ref, "scroll_to_index", {"index": int(index), "animated": animated})

    def _scroll_to_end(animated: bool = True) -> None:
        _dispatch_scroll_command(internal_ref, "scroll_to_end", {"animated": animated})

    use_imperative_handle(
        controller_ref,
        lambda: ListController(_scroll_to_offset, _scroll_to_index, _scroll_to_end),
        None,
    )

    props: Dict[str, Any] = dict(list_style or {})
    props["count"] = n
    if uniform:
        props["row_height"] = heights[0] if heights else _DEFAULT_ROW_EXTENT
    else:
        props["row_heights"] = heights
    props["render_row"] = _render_row
    props["ref"] = internal_ref
    wants_scroll = on_end_reached is not None or on_viewable is not None or user_on_scroll is not None
    if wants_scroll:
        props["on_scroll"] = _handle_scroll
    if shows_scroll_indicator is False:
        props["shows_scroll_indicator"] = False
    return Element("VirtualList", props, [])


def _all_extents_known(rows: List[_RowSpec]) -> bool:
    return all(spec.extent is not None for spec in rows)


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

    Only the rows inside (and just beyond) the viewport are mounted;
    leading and trailing spacers stand in for everything else, and the
    window shifts as the user scrolls. Rows may have **variable
    heights**: pass ``item_height`` when rows are uniform,
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
            once per data length).
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
            try:
                return str(key_extractor(item, index))
            except Exception:
                pass
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
            rows.append(_RowSpec(group_key, _make_group, extent, item=chunk, index=start))
    else:
        for i, item in enumerate(items_list):
            rows.append(_RowSpec(_row_key(item, i), _make_row(item, i), _row_extent(item, i), item=item, index=i))

    estimated = estimated_item_height if estimated_item_height is not None else (item_height or _DEFAULT_ROW_EXTENT)

    # Route to the platform virtualizer (RecyclerView / UITableView)
    # when it can represent this list exactly: vertical, single-column,
    # every row extent known up front, and no features that only the
    # Python-windowed engine implements (ornaments, pull-to-refresh).
    if (
        _use_native_lists()
        and not horizontal
        and num_columns == 1
        and list_header is None
        and list_footer is None
        and list_empty is None
        and refresh_control is None
        and _all_extents_known(rows)
    ):
        return _NativeList(
            rows=rows,
            on_end_reached=on_end_reached,
            on_end_reached_threshold=on_end_reached_threshold,
            on_viewable_items_changed=on_viewable_items_changed,
            on_scroll=on_scroll,
            shows_scroll_indicator=shows_scroll_indicator,
            list_style=resolve_style(style) or None,
            controller_ref=ref,
        ).with_key(key)

    return _VirtualizedList(
        rows=rows,
        horizontal=horizontal,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_viewable_items_changed=on_viewable_items_changed,
        on_scroll=on_scroll,
        shows_scroll_indicator=shows_scroll_indicator,
        content_container_style=resolve_style(content_container_style) or None,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
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
            )
        )
        flat_index += 1
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

    # Same native routing as FlatList: headers and items become one
    # flattened row sequence with per-row heights.
    if (
        _use_native_lists()
        and list_header is None
        and list_footer is None
        and list_empty is None
        and refresh_control is None
        and _all_extents_known(rows)
    ):
        return _NativeList(
            rows=rows,
            on_end_reached=on_end_reached,
            on_end_reached_threshold=on_end_reached_threshold,
            on_scroll=on_scroll,
            list_style=resolve_style(style) or None,
            controller_ref=ref,
        ).with_key(key)

    return _VirtualizedList(
        rows=rows,
        horizontal=False,
        estimated_row_extent=float(estimated) + sep,
        header=list_header,
        footer=list_footer,
        empty=list_empty,
        refresh_control=refresh_control,
        on_end_reached=on_end_reached,
        on_end_reached_threshold=on_end_reached_threshold,
        on_scroll=on_scroll,
        list_style=resolve_style(style) or None,
        controller_ref=ref,
    ).with_key(key)
