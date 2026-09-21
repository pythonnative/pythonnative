# Component property reference

All visual and layout properties are passed via the `style` dict (or list of dicts) to element functions. Behavioural properties (callbacks, data, content) remain as keyword arguments.

Layout properties are interpreted by Yoga beside the native widgets, with
platform measurements for text and controls. Visual properties are applied by
component managers. The browser preview uses Yoga WebAssembly and DOM widgets.
See [Layout engine](../concepts/layout.md) for the shared rules and platform
differences.

## Common layout properties (inside `style`)

All components accept these layout properties in their `style` dict:

### Sizing

- `width`: fixed width in dp (Android) / pt (iOS). Accepts an `int`/`float`,
  or a percentage string like `"50%"` (resolved against the parent's content
  width).
- `height`: fixed height. Same number / percentage rules as `width`.
- `min_width`, `max_width`: width constraints (numbers or `"%"` strings).
- `min_height`, `max_height`: height constraints.
- `aspect_ratio`: width / height ratio. When only one of `width` / `height`
  is known, the other axis is derived from this ratio.

### Flex

- `flex`: shorthand. Setting `flex: N` is equivalent to
  `flex_grow: N, flex_shrink: 1, flex_basis: 0`.
- `flex_grow`: how much a child grows to fill remaining main-axis space.
- `flex_shrink`: how much a child shrinks when its parent runs out of space.
- `flex_basis`: initial main-axis size before grow / shrink is applied
  (`"auto"`, a number, or a percentage string).
- `align_self`: override parent alignment for this child (`"auto"`,
  `"stretch"`, `"flex_start"`, `"center"`, `"flex_end"`).

### Spacing

- `margin`: outer spacing. Accepts a number (all sides), or a dict with any
  of `horizontal`, `vertical`, `left`, `top`, `right`, `bottom`.
- `padding`: inner spacing on container elements. Same shape as `margin`.
- `spacing`: gap between children of a flex container (applied along the
  main axis).
- `gap`: alias for `spacing`.

### Position

- `position`: `"relative"` (default) or `"absolute"`. Absolute children are
  removed from the normal flow and placed using `top` / `right` / `bottom` /
  `left` (numbers or percentage strings).
- `top`, `right`, `bottom`, `left`: offsets used when `position: "absolute"`.
- `inset`, `inset_horizontal`, `inset_vertical`: shorthands that fill all
  four edges, `left` and `right`, or `top` and `bottom`; explicit edge keys
  win. They mirror the `padding_horizontal` / `padding_vertical` vocabulary.

### Other

- `key`: stable identity for reconciliation (passed as a kwarg, not inside
  `style`).

### Accessibility and testing (kwargs)

Most visible components also accept these keyword arguments (see
[Platform & Accessibility](../guides/platform-accessibility.md)):

- `accessibility_label`, `accessibility_hint`, `accessibility_role`,
  `accessible`
- `accessibility_state`: dict of `disabled` / `selected` / `checked` /
  `busy` / `expanded` flags
- `accessibility_value`: a string or an
  [`AccessibilityValue`][pythonnative.AccessibilityValue] with `min` /
  `max` / `now` / `text`
- `accessibility_actions` and `on_accessibility_action`: custom
  screen-reader actions ([`AccessibilityAction`][pythonnative.AccessibilityAction])
  and the callback that receives the invoked action's name
- `accessibility_live_region`: `"none"`, `"polite"`, or `"assertive"`
- `important_for_accessibility`: `"auto"`, `"yes"`, `"no"`, or
  `"no_hide_descendants"`
- `test_id`: stable identifier exposed to UI test frameworks
  (`accessibilityIdentifier` on iOS, resource-id on Android)
- `ref`: a [`Ref`][pythonnative.Ref] that receives a typed
  [handle](handles.md) after commit
- `on_layout` (views): callback receiving a
  [`LayoutEvent`][pythonnative.LayoutEvent] after layout and on frame
  changes

