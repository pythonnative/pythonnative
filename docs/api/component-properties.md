# Component Property Reference

All visual and layout properties are passed via the `style` dict (or list of dicts) to element functions. Behavioural properties (callbacks, data, content) remain as keyword arguments.

> Layout is computed by PythonNative's pure-Python flexbox engine (see
> [Layout engine](../concepts/layout.md)). The same `style` keys produce the
> same frames on Android and iOS — every property listed below is honoured by
> the engine and applied via `set_frame` on the underlying native view.

## Common layout properties (inside `style`)

All components accept these layout properties in their `style` dict:

### Sizing

- `width` — fixed width in dp (Android) / pt (iOS). Accepts an `int`/`float`,
  or a percentage string like `"50%"` (resolved against the parent's content
  width).
- `height` — fixed height. Same number / percentage rules as `width`.
- `min_width`, `max_width` — width constraints (numbers or `"%"` strings).
- `min_height`, `max_height` — height constraints.
- `aspect_ratio` — width / height ratio. When only one of `width` / `height`
  is known, the other axis is derived from this ratio.

### Flex

- `flex` — shorthand. Setting `flex: N` is equivalent to
  `flex_grow: N, flex_shrink: 1, flex_basis: 0`.
- `flex_grow` — how much a child grows to fill remaining main-axis space.
- `flex_shrink` — how much a child shrinks when its parent runs out of space.
- `flex_basis` — initial main-axis size before grow / shrink is applied
  (`"auto"`, a number, or a percentage string).
- `align_self` — override parent alignment for this child (`"auto"`,
  `"stretch"`, `"flex_start"`, `"center"`, `"flex_end"`).

### Spacing

- `margin` — outer spacing. Accepts a number (all sides), or a dict with any
  of `horizontal`, `vertical`, `left`, `top`, `right`, `bottom`.
- `padding` — inner spacing on container elements. Same shape as `margin`.
- `spacing` — gap between children of a flex container (applied along the
  main axis).
- `gap` — alias for `spacing`.

### Position

- `position` — `"relative"` (default) or `"absolute"`. Absolute children are
  removed from the normal flow and placed using `top` / `right` / `bottom` /
  `left` (numbers or percentage strings).
- `top`, `right`, `bottom`, `left` — offsets used when `position: "absolute"`.

### Other

- `key` — stable identity for reconciliation (passed as a kwarg, not inside
  `style`).

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

