# Lists

[`FlatList`][pythonnative.FlatList] and
[`SectionList`][pythonnative.SectionList] are the two list components
shipped with PythonNative. Sections use frozen `Section(key=..., data=..., title=...)` records; section keys
are unique and independent of their positions. Both lists are **virtualized**: only the rows
inside (and just beyond) the viewport are mounted as native views.
On mobile, `RecyclerView` (Android) and `UICollectionView` (iOS) own physical
cell recycling. Rows remain ordinary keyed components in the application's
logical tree. Providers, error boundaries, suspense boundaries, and cancellation
therefore work across row and screen containers.

Use stable keys and immutable data. A new data snapshot advances the list's
revision; stale row requests are discarded. `estimated_item_height` provides an
initial estimate for variable content, and native measurement refines row
extents. Fixed heights, sections, grids, headers, footers, and pull-to-refresh
use this native path too. The browser implements the same logical-row protocol;
headless tests use a windowed scroll container.

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

## Incremental data

Use `ListData[T]` for frequently edited lists. It owns stable string keys and
notifies mounted lists when items change. Keep it in a repository or create it
with `use_memo` on the application thread:

```python
from dataclasses import dataclass, replace
import pythonnative as pn

@dataclass(frozen=True)
class Message:
    id: str
    title: str


def render_message(message: Message, index: int):
    return pn.Text(message.title)


@pn.component
def Messages():
    messages = pn.use_memo(
        lambda: pn.ListData([Message("a", "Hello")], key=lambda message: message.id),
        [],
    )

    def edit():
        new_key = f"message-{messages.revision}"
        with messages.batch():
            messages.update("a", replace(messages.get("a"), title="Edited"))
            messages.append(Message(new_key, "New message"))
            messages.move(new_key, 0)

    return pn.Column(
        pn.Button("Edit messages", on_press=edit),
        pn.FlatList(data=messages, render_item=render_message, style={"flex": 1}),
        style={"flex": 1},
    )
```

Omit `key_extractor` when passing `ListData`; the source owns its keys. Mutate
it on its creating thread. `update(key, replacement)` preserves identity;
`insert(index, item)`, `append(item)`, `remove(key)`, `move(key, final_index)`,
and `clear()` publish explicit edits. `batch()` combines notifications, including
nested batches. It doesn't roll back successful edits if its body raises.

A one-item update does constant metadata work and sends one row record, even
with 100,000 items. Initial mounting and expired history require a full metadata
snapshot. Structural edits shift indexed arrays, so insertion and reordering
aren't constant-time operations. The bounded journal defaults to 1,024 changes;
each mounted list tracks its own committed revision.

The incremental path supports ordinary single-column lists with fixed or
estimated heights. Grids and `get_item_height` use the sequence adapter below.
Changing rendering callbacks or list decorations also invalidates the snapshot.
Keep callbacks stable with module-level functions or `use_callback`.

## Data snapshots

Lists accept a `Sequence` and cache keys and row metadata separately from the
scrolling window. Keep `render_item`, `key_extractor`, and height callbacks
stable when the parent rerenders, using module-level functions or
`use_callback`. Scrolling then does work proportional to the mounted window.

Prefer replacing data with a new sequence. If you mutate a sequence in place,
increment `data_revision` when passing it to `FlatList` or `SectionList`.
The revision invalidates the cached snapshot. Native prefetch requests mount
nearby rows, and keyed anchoring preserves the visible row as measurements or
data updates change extents above it.

## Row heights

Three ways to tell the list how tall rows are, in order of preference:

- `item_height=44`: uniform rows. Offsets are exact and cheap, and
  native containers can skip estimating that extent.
- `get_item_height=lambda item, i: ...`: exact per-row extents
  without measurement. Native containers use those extents directly.
- Nothing at all: rows start at `estimated_item_height` (default 44)
  and are corrected with their measured extent once they've been on
  screen. Native containers refine their layout as measurements arrive;
  variable-height rows use the same recycling path as fixed-height rows.