## View

```python
pn.View(*children, style={
    "flex_direction": "column",
    "justify_content": "center",
    "align_items": "center",
    "overflow": "hidden",
    "spacing": 8,
    "padding": 16,
    "background_color": "#F5F5F5",
})
```

Universal flex container (like React Native's `View`). Defaults to `flex_direction: "column"`.

Flex container properties (inside `style`):

- `flex_direction`: `"column"` (default), `"row"`, `"column_reverse"`, `"row_reverse"`
- `justify_content`: `"flex_start"`, `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`, `"space_evenly"`
- `align_items`: `"stretch"`, `"flex_start"`, `"center"`, `"flex_end"`
- `overflow`: `"visible"` (default), `"hidden"`
- `spacing`, `padding`, `background_color`

Containers also fully support absolute positioning for their children:

```python
pn.View(
    pn.View(style={"position": "absolute", "top": 0, "left": 0,
                   "width": 40, "height": 40, "background_color": "#F00"}),
    pn.View(style={"position": "absolute", "bottom": 8, "right": 8,
                   "width": 40, "height": 40, "background_color": "#0A0"}),
    style={"width": 200, "height": 200, "background_color": "#EEE"},
)
```

## Text

```python
pn.Text(text, ellipsize_mode="tail", selectable=False, allow_font_scaling=True,
        on_press=None, style={"font_size": 18, "color": "#333", "bold": True, "text_align": "center"})
```

- `text`: display string (positional)
- `on_press`: callback `() -> None` when the label is tapped; on a nested
  span, when that span is tapped
- `ellipsize_mode`: where to truncate past `max_lines`: `"head"`, `"middle"`,
  `"tail"` (default), or `"clip"`. Android draws `"head"` and `"middle"` only
  on single-line text.
- `selectable`: let the user select and copy the text
- `allow_font_scaling`: scale with the user's text-size setting (default
  `True`); set `False` for text that must keep its exact size
- Style properties: `font_size`, `color`, `bold`, `text_align`, `background_color`, `max_lines`

Rich text: pass a mix of strings and nested `Text` elements as the
positional parts; they flatten into a single native attributed string
(each nested `Text` styles its own run and inherits the rest):

```python
pn.Text("Total: ", pn.Text("$42", style={"bold": True, "color": "#16A34A"}))
pn.Text("Read the ", pn.Text("terms", on_press=open_terms, style={"color": "#06F"}), ".")
```

A nested `Text` with `on_press` becomes a pressable span; only nested
spans produce span presses, while `on_press` on the outer element is the
whole-label event.

## Button

```python
pn.Button(title, on_press=handler, style={"color": "#FFF", "background_color": "#007AFF", "font_size": 16})
```

- `title`: button label (positional)
- `on_press`: callback `() -> None`
- `enabled`: interactive state (kwarg, default `True`)
- Style properties: `color`, `background_color`, `font_size`

## Column / Row

```python
pn.Column(*children, style={"spacing": 12, "padding": 16, "align_items": "center"})
pn.Row(*children, style={"spacing": 8, "justify_content": "space_between"})
```

Convenience wrappers for `View` with fixed `flex_direction`:

- `Column` = `View` with `flex_direction: "column"` (always vertical)
- `Row` = `View` with `flex_direction: "row"` (always horizontal)

- `*children`: child elements (positional)
- Style properties:
  - `spacing`: gap between children (dp / pt)
  - `padding`: inner padding (int for all sides, or dict with `horizontal`, `vertical`, `left`, `top`, `right`, `bottom`)
  - `align_items`: cross-axis alignment: `"stretch"`, `"flex_start"`, `"center"`, `"flex_end"`, `"leading"`, `"trailing"`
  - `justify_content`: main-axis distribution: `"flex_start"`, `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`, `"space_evenly"`
  - `overflow`: `"visible"` (default), `"hidden"`
  - `background_color`: container background