- `flex_direction` — `"column"` (default), `"row"`, `"column_reverse"`, `"row_reverse"`
- `justify_content` — `"flex_start"`, `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`, `"space_evenly"`
- `align_items` — `"stretch"`, `"flex_start"`, `"center"`, `"flex_end"`
- `overflow` — `"visible"` (default), `"hidden"`
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
pn.Text(text, style={"font_size": 18, "color": "#333", "bold": True, "text_align": "center"})
```

- `text` — display string (positional)
- Style properties: `font_size`, `color`, `bold`, `text_align`, `background_color`, `max_lines`

## Button

```python
pn.Button(title, on_click=handler, style={"color": "#FFF", "background_color": "#007AFF", "font_size": 16})
```

- `title` — button label (positional)
- `on_click` — callback `() -> None`
- `enabled` — interactive state (kwarg, default `True`)
- Style properties: `color`, `background_color`, `font_size`

## Column / Row

```python
pn.Column(*children, style={"spacing": 12, "padding": 16, "align_items": "center"})
pn.Row(*children, style={"spacing": 8, "justify_content": "space_between"})
```

Convenience wrappers for `View` with fixed `flex_direction`:

- `Column` = `View` with `flex_direction: "column"` (always vertical)
- `Row` = `View` with `flex_direction: "row"` (always horizontal)

- `*children` — child elements (positional)
- Style properties:
  - `spacing` — gap between children (dp / pt)
  - `padding` — inner padding (int for all sides, or dict with `horizontal`, `vertical`, `left`, `top`, `right`, `bottom`)
  - `align_items` — cross-axis alignment: `"stretch"`, `"flex_start"`, `"center"`, `"flex_end"`, `"leading"`, `"trailing"`
  - `justify_content` — main-axis distribution: `"flex_start"`, `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`, `"space_evenly"`
  - `overflow` — `"visible"` (default), `"hidden"`
  - `background_color` — container background

## SafeAreaView

```python
pn.SafeAreaView(*children, style={"background_color": "#FFF", "padding": 8})
```

Container that respects safe area insets (notch, status bar).

## ScrollView

```python
pn.ScrollView(
    child,
    scroll_axis="vertical",        # or "horizontal"
    on_scroll=lambda x, y: ...,    # content offset as the user scrolls
    shows_scroll_indicator=True,
    paging_enabled=False,          # snap to viewport-sized pages (carousel)
    bounces=True,                  # iOS rubber-band overscroll
    keyboard_dismiss_mode=None,    # "none" | "on_drag" | "interactive"
    content_container_style={"padding": 16},
    refresh_control=pn.RefreshControl(refreshing=loading, on_refresh=reload),
    style={"background_color": "#FFF"},
)
```

- `scroll_axis` — `"vertical"` (default) or `"horizontal"`
- `on_scroll` — callback `(x, y) -> None` with the content offset
- `shows_scroll_indicator` — show/hide the scroll bar
- `paging_enabled` — snap scrolling to multiples of the viewport size
- `bounces` — enable the iOS overscroll bounce
- `content_container_style` — style for the inner content wrapper (padding,
  alignment, spacing), distinct from `style` (the scroll frame)
- `keyboard_dismiss_mode` — `"none"`, `"on_drag"`, or `"interactive"`
- `refresh_control` — pull-to-refresh spec (see [`RefreshControl`](#refreshcontrol))

## TextInput

```python
pn.TextInput(value="", placeholder="Enter text", on_change=handler, secure=False,
             editable=True, clear_button=True, on_focus=f, on_blur=g,
             selection_color="#007AFF", text_content_type="password",
             style={"font_size": 16, "color": "#000", "background_color": "#FFF"})
```

- `on_change` — callback `(str) -> None` receiving new text
- `on_submit` — callback `(str) -> None` on Return / Done
- `editable` — when `False`, the field is read-only
- `clear_button` — show an inline clear ("x") button while editing
- `on_focus` / `on_blur` — callbacks `() -> None` on focus changes
- `selection_color` — cursor / selection highlight color
- `text_content_type` — autofill hint (`"username"`, `"password"`,
  `"one_time_code"`, …)
- Other kwargs: `secure`, `multiline`, `keyboard_type`, `auto_capitalize`,
  `auto_correct`, `auto_focus`, `return_key_type`, `max_length`,
  `placeholder_color`

## Image

```python
pn.Image(source="https://example.com/photo.jpg", style={"width": 200, "height": 150, "scale_type": "cover"})
```

- `source` — image URL (`http://...` / `https://...`) or local resource name
- Style properties: `width`, `height`, `scale_type` (`"cover"`, `"contain"`, `"stretch"`, `"center"`), `background_color`

## Switch

```python
pn.Switch(value=False, on_change=handler)
```

- `on_change` — callback `(bool) -> None`

## Slider

```python
pn.Slider(value=0.5, min_value=0.0, max_value=1.0, on_change=handler)
```

- `on_change` — callback `(float) -> None`

## ProgressBar

```python
pn.ProgressBar(value=0.5, color="#007AFF", track_color="#EEE", indeterminate=False)
```

- `value` — 0.0 to 1.0
- `color` — color of the filled portion
- `track_color` — color of the unfilled track
- `indeterminate` — animate continuously and ignore `value`

## ActivityIndicator

```python
pn.ActivityIndicator(animating=True, color="#007AFF", size="large")
```

- `animating` — hide the spinner when `False`
- `color` — spinner color
- `size` — `"small"` (default) or `"large"`

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