`separator_height=` adds a fixed gap below every row. For a drawn
divider, pass `item_separator=` an element or a zero-argument function
returning one; it renders after every row except the last (and, in a
`SectionList`, only between the items of a section, never after a
header or a section's last item):

```python
pn.FlatList(
    data=items,
    item_height=44,
    item_separator=lambda: pn.View(style={"height": 1, "background_color": "#E5E7EB"}),
)
```

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
it changes, as a list of frozen `ViewableItem` records with `.index`, `.key`, and `.item`; on a
`SectionList` the list covers items only, with flat indices.
`on_scroll` receives a [`ScrollEvent`][pythonnative.ScrollEvent] as the
list scrolls.

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
`scroll_to_end(animated=True)`. To start at a given row instead, pass
`initial_scroll_index=`; the list scrolls there without animation once
it mounts.

## Grids, headers, and empty states

- `num_columns=2` chunks items into grid rows.
- `horizontal=True` scrolls on the x-axis (extents become widths).
- `list_header=` / `list_footer=` render once before/after all rows.
- `list_empty=` renders when `data` is empty.

## Inverted lists

`inverted=True` renders the list bottom-up (or right-to-left when
`horizontal`), so rows appended to `data` appear at the visible end,
the chat-transcript layout. It is implemented in Python on top of the
same `VirtualList` contract: a mirror transform (`scale_y: -1`, or
`scale_x: -1` for horizontal lists) is applied to the container and to
each row, so no native change is involved.

```python
pn.FlatList(
    data=messages,
    inverted=True,
    render_item=lambda m, _: Bubble(message=m),
    key_extractor=lambda m, _: m["id"],
)
```

## Section lists

[`SectionList`][pythonnative.SectionList] flattens an iterable of
`Section` records into a single virtualized
list, dispatching to either `render_section_header` or `render_item`
depending on the row's kind.

```python
sections = [
    pn.Section(key="a", title="A", data=["Apple", "Avocado"]),
    pn.Section(key="b", title="B", data=["Banana", "Blueberry"]),
]

pn.SectionList(
    sections=sections,
    item_height=44,
    section_header_height=32,
    render_section_header=lambda s, _: pn.Text(s.title),
    render_item=lambda item, _i, _s: pn.Text(item),
)
```

Headers and items can have different extents, and variable-height
rows work exactly as in `FlatList` (exact via `get_item_height`, or
estimated and measured). `inverted`, `item_separator`, and
`on_viewable_items_changed` work as on `FlatList`.

`sticky_section_headers=True` keeps the current section's header pinned at the
top of the native list and lets the next header push it away. Native layout
owns this movement, including while Python is busy. Python retains the active
header in its bounded mounted window. No application `on_scroll` handler is
needed.

```python
pn.SectionList(
    sections=sections,
    sticky_section_headers=True,
    section_header_height=32,
    render_section_header=lambda s, _: pn.Text(s.title, style={"background_color": "#FFF"}),
    render_item=lambda item, _i, _s: pn.Text(item),
)
```

Give the header an opaque background so rows don't show through it.

## Performance notes

- Use `ListData` keys or a stable `key_extractor` so rows that stay inside
  the window refresh in place rather than tearing down and rebuilding
  their subtree as the window shifts.
- Provide real extents (`item_height` / `get_item_height`) when you
  can. Exact extents reduce native measurement work. For variable content,
  choose an `estimated_item_height` close to typical row sizes.
- Headers, footers, empty states, pull-to-refresh, grids, and horizontal
  scrolling all use native recycling on mobile. Test representative content
  and scrolling on your deployment targets.
- Keep row subtrees shallow. The reconciler is fast, but mounting a
  hundred `Text`/`Image`/`Button` nodes per row is wasteful work
  every time a row enters the window.
- Move expensive computation out of `render_item` (use
  [`use_memo`][pythonnative.use_memo] in the parent component, or
  pre-compute once before constructing the data list).
