# Lists

[`FlatList`][pythonnative.FlatList] and
[`SectionList`][pythonnative.SectionList] are the two list components
shipped with PythonNative. Both are **virtualized**: only the rows
inside (and just beyond) the viewport are mounted as native views.
Under the hood the list picks one of two engines:

- **Native virtualization.** On Android and iOS, when every row's
  extent is known up front (a fixed `item_height`, or exact
  `get_item_height` / `section_header_height` values) and no
  windowed-only feature is requested, the list is backed by a real
  `RecyclerView` (Android) or `UITableView` (iOS). The platform owns
  row recycling; each visible row hosts its own PythonNative subtree
  that is mounted on demand and reconciled in place when its cell is
  recycled. This is the fastest path and the one long feeds should
  aim for.
- **Python windowing.** Everywhere else (the desktop preview,
  variable-height rows, grids, horizontal lists, headers/footers/empty
  states, and pull-to-refresh), rows render into a native scroll view
  with leading and trailing spacers standing in for off-screen
  content, and the window of mounted rows shifts from scroll events.

The public surface is identical on both paths: `on_end_reached`,
`on_viewable_items_changed`, `on_scroll`, and the imperative scroll
controller behave the same regardless of which engine is active.

```python
import pythonnative as pn

items = [{"id": i, "title": f"Row {i}"} for i in range(10_000)]


@pn.component
def Big():
    return pn.FlatList(
        data=items,
        item_height=44,
        render_item=lambda item, _: pn.Text(item["title"]),
        key_extractor=lambda item, _: str(item["id"]),
    )
```

The list never holds 10,000 native views; only the window around the
viewport ever exists.

## Row heights

Three ways to tell the list how tall rows are, in order of preference:

- `item_height=44`: uniform rows. Offsets are exact and cheap, and
  the list qualifies for the native virtualization path.
- `get_item_height=lambda item, i: ...`: exact per-row extents
  without measurement. Also qualifies for native virtualization.
- Nothing at all: rows start at `estimated_item_height` (default 44)
  and are corrected with their measured extent once they've been on
  screen. Scroll positions stay stable as estimates converge. This
  always uses the Python-windowed engine (native recyclers need exact
  heights before rows are rendered).

`separator_height=` adds a fixed gap below every row.

## Pull-to-refresh

Use [`RefreshControl`][pythonnative.RefreshControl] as a prop on
either `FlatList` or [`ScrollView`][pythonnative.ScrollView]:

```python
@pn.component
def Pullable():
    refreshing, set_refreshing = pn.use_state(False)

    def reload():
        set_refreshing(True)
        # ... fetch data ...
        set_refreshing(False)

    return pn.FlatList(
        data=items,
        item_height=44,
        refresh_control=pn.RefreshControl(
            refreshing=refreshing,
            on_refresh=reload,
        ),
    )
```

## Row taps

Wrap the row in a [`Pressable`][pythonnative.Pressable] inside
`render_item`:

```python
def render_row(item, index):
    return pn.Pressable(
        pn.Text(item["title"]),
        on_press=lambda: open_detail(item["id"]),
    )
```

## Infinite scroll

`on_end_reached` fires once when the user scrolls within
`on_end_reached_threshold` viewports of the end (re-arming when the
data length changes), which is the hook for pagination:

```python
pn.FlatList(
    data=items,
    item_height=44,
    on_end_reached=load_next_page,
    on_end_reached_threshold=0.5,  # half a viewport from the bottom
)
```

`on_viewable_items_changed` reports the set of visible rows whenever
it changes, as a list of `{"index", "key", "item"}` dicts.

## Imperative scrolling

Pass a [`use_ref`][pythonnative.use_ref] as `ref=` and the list
publishes a [`ListController`][pythonnative.ListController] on
`ref.current`:

```python
@pn.component
def JumpableList():
    list_ref = pn.use_ref()

    return pn.Column(
        pn.Button("Jump to row 200", on_press=lambda: list_ref.current.scroll_to_index(200)),
        pn.FlatList(data=items, item_height=44, ref=list_ref, style={"flex": 1}),
        style={"flex": 1},
    )
```

The controller exposes `scroll_to_index(i, animated=True)`,
`scroll_to_offset(points, animated=True)`, and
`scroll_to_end(animated=True)`.

## Grids, headers, and empty states

- `num_columns=2` chunks items into grid rows.
- `horizontal=True` scrolls on the x-axis (extents become widths).
- `list_header=` / `list_footer=` render once before/after all rows.
- `list_empty=` renders when `data` is empty.

## Section lists

[`SectionList`][pythonnative.SectionList] flattens an iterable of
`{"title": ..., "data": [...]}` sections into a single virtualized
list, dispatching to either `render_section_header` or `render_item`
depending on the row's kind.

```python
sections = [
    {"title": "A", "data": ["Apple", "Avocado"]},
    {"title": "B", "data": ["Banana", "Blueberry"]},
]

pn.SectionList(
    sections=sections,
    item_height=44,
    section_header_height=32,
    render_section_header=lambda s, _: pn.Text(s["title"]),
    render_item=lambda item, _i, _s: pn.Text(item),
)
```

Headers and items can have different extents, and variable-height
rows work exactly as in `FlatList` (exact via `get_item_height`, or
estimated and measured).

## Performance notes

- Always provide a stable `key_extractor` so rows that stay inside
  the window refresh in place rather than tearing down and rebuilding
  their subtree as the window shifts.
- Provide real extents (`item_height` / `get_item_height`) when you
  can. Exact extents unlock the native RecyclerView / UITableView
  path on device; measured estimation works but stays on the
  Python-windowed engine and does more bookkeeping per scroll.
- Features that force the windowed engine (`list_header`,
  `list_footer`, `list_empty`, `refresh_control`, `num_columns`,
  `horizontal`) are fine for short lists, but a very long feed is
  smoothest with none of them and a fixed `item_height`.
- Keep row subtrees shallow. The reconciler is fast, but mounting a
  hundred `Text`/`Image`/`Button` nodes per row is wasteful work
  every time a row enters the window.
- Move expensive computation out of `render_item` (use
  [`use_memo`][pythonnative.use_memo] in the parent component, or
  pre-compute once before constructing the data list).