## SafeAreaView

```python
pn.SafeAreaView(*children, style={"background_color": "#FFF", "padding": 8})
```

Container that respects safe area insets (notch, status bar).

## ScrollView

```python
pn.ScrollView(
    *children,
    horizontal=False,                       # scroll along x instead of y
    content_container_style={"padding": 16, "gap": 12},
    content_inset=pn.EdgeInsets(bottom=80),
    scroll_enabled=True,
    scroll_event_throttle=16,               # ms between on_scroll callbacks
    on_scroll=lambda e: ...,                # ScrollEvent
    on_scroll_begin_drag=..., on_scroll_end_drag=..., on_momentum_scroll_end=...,
    shows_scroll_indicator=True,
    paging_enabled=False,                   # snap to viewport-sized pages (carousel)
    bounces=True,                           # iOS rubber-band overscroll
    keyboard_dismiss_mode=None,             # "none" | "on_drag" | "interactive"
    keyboard_should_persist_taps="never",   # "never" | "always" | "handled"
    snap_to_interval=None, snap_to_alignment="start",
    deceleration_rate="normal",             # "normal" | "fast" | a float
    refresh_control=pn.RefreshControl(refreshing=loading, on_refresh=reload),
    ref=scroll_ref,                         # receives a ScrollViewHandle
    style={"background_color": "#FFF"},
)
```

- `horizontal`: scroll along the x axis instead of the y axis
- `content_container_style`: style for the scrollable content (padding,
  gap, alignment), distinct from `style` (the scroll frame). The children
  are wrapped in one inner `View` carrying this style, so every layout key
  works on every renderer.
- `content_inset`: extra scrollable space around the content, as an
  [`EdgeInsets`][pythonnative.EdgeInsets]
- `scroll_enabled`: when `False`, the user can't scroll (imperative
  scrolling still works)
- `scroll_event_throttle`: minimum milliseconds between `on_scroll`
  callbacks; native emits `on_scroll` only when the app wired it
- `on_scroll`, `on_scroll_begin_drag`, `on_scroll_end_drag`,
  `on_momentum_scroll_end`: callbacks receiving a
  [`ScrollEvent`][pythonnative.ScrollEvent] (`x`, `y`, `content_width`,
  `content_height`, `viewport_width`, `viewport_height`)
- `shows_scroll_indicator`: show/hide the scroll bar
- `paging_enabled`: snap scrolling to multiples of the viewport size
- `bounces`: enable the iOS overscroll bounce
- `keyboard_dismiss_mode`: `"none"`, `"on_drag"`, or `"interactive"`
- `keyboard_should_persist_taps`: whether a tap inside the scroll view
  dismisses the keyboard: `"never"` (default), `"always"`, or `"handled"`
- `snap_to_interval`, `snap_to_alignment`: snap the resting offset to
  multiples of a length, aligned to `"start"`, `"center"`, or `"end"`
- `deceleration_rate`: `"normal"`, `"fast"`, or a per-millisecond factor
  (`0.998` is normal, `0.99` is fast)
