# Styling

Style properties are passed via the `style` prop on every element
factory. The value can be a plain dict, a [typed
`Style`](#typed-styles-with-pnstyle) `TypedDict` built with
[`pn.style(...)`][pythonnative.style.style], a list mixing those
(later entries win on key collision), or `None`. PythonNative also
provides a [`StyleSheet`][pythonnative.StyleSheet] utility for
declaring named styles and a theming system via context.

## Inline styles

Pass a `style` dict to components:

```python
pn.Text("Hello", style={"color": "#FF3366", "font_size": 24, "bold": True})
pn.Button("Tap", style={"background_color": "#FF1E88E5", "color": "#FFFFFF"})
pn.Column(pn.Text("Content"), style={"background_color": "#FFF5F5F5"})
```

## Typed styles with `pn.style()`

[`pn.style(**props)`][pythonnative.style.style] is a tiny helper that
returns a [`pn.Style`][pythonnative.style.Style] `TypedDict`. Values are
plain Python `dict` instances at runtime, but the type is fully
recognised by static checkers (mypy, pyright, Pylance) and editors
will autocomplete known keys and `Literal` values:

```python
import pythonnative as pn

heading: pn.Style = pn.style(
    font_size=28,
    font_weight="700",        # Literal: "100".."900" | "bold" | "normal" | …
    text_align="center",      # Literal: "left" | "center" | "right" | "justify"
    color="#0F172A",
)

pn.Text("Welcome", style=heading)
```

Why use `pn.style()` over a raw dict?

- **IDE autocomplete** for every supported key (`flex_direction`,
  `align_items`, `transform`, `shadow_offset`, …).
- **Type-checked literals**: typos like `align_items="centre"` are
  flagged before you ever run the app.
- **Self-documenting code**: the `pn.Style` annotation tells readers
  this dict is meant to flow into the `style` prop.

Because `Style` is `total=False`, every key is optional; you only
include the props you care about. Plain dicts continue to work
everywhere (they're widened to the same `StyleProp` type) and
existing code does not need to change.

### `StyleProp` for component authors

The argument type accepted by every built-in factory is
[`pn.StyleProp`][pythonnative.style.StyleProp]:

```python
StyleProp = Style | dict[str, Any] | list[Style | dict | None] | None
```

Use it in your own components when you want to forward styles
through:

```python
from typing import Optional
import pythonnative as pn

@pn.component
def Card(
    *children: pn.Element,
    style: Optional[pn.StyleProp] = None,
) -> pn.Element:
    base: pn.Style = pn.style(
        padding=16,
        border_radius=12,
        background_color="#FFFFFF",
    )
    return pn.View(*children, style=[base, style])
```

The list form lets callers layer overrides on top of `base` without
losing any keys you didn't override.

## StyleSheet

Create reusable named styles with
[`StyleSheet.create`][pythonnative.style.StyleSheet.create]:

```python
import pythonnative as pn

styles = pn.StyleSheet.create(
    title={"font_size": 28, "bold": True, "color": "#333"},
    subtitle={"font_size": 14, "color": "#666"},
    container={"padding": 16, "spacing": 12, "align_items": "stretch"},
)

pn.Text("Welcome", style=styles["title"])
pn.Column(
    pn.Text("Subtitle", style=styles["subtitle"]),
    style=styles["container"],
)
```

### Composing styles

Merge multiple style dicts with
[`StyleSheet.compose`][pythonnative.style.StyleSheet.compose]:

```python
base = {"font_size": 16, "color": "#000"}
highlight = {"color": "#FF0000", "bold": True}
merged = pn.StyleSheet.compose(base, highlight)
# Result: {"font_size": 16, "color": "#FF0000", "bold": True}
```

### Combining styles with a list

You can also pass a list of dicts to `style`. They are merged left-to-right:

```python
pn.Text("Highlighted", style=[base, highlight])
```

### Flattening styles

Flatten a style or list of styles into a single dict:

```python
pn.StyleSheet.flatten([base, highlight])
pn.StyleSheet.flatten(None)  # returns {}
```

### `StyleSheet.absolute_fill`

Convenience factory for the common "fill the parent" overlay style:

```python
overlay = pn.StyleSheet.absolute_fill()
# {"position": "absolute", "top": 0, "right": 0, "bottom": 0, "left": 0}
pn.View(pn.Text("Loading…"), style=[overlay, {"background_color": "#0008"}])
```

## Colors

Pass hex strings (`#RRGGBB` or `#AARRGGBB`) to color properties inside `style`:

```python
pn.Text("Hello", style={"color": "#FF3366"})
pn.Button("Tap", style={"background_color": "#FF1E88E5", "color": "#FFFFFF"})
```

## Text styling

`Text` accepts the full typography surface inside `style`:

| Prop | Value | Notes |
|---|---|---|
| `font_size` | number | In pt (iOS) / sp (Android) |
| `color` | hex string | `#RRGGBB` or `#AARRGGBB` |
| `bold` | bool | Shorthand for `font_weight: "bold"` |
| `font_weight` | `"normal"`, `"bold"`, `"100"`–`"900"` | |
| `font_family` | string | System font name |
| `italic` | bool | |
| `text_align` | `"left"`, `"center"`, `"right"`, `"justify"` | |
| `letter_spacing` | number | Tracking in points |
| `line_height` | number | Multiple of font size |
| `text_decoration` | `"underline"`, `"line_through"`, or `None` | |
| `text_transform` | `"none"`, `"uppercase"`, `"lowercase"`, `"capitalize"` | Applied before measurement |
| `max_lines` | int | Truncate after N lines |
| `text_shadow_color` | hex string | |
| `text_shadow_offset` | `{"width": x, "height": y}` or `(x, y)` | |
| `text_shadow_radius` | number (blur radius) | |

```python
pn.Text(
    "Headline",
    style={
        "font_size": 28,
        "font_weight": "700",
        "letter_spacing": -0.5,
        "line_height": 32,
        "color": "#0F172A",
    },
)
```

`text_transform` is applied in Python before the string reaches the
native label, so the layout engine measures the transformed text and
rich-text spans inherit the outer element's transform. `"capitalize"`
upper-cases the first character of each word and leaves the rest as
written (it doesn't lower-case like `str.title()`).

Text shadows render through `NSShadow` on iOS and
`TextView.setShadowLayer` on Android. The desktop preview accepts the
keys but draws no shadow, since Tk has no text shadow primitive:

```python
pn.Text(
    "Overlay caption",
    style={
        "color": "#FFFFFF",
        "text_transform": "uppercase",
        "text_shadow_color": "#00000099",
        "text_shadow_offset": {"width": 0, "height": 1},
        "text_shadow_radius": 3,
    },
)
```

### Rich text (nested spans)

`Text` accepts a mix of strings and nested `Text` elements, which
flatten into one native label (a `SpannableString` on Android, an
`NSAttributedString` on iOS). Each nested `Text` styles its own run
and inherits everything it doesn't override from the outer element:

```python
pn.Text(
    "Every plan includes ",
    pn.Text("unlimited builds", style={"bold": True}),
    " and ",
    pn.Text("priority support", style={"color": "#DC2626", "text_decoration": "underline"}),
    ".",
    style={"font_size": 15, "color": "#0F172A"},
)
```

Because the result is a single label, it wraps, truncates
(`max_lines`), and measures as one paragraph; there's no need to
assemble rows of separate `Text` views to mix weights or colors
inline.

### Pressed-state styles

[`Pressable`][pythonnative.Pressable]'s `style` prop also accepts a
callable receiving a state dict, mirroring React Native's
function-style prop. It's called with `{"pressed": bool}` and
re-applied as the press state changes:

```python
pn.Pressable(
    pn.Text("Save"),
    on_press=save,
    style=lambda state: {
        "padding": 12,
        "border_radius": 8,
        "background_color": "#1D4ED8" if state["pressed"] else "#3B82F6",
    },
)
```

## Borders, shadows, and shape

Every element accepts these visual props in `style`:

| Prop | Value |
|---|---|
| `border_radius` | number (uniform) |
| `border_top_left_radius`, `border_top_right_radius`, `border_bottom_left_radius`, `border_bottom_right_radius` | number (per corner) |
| `border_width` | number (in pt / dp) |
| `border_color` | hex string |
| `border_left_width`, `border_top_width`, `border_right_width`, `border_bottom_width` | number (per side) |
| `border_left_color`, `border_top_color`, `border_right_color`, `border_bottom_color` | hex string (per side) |
| `shadow_color` | hex string |
| `shadow_offset` | `{"width": x, "height": y}` |
| `shadow_opacity` | 0.0 – 1.0 |
| `shadow_radius` | number (blur radius) |
| `elevation` | number (Android Material shadow shorthand) |
| `opacity` | 0.0 – 1.0 |
| `tint_color` | hex string (Image only) |

Per-corner radius props override the uniform `border_radius` for the
corners they name, so a "speech bubble" or "top-rounded sheet" shape
needs no images:

```python
pn.View(
    content,
    style={
        "border_top_left_radius": 16,
        "border_top_right_radius": 16,
        "background_color": "#FFFFFF",
    },
)
```

Borders take up space inside the element's frame, exactly like
padding: a child inside a `border_width: 4` parent starts 4 points in
from the parent's edge, and a content-sized parent grows by its border
on every side. This matches Yoga's box model, so styles ported from
React Native line up without adjustment.

Per-side border props override the uniform `border_width` /
`border_color` for the sides they name, so an "underline" card is
just:

```python
pn.View(
    pn.Text("Active tab"),
    style={"border_bottom_width": 2, "border_bottom_color": "#007AFF"},
)
```

On Android, `shadow_color` and `shadow_opacity` apply on API 28+;
older versions fall back to the elevation shadow's default color.
When `shadow_radius` is set without `elevation`, the elevation is
derived from it so shadows show up without extra Android-only props.

```python
pn.View(
    pn.Text("Card"),
    style={
        "padding": 20,
        "background_color": "#FFFFFF",
        "border_radius": 16,
        "border_width": 1,
        "border_color": "#E5E7EB",
        "shadow_color": "#000000",
        "shadow_offset": {"width": 0, "height": 4},
        "shadow_opacity": 0.08,
        "shadow_radius": 12,
        "elevation": 4,
    },
)
```

## Transforms

`transform` is either a 6-element CGAffineTransform-style array or a
shorthand mapping:

```python
pn.View(
    pn.Text("Tilted"),
    style={
        "transform": {"rotate": 15, "scale": 1.1, "translate_x": 10},
    },
)
```

Supported keys: `rotate` (degrees), `scale`, `scale_x`, `scale_y`,
`translate_x`, `translate_y`. For animated transforms, see
[Animations](animations.md).

## Flex layout

PythonNative uses a Yoga-style flexbox layout model implemented in
pure Python (see [Layout engine](../concepts/layout.md)). `View` is
the universal flex container, and `Column`/`Row` are convenience
wrappers that fix the direction.

### Flex container properties

These go in the `style` dict of `View`, `Column`, or `Row`:

- `flex_direction`: `"column"` (default), `"row"`, `"column_reverse"`,
  `"row_reverse"` (only for `View`; `Column` and `Row` have fixed
  directions).
- `justify_content`: main-axis distribution: `"flex_start"`,
  `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`,
  `"space_evenly"`.
- `align_items`: cross-axis alignment: `"stretch"`, `"flex_start"`,
  `"center"`, `"flex_end"`, `"baseline"`.
- `overflow`: `"visible"` (default), `"hidden"`.
- `spacing`: gap between children (dp / pt).
- `padding`: inner spacing (int for all sides, or dict).

`align_items: "baseline"` (rows only) lines children up along a shared
baseline instead of their top edges. Native text handlers report a
size but not the position of the first line's baseline, so the engine
approximates: a leaf's baseline is its height (leaves align along
their bottom edges), and a container's baseline is that of its first
in-flow child. Columns treat `"baseline"` as `"flex_start"`, matching
Yoga.

### Child layout properties

All components accept these in `style`:

- `width`, `height`: fixed dimensions (number in dp / pt, or
  percentage string like `"50%"`).
- `min_width`, `min_height`, `max_width`, `max_height`: size
  constraints.
- `aspect_ratio`: derive the unknown axis from the known one
  (`width / height`).
- `flex`: shorthand for `flex_grow: N, flex_shrink: 1, flex_basis: 0`.
- `flex_grow`, `flex_shrink`, `flex_basis`: explicit flex properties.
- `margin`: outer spacing (number for all sides, a dict, or `"auto"`;
  per-edge keys such as `margin_left` also accept `"auto"`).
- `align_self`: override parent alignment: `"auto"`, `"flex_start"`,
  `"center"`, `"flex_end"`, `"stretch"`, `"baseline"`.
- `display`: `"flex"` (default) or `"none"`. A `"none"` element and
  its subtree are removed from layout entirely: no size, gap, or
  margin is reserved for it and every frame in the subtree is zero.
  Toggle it to hide content without unmounting it (state and native
  views are kept).
- `position`: `"relative"` (default) or `"absolute"`.
- `top`, `right`, `bottom`, `left`: edge offsets when
  `position: "absolute"` (number or percentage string).
- `z_index`: stacking order among siblings. Higher values render on
  top regardless of declaration order; siblings without one keep
  document order. Essential for absolutely positioned overlays like
  collapsing headers and floating action buttons.

### Layout examples

**Centering content:**

```python
pn.View(
    pn.Text("Centered!"),
    style={"flex": 1, "justify_content": "center", "align_items": "center"},
)
```

**Horizontal row with spacer:**

```python
pn.Row(
    pn.Text("Left"),
    pn.Spacer(flex=1),
    pn.Text("Right"),
    style={"padding": 16, "align_items": "center"},
)
```

**Auto margins instead of a spacer:**

Auto margins absorb the free space on the main axis before
`justify_content` is applied, following CSS and Yoga. When any child
on a line has an auto main-axis margin, the remaining space is split
equally among every auto margin on that line and `justify_content` has
no effect. On the cross axis, `margin_top: "auto"` and friends center
or push the child and override `align_items` / `align_self` (including
`stretch`):

```python
pn.Row(
    pn.Text("Left"),
    pn.Text("Right", style={"margin_left": "auto"}),   # pushed to the trailing edge
    style={"padding": 16},
)

pn.Column(
    pn.Text("Centered", style={"margin_horizontal": "auto"}),  # centered without align_items
    style={"flex": 1},
)
```

**Child with flex grow:**

```python
pn.Column(
    pn.Text("Header", style={"font_size": 20, "bold": True}),
    pn.View(pn.Text("Content area"), style={"flex": 1}),
    pn.Text("Footer"),
    style={"flex": 1, "spacing": 8},
)
```

**Horizontal button bar:**

```python
pn.Row(
    pn.Button("Cancel", style={"flex": 1}),
    pn.Button("OK", style={"flex": 1, "background_color": "#007AFF", "color": "#FFF"}),
    style={"spacing": 8, "padding": 16},
)
```

**Absolute positioning:**

```python
pn.View(
    pn.View(style={"position": "absolute", "top": 0, "left": 0,
                   "width": 40, "height": 40, "background_color": "#F00"}),
    pn.View(style={"position": "absolute", "bottom": 0, "right": 0,
                   "width": 40, "height": 40, "background_color": "#0A0"}),
    pn.Text("Centered overlay", style={
        "position": "absolute",
        "top": "50%", "left": "10%", "right": "10%",
        "text_align": "center",
    }),
    style={"width": 240, "height": 160, "background_color": "#EEE"},
)
```

**Aspect-ratio thumbnail grid cell:**

```python
pn.View(
    pn.Image(source="cover.jpg", style={"flex": 1}),
    style={"width": "33%", "aspect_ratio": 1.0, "padding": 4},
)
```

## Layout with Column and Row

`Column` (vertical) and `Row` (horizontal) are convenience wrappers for `View`:

```python
pn.Column(
    pn.Text("Username"),
    pn.TextInput(placeholder="Enter username"),
    pn.Text("Password"),
    pn.TextInput(placeholder="Enter password", secure=True),
    pn.Button("Login", on_press=handle_login),
    style={"spacing": 8, "padding": 16, "align_items": "stretch"},
)
```

### Alignment properties

`Column` and `Row` support `align_items` and `justify_content` inside
`style`:

- **`align_items`**: cross-axis alignment: `"stretch"`,
  `"flex_start"`, `"center"`, `"flex_end"`, `"baseline"`, `"leading"`,
  `"trailing"`.
- **`justify_content`**: main-axis distribution: `"flex_start"`,
  `"center"`, `"flex_end"`, `"space_between"`, `"space_around"`,
  `"space_evenly"`.

```python
pn.Row(
    pn.Text("Left"),
    pn.Spacer(flex=1),
    pn.Text("Right"),
    style={"align_items": "center", "justify_content": "space_between", "padding": 16},
)
```

### Spacing

- `spacing` sets the gap between children in dp (Android) / points (iOS).

### Padding

- `padding: 16`: all sides.
- `padding: {"horizontal": 12, "vertical": 8}`: per axis.
- `padding: {"left": 8, "top": 16, "right": 8, "bottom": 16}`: per
  side.

## Interaction surface

A few props shape how views participate in touch handling and layout
measurement.

### `pointer_events`

The `pointer_events` style key controls whether a view (and its
subtree) takes part in hit testing:

- `"auto"` (default): normal hit testing.
- `"none"`: the view and its children are invisible to touches;
  taps pass through to whatever is underneath.
- `"box_none"`: the view itself ignores touches but its children
  still receive them, the right setting for full-screen overlay
  containers that host a few interactive widgets.
- `"box_only"`: the view receives touches but its children don't.

```python
pn.View(
    style=[pn.StyleSheet.absolute_fill(), {
        "background_color": "#00000022",
        "pointer_events": "none",   # decorative scrim; taps pass through
    }],
)
```

### `hit_slop`

`hit_slop` expands a pressable area beyond the view's visual bounds,
so small controls stay comfortably tappable. Pass a number for a
uniform expansion or a dict with `top` / `left` / `bottom` / `right`:

```python
pn.Pressable(
    pn.Image(source="close.png", style={"width": 16, "height": 16}),
    on_press=dismiss,
    hit_slop=12,   # 40 x 40 effective target
)
```

`View`, `Column`, `Row`, and `Pressable` all accept it.

### `on_layout`

The `on_layout` prop reports the element's computed frame after each
layout pass in which it changed. The payload carries `x`, `y`,
`width`, and `height` in the parent's coordinate space:

```python
def handle_layout(frame):
    set_width(frame["width"])

pn.View(content, on_layout=handle_layout)
```

The callback runs post-commit, so setting state inside it is safe and
schedules a normal re-render. Use it for measure-then-position
patterns (tooltips, anchored popovers) or container-driven item
sizing.

## Dark mode and theming

### Following the system appearance

[`use_color_scheme`][pythonnative.use_color_scheme] returns the
effective scheme (`"light"` or `"dark"`) and re-renders the component
when it changes, including live when the user flips the system
setting while the app is open:

```python
import pythonnative as pn


@pn.component
def Wallpaper():
    scheme = pn.use_color_scheme()
    bg = "#000000" if scheme == "dark" else "#FFFFFF"
    return pn.View(style={"flex": 1, "background_color": bg})
```

[`use_theme`][pythonnative.use_theme] goes one step further: without
any provider it resolves the built-in
[`DEFAULT_LIGHT_THEME`][pythonnative.style.DEFAULT_LIGHT_THEME] or
[`DEFAULT_DARK_THEME`][pythonnative.style.DEFAULT_DARK_THEME] from the
current scheme, so themed components are dark-mode aware by default.
Themes are typed [`Theme`][pythonnative.Theme] records, so
`theme.text_color` autocompletes and a typo is a static error:

```python
@pn.component
def ThemedText(text: str = ""):
    theme = pn.use_theme()
    return pn.Text(text, style={"color": theme.text_color, "font_size": theme.font_size})
```

An in-app appearance toggle overrides the system setting through the
[`appearance`](../api/appearance.md) module:

```python
pn.appearance.set_color_scheme("dark")  # force dark everywhere
pn.appearance.set_color_scheme(None)  # follow the system again
```

### Custom themes and providers

Derive a brand theme from a built-in one with
[`Theme.replace`][pythonnative.style.Theme.replace], then pin it for a
subtree (ignoring the color scheme) with a `ThemeContext` provider.
`use_theme` returns the provided value as-is, and rejects anything
that isn't a `Theme` with a `TypeError`:

```python
import pythonnative as pn

BRAND = pn.DEFAULT_DARK_THEME.replace(primary_color="#FF2D55", border_radius=12)


@pn.component
def DarkPage():
    return pn.ThemeContext.Provider(
        BRAND,
        pn.Column(
            ThemedText(text="Always dark!"),
            style={"spacing": 8},
        ),
    )
```

### Theme fields

Every `Theme` has these fields:

- `primary_color`, `secondary_color`: accent colors.
- `background_color`, `surface_color`: background colors.
- `text_color`, `text_secondary_color`: text colors.
- `error_color`, `success_color`, `warning_color`: semantic colors.
- `font_size`, `font_size_small`, `font_size_large`,
  `font_size_title`: typography.
- `spacing`, `spacing_large`: layout spacing.
- `border_radius`: corner rounding.

## ScrollView

Wrap content in a [`ScrollView`][pythonnative.ScrollView]:

```python
pn.ScrollView(
    pn.Column(
        pn.Text("Item 1"),
        pn.Text("Item 2"),
        style={"spacing": 8},
    )
)
```

## Next steps

- See it in practice: [Forms](../examples/forms.md),
  [Lists](../examples/lists.md).
- Browse the API: [Style](../api/style.md),
  [Components](../api/components.md).
- Forward typed styles through your own widgets:
  [Custom native components](custom-native-components.md).
- Learn about reconciliation and how style props are diffed:
  [Reconciliation](../concepts/reconciliation.md).
