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
| `max_lines` | int | Truncate after N lines |

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
  `"center"`, `"flex_end"`.
- `overflow`: `"visible"` (default), `"hidden"`.
- `spacing`: gap between children (dp / pt).
- `padding`: inner spacing (int for all sides, or dict).

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
- `margin`: outer spacing (number for all sides, or dict).
- `align_self`: override parent alignment: `"auto"`, `"flex_start"`,
  `"center"`, `"flex_end"`, `"stretch"`.
- `position`: `"relative"` (default) or `"absolute"`.
- `top`, `right`, `bottom`, `left`: edge offsets when
  `position: "absolute"` (number or percentage string).

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
  `"flex_start"`, `"center"`, `"flex_end"`, `"leading"`, `"trailing"`.
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
current scheme, so themed components are dark-mode aware by default:

```python
@pn.component
def ThemedText(text: str = ""):
    theme = pn.use_theme()
    return pn.Text(text, style={"color": theme["text_color"], "font_size": theme["font_size"]})
```

An in-app appearance toggle overrides the system setting through the
[`appearance`](../api/appearance.md) module:

```python
pn.appearance.set_color_scheme("dark")  # force dark everywhere
pn.appearance.set_color_scheme(None)  # follow the system again
```

### Pinning a theme with a provider

To pin an explicit theme for a subtree (ignoring the color scheme),
mount a `ThemeContext` provider; `use_theme` returns the provided
value as-is:

```python
import pythonnative as pn
from pythonnative.style import DEFAULT_DARK_THEME


@pn.component
def DarkPage():
    return pn.Provider(pn.ThemeContext, DEFAULT_DARK_THEME,
        pn.Column(
            ThemedText(text="Always dark!"),
            style={"spacing": 8},
        )
    )
```

### Theme properties

Both light and dark themes include:

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