- `refresh_control`: pull-to-refresh element (see [`RefreshControl`](#refreshcontrol))
- `ref`: receives a [`ScrollViewHandle`][pythonnative.ScrollViewHandle]
  (`scroll_to`, `scroll_to_end`, `flash_scroll_indicators`,
  `await get_scroll_offset()`)

## TextInput

```python
pn.TextInput(value="", placeholder="Enter text", on_change=handler, secure=False,
             editable=True, clear_button=True, on_focus=f, on_blur=g,
             selection=(start, end), on_selection_change=lambda e: ...,
             on_key_press=lambda e: ..., on_content_size_change=lambda e: ...,
             select_text_on_focus=False, blur_on_submit=None,
             keyboard_type="default", keyboard_appearance="default",
             selection_color="#007AFF", text_content_type="password",
             ref=input_ref,
             style={"font_size": 16, "color": "#000", "background_color": "#FFF"})
```

- `on_change`: callback `(str) -> None` receiving new text
- `on_submit`: callback `(str) -> None` on Return / Done
- `selection`: controlled selection as `(start, end)` UTF-16 offsets;
  `start == end` places the caret
- `on_selection_change`: callback receiving a
  [`SelectionEvent`][pythonnative.SelectionEvent] (`start`, `end`)
- `on_key_press`: callback receiving a
  [`KeyPressEvent`][pythonnative.KeyPressEvent] whose `key` is the typed
  character or `"Backspace"` / `"Enter"`. iOS and Android report only
  what their input pipeline exposes; the browser reports every key.
- `on_content_size_change`: callback receiving a
  [`ContentSizeEvent`][pythonnative.ContentSizeEvent] (`width`,
  `height`) when the measured text size changes (auto-growing
  multiline fields)
- `select_text_on_focus`: select the whole text when the field gains focus
- `blur_on_submit`: whether submitting blurs the field; `None` (default)
  blurs single-line fields and keeps multiline fields focused
- `keyboard_type`: a [`KeyboardType`][pythonnative.KeyboardType]:
  `"default"`, `"email_address"`, `"number_pad"`, `"decimal_pad"`,
  `"phone_pad"`, `"url"`, `"ascii"`, `"numbers_and_punctuation"`,
  `"web_search"`, or `"visible_password"`
- `keyboard_appearance`: iOS keyboard theme, `"default"`, `"light"`, or
  `"dark"`; ignored elsewhere
- `editable`: when `False`, the field is read-only
- `clear_button`: show an inline clear ("x") button while editing
- `on_focus` / `on_blur`: callbacks `() -> None` on focus changes
- `selection_color`: cursor / selection highlight color
- `text_content_type`: autofill hint (`"username"`, `"password"`,
  `"one_time_code"`, ...)
- `ref`: receives a [`TextInputHandle`][pythonnative.TextInputHandle]
  (`focus`, `blur`, `clear`, `select_all`, `set_selection`,
  `await get_value()`)
- Other kwargs: `secure`, `multiline`, `auto_capitalize`, `auto_correct`,
  `auto_focus`, `return_key_type`, `max_length`, `placeholder_color`

## Image

```python
pn.Image(source="https://example.com/photo.jpg",
         placeholder_color="#E2E8F0",
         on_load_start=lambda: ..., on_load=lambda e: ..., on_load_end=lambda: ...,
         on_error=lambda message: ...,
         fade_duration=200, headers={"Authorization": f"Bearer {token}"},
         style={"width": 200, "height": 150, "scale_type": "cover"})
```

- `source`: a bundled [`Asset`][pythonnative.Asset], an image URL
  (`http://...` / `https://...`), an inline `data:` URI, or an absolute
  file path
- `placeholder_color`: background shown while a remote image loads
- `on_load_start`: callback `() -> None` when loading begins
- `on_load`: callback receiving an [`ImageLoadEvent`][pythonnative.ImageLoadEvent]
  (`width`, `height`) once the image is displayed
- `on_load_end`: callback `() -> None` after `on_load` or `on_error`
- `on_error`: callback `(str) -> None` when loading or decoding fails
- `fade_duration`: milliseconds to cross-fade the image in (Android and
  the browser; iOS shows it at once)
- `headers`: extra HTTP headers sent with a network `source`
- Style properties: `width`, `height`, `scale_type` (`"cover"`, `"contain"`, `"stretch"`, `"center"`), `background_color`, `tint_color`

Remote sources load through the shared [image pipeline](images.md):
background download, memory + disk caching, request deduplication,
and decode downsampled to the view's bounds.

## Switch

```python
pn.Switch(value=False, on_change=handler)
```

- `on_change`: callback `(bool) -> None`

## Slider

```python
pn.Slider(value=0.5, min_value=0.0, max_value=1.0, on_change=handler)
```

- `on_change`: callback `(float) -> None`

## ProgressBar

```python
pn.ProgressBar(value=0.5, color="#007AFF", track_color="#EEE", indeterminate=False)
```

- `value`: 0.0 to 1.0
- `color`: color of the filled portion
- `track_color`: color of the unfilled track
- `indeterminate`: animate continuously and ignore `value`

## ActivityIndicator

```python
pn.ActivityIndicator(animating=True, color="#007AFF", size="large")
```

- `animating`: hide the spinner when `False`
- `color`: spinner color
- `size`: `"small"` (default) or `"large"`

## WebView

```python
pn.WebView(
    url="https://example.com",
    html=None,                          # render inline HTML instead of a URL
    on_load=lambda url: ...,            # page finished loading
    on_message=lambda msg: ...,         # window.pythonnative.postMessage(...)
    on_navigation_state_change=lambda url: ...,
    inject_javascript="document.body.style.background='#fff'",
    scroll_enabled=True,
)
```

- `url`: page to load (ignored when `html` is given)
- `html`: inline HTML markup
- `on_load`: callback `(url) -> None` when a page finishes loading
- `on_message`: callback `(str) -> None` for messages posted from page JS
- `on_navigation_state_change`: callback `(url) -> None` on navigation
- `inject_javascript`: JS evaluated after each page load
- `scroll_enabled`: allow scrolling within the web content

## Spacer

```python
pn.Spacer(size=16, flex=1)
```

- `size`: fixed dimension in dp / pt
- `flex`: flex grow factor

## Pressable

```python
pn.Pressable(child, on_press=handler, on_long_press=handler,
             disabled=False, delay_long_press=500,
             android_ripple=pn.Ripple(color="#33000000"))
```

Wraps any child element with tap/long-press handling.

- `disabled`: when `True`, no press callback fires and the view reports
  the disabled accessibility state
- `delay_long_press`: milliseconds a press must be held before
  `on_long_press` fires (default 500)
- `pressed_opacity`: opacity applied while the finger is down (default 0.6)
- `android_ripple`: a [`Ripple`][pythonnative.Ripple] (`color`,
  `borderless`, `radius`, `foreground`) drawn on Android while pressed;
  ignored on iOS and in the browser
- `hit_slop`, `gestures`, `on_layout`: as on `View`

`style` and the single child may also be callables receiving a
[`PressState`][pythonnative.PressState], re-evaluated as the press state
changes:

```python
pn.Pressable(
    lambda state: pn.Text("Pressed" if state.pressed else "Press me"),
    on_press=handler,
    style=lambda state: {"opacity": 0.6 if state.pressed else 1.0},
)
```

## Modal

```python
pn.Modal(*children, visible=show_modal, on_dismiss=handler, on_show=shown,
         on_request_close=lambda: set_show_modal(False),
         title="Confirm", animation_type="slide", transparent=False,
         presentation_style="page_sheet", dismiss_on_backdrop=True,
         status_bar_translucent=False,
         style={"background_color": "#FFF"})
```

Overlay dialog shown when `visible=True`.

- `on_dismiss`: callback `() -> None` once the modal has closed after
  `visible` became `False`
- `on_show`: callback `() -> None` once the modal finishes presenting
- `on_request_close`: callback `() -> None` when the user asks to close
  the modal from outside your content (the Android back button, an iOS
  sheet pull-down, or a tap on an overlay's backdrop); set `visible=False`
  in response. When unset, the modal stays open.
- `status_bar_translucent`: draw the modal under a translucent status bar
  (Android only)
- `animation_type`: `"slide"` (default), `"fade"`, `"none"`
- `transparent`: dim the underlying view instead of fully covering it
- `presentation_style`: `"page_sheet"` (default), `"form_sheet"`,
  `"full_screen"`, `"overlay"`
- `dismiss_on_backdrop`: when `True` (default), a tap on the dimmed backdrop
  of a transparent or `"overlay"` modal, outside its content, calls
  `on_request_close`; `False` ignores those taps and locks an iOS sheet
  against the pull-down

## StatusBar

```python
pn.StatusBar(bar_style="light", background_color="#000000", hidden=False,
             translucent=False, animated=False)
```

Side-effect element that configures the device status bar; it renders
nothing visible.

- `bar_style`: `"light"`, `"dark"`, or `"default"`
- `background_color`: status-bar background (Android only)
- `hidden`: hide the status bar
- `translucent`: draw content under the status bar instead of below it
  (Android only; iOS always draws underneath)
- `animated`: animate `bar_style` and `hidden` changes (iOS only)

## TouchableOpacity

```python
pn.TouchableOpacity(child, on_press=handler, on_long_press=handler,
                    active_opacity=0.2, disabled=False)
```

Tappable wrapper that dips to `active_opacity` while pressed (a thin alias
over [`Pressable`](#pressable)). `disabled=True` ignores presses and dims the
content.

## ImageBackground

```python
pn.ImageBackground(child, source="bg.png", scale_type="cover",
                   style={"width": 320, "height": 180, "padding": 16})
```

Renders `child` content layered over a background image. Composed from an
absolutely-filled `Image` plus a content `View`.

- `source`: image resource name or URL
- `scale_type`: `"cover"` (default), `"contain"`, `"stretch"`, `"center"`

## Checkbox

```python
pn.Checkbox(value=accepted, on_change=set_accepted, label="Accept terms",
            disabled=False, color="#007AFF")
```

- `value`: checked state (`bool`)
- `on_change`: callback `(bool) -> None`
- `label`: optional inline label (also tappable)
- `disabled`: grey out and ignore input
- `color`: tint for the checked box

| Platform | Native view              |
|----------|--------------------------|
| Android  | `android.widget.CheckBox` |
| iOS      | checkmark `UIButton`     |

## SegmentedControl

```python
pn.SegmentedControl(segments=["Day", "Week", "Month"], selected_index=0,
                    on_change=handler, tint_color="#007AFF")
```

- `segments`: list of segment label strings
- `selected_index`: index of the selected segment
- `on_change`: callback `(int) -> None` with the new index
- `tint_color`: accent color for the selected segment

| Platform | Native view              |
|----------|--------------------------|
| Android  | toggle row (`LinearLayout` of buttons) |
| iOS      | `UISegmentedControl`     |

## DatePicker

```python
pn.DatePicker(value="2026-05-31", mode="date", on_change=handler,
              minimum="2026-01-01", maximum="2026-12-31")
```

ISO-8601 string values: `"YYYY-MM-DD"` (date), `"HH:MM"` (time),
`"YYYY-MM-DDTHH:MM"` (datetime).

- `value`: current selection (ISO-8601 string)
- `mode`: `"date"` (default), `"time"`, `"datetime"`
- `on_change`: callback `(str) -> None` with the new ISO-8601 string
- `minimum` / `maximum`: selectable bounds

| Platform | Native view              |
|----------|--------------------------|
| Android  | `DatePickerDialog` / `TimePickerDialog` |
| iOS      | `UIDatePicker`           |

## Picker

```python
pn.Picker(value=selected, items=[{"value": "a", "label": "Apple"}],
          on_change=handler, placeholder="Select…")
```

Native dropdown / select. `items` is a list of `{"value": Any, "label": str}`.

## RefreshControl

```python
pn.ScrollView(child, refresh_control=pn.RefreshControl(
    refreshing=loading, on_refresh=reload, tint_color="#007AFF"))
```

Pull-to-refresh control, an element of type `"RefreshControl"`, passed as the `refresh_control=` prop of a `ScrollView`, `FlatList`, or `SectionList`. The scroll container attaches it to its native scroll view rather than rendering it as a child, and raises `TypeError` for anything that isn't a `RefreshControl`.

- `refreshing`: drive the spinner from state
- `on_refresh`: callback `() -> None` when pulled past threshold
- `tint_color`: spinner color

## TabBar

```python
pn.Element("TabBar", {
    "items": [
        {"name": "Home", "title": "Home"},
        {"name": "Settings", "title": "Settings"},
    ],
    "active_tab": "Home",
    "on_tab_select": handler,
})
```

Native tab bar, typically created automatically by `Tab.Navigator`.

| Platform | Native view              |
|----------|--------------------------|
| Android  | `BottomNavigationView`   |
| iOS      | `UITabBar`               |

- `items`: list of `{"name": str, "title": str}` dicts defining each tab
- `active_tab`: the `name` of the currently active tab
- `on_tab_select`: callback `(str) -> None` receiving the selected tab name

## FlatList

```python
pn.FlatList(data=items, render_item=render_fn, key_extractor=key_fn,
            item_height=44, separator_height=1,
            horizontal=False, num_columns=1,
            list_header=pn.Text("Header"), list_footer=pn.Text("Footer"),
            list_empty=pn.Text("Nothing here"),
            on_end_reached=load_more, on_end_reached_threshold=0.5,
            refresh_control=pn.RefreshControl(refreshing=loading, on_refresh=reload),
            content_container_style={"padding": 8},
            style={"background_color": "#FFF"})
```

- `data`: list of items
- `render_item`: `(item, index) -> Element` function
- `key_extractor`: `(item, index) -> str` for stable keys
- `item_height`: fixed row extent; reduces measurement work in the native
  RecyclerView / UICollectionView containers (see the
  [Lists guide](../guides/lists.md))
- `separator_height`: spacing between items
- `item_separator`: an element, or a zero-argument function returning one,
  rendered after every row except the last
- `horizontal`: scroll horizontally; row extents become widths
- `inverted`: render bottom-up (or right-to-left when `horizontal`), so
  rows appended to `data` appear at the visible end, as in a chat
- `initial_scroll_index`: item index scrolled to, without animation, once
  the list mounts
- `num_columns`: render as a grid of N columns
- `on_scroll`: callback receiving a [`ScrollEvent`][pythonnative.ScrollEvent]
- `on_viewable_items_changed`: callback receiving a list of
  `{"index", "key", "item"}` dicts whenever the visible rows change
- `list_header` / `list_footer`: elements rendered once above / below rows
- `list_empty`: element rendered when `data` is empty
- `on_end_reached`: callback `() -> None` near the end (virtualized)
- `on_end_reached_threshold`: fraction-of-viewport trigger distance
- `content_container_style`: style for the inner content wrapper
- `refresh_control`: pull-to-refresh element (see [`RefreshControl`](#refreshcontrol))
- `ref`: receives a [`ListController`][pythonnative.ListController]

## SectionList

```python
pn.SectionList(sections=[{"title": "A", "data": ["Apple"]}],
               render_item=lambda item, i, s: pn.Text(item),
               render_section_header=lambda section, s: pn.Text(section["title"]),
               sticky_section_headers=True, inverted=False,
               item_separator=lambda: pn.View(style={"height": 1, "background_color": "#EEE"}),
               on_viewable_items_changed=handler)
```

Virtualized list with section headers interleaved between row groups;
shares the windowing engine and most arguments with `FlatList`.

- `sections`: list of `{"title": ..., "data": [...]}` dicts
- `render_item`: `(item, item_index, section_index) -> Element`
- `render_section_header`: `(section, section_index) -> Element`
- `sticky_section_headers`: keep the current section's header pinned at the
  top while its items scroll by (rendered by Python as an overlay)
- `inverted`: render bottom-up
- `item_separator`: rendered between the items of each section, never after
  a header or a section's last item
- `on_viewable_items_changed`: callback receiving `{"index", "key", "item"}`
  dicts for the visible items (flat indices)