- `url` — page to load (ignored when `html` is given)
- `html` — inline HTML markup
- `on_load` — callback `(url) -> None` when a page finishes loading
- `on_message` — callback `(str) -> None` for messages posted from page JS
- `on_navigation_state_change` — callback `(url) -> None` on navigation
- `inject_javascript` — JS evaluated after each page load
- `scroll_enabled` — allow scrolling within the web content

## Spacer

```python
pn.Spacer(size=16, flex=1)
```

- `size` — fixed dimension in dp / pt
- `flex` — flex grow factor

## Pressable

```python
pn.Pressable(child, on_press=handler, on_long_press=handler)
```

Wraps any child element with tap/long-press handling.

## Modal

```python
pn.Modal(*children, visible=show_modal, on_dismiss=handler, on_show=shown,
         title="Confirm", animation_type="slide", transparent=False,
         presentation_style="page_sheet", dismiss_on_backdrop=True,
         style={"background_color": "#FFF"})
```

Overlay dialog shown when `visible=True`.

- `on_dismiss` — callback `() -> None` when dismissed via gesture
- `on_show` — callback `() -> None` once the modal finishes presenting
- `animation_type` — `"slide"` (default), `"fade"`, `"none"`
- `transparent` — dim the underlying view instead of fully covering it
- `presentation_style` — `"page_sheet"` (default), `"form_sheet"`,
  `"full_screen"`, `"overlay"`
- `dismiss_on_backdrop` — tapping the dimmed backdrop dismisses the modal

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

- `source` — image resource name or URL
- `scale_type` — `"cover"` (default), `"contain"`, `"stretch"`, `"center"`

## Checkbox

```python
pn.Checkbox(value=accepted, on_change=set_accepted, label="Accept terms",
            disabled=False, color="#007AFF")
```

- `value` — checked state (`bool`)
- `on_change` — callback `(bool) -> None`
- `label` — optional inline label (also tappable)
- `disabled` — grey out and ignore input
- `color` — tint for the checked box

| Platform | Native view              |
|----------|--------------------------|
| Android  | `android.widget.CheckBox` |
| iOS      | checkmark `UIButton`     |

## SegmentedControl

```python
pn.SegmentedControl(segments=["Day", "Week", "Month"], selected_index=0,
                    on_change=handler, tint_color="#007AFF")
```

- `segments` — list of segment label strings
- `selected_index` — index of the selected segment
- `on_change` — callback `(int) -> None` with the new index
- `tint_color` — accent color for the selected segment

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

- `value` — current selection (ISO-8601 string)
- `mode` — `"date"` (default), `"time"`, `"datetime"`
- `on_change` — callback `(str) -> None` with the new ISO-8601 string
- `minimum` / `maximum` — selectable bounds

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

Pull-to-refresh spec (a plain dict) passed to a `ScrollView` or `FlatList`.

- `refreshing` — drive the spinner from state
- `on_refresh` — callback `() -> None` when pulled past threshold
- `tint_color` — spinner color

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

Native tab bar — typically created automatically by `Tab.Navigator`.

| Platform | Native view              |
|----------|--------------------------|
| Android  | `BottomNavigationView`   |
| iOS      | `UITabBar`               |

- `items` — list of `{"name": str, "title": str}` dicts defining each tab
- `active_tab` — the `name` of the currently active tab
- `on_tab_select` — callback `(str) -> None` receiving the selected tab name

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

- `data` — list of items
- `render_item` — `(item, index) -> Element` function
- `key_extractor` — `(item, index) -> str` for stable keys
- `item_height` — fixed row height; enables native virtualization
- `separator_height` — spacing between items
- `horizontal` — lay rows out left-to-right (eager backend)
- `num_columns` — render as a grid of N columns (eager backend)
- `list_header` / `list_footer` — elements rendered once above / below rows
- `list_empty` — element rendered when `data` is empty
- `on_end_reached` — callback `() -> None` near the end (virtualized)
- `on_end_reached_threshold` — fraction-of-viewport trigger distance
- `content_container_style` — style for the inner content wrapper
- `refresh_control` — pull-to-refresh spec (see [`RefreshControl`](#refreshcontrol))
