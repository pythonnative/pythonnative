# Styling

Every element factory takes a `style` prop. Its value is a
[`Style`][pythonnative.Style] dict, a list of them (later entries win),
or `None`. On top of that, PythonNative gives you three tools that keep
styles typed and consistent as an app grows:

- [`StyleSheet`](#style-sheets) namespaces group named styles with
  attribute access, so a misspelled style name is a static error.
- A [`Theme`](#themes) holds the app's design tokens (colors,
  typography, spacing, and radii), switches with dark mode, and also
  styles the navigators.
- [`use_styles`](#theme-dependent-styles-with-use_styles) derives
  theme-dependent styles once per theme.

## Inline styles

Pass a `style` dict to any component:

```python
pn.Text("Hello", style={"color": "#FF3366", "font_size": 24, "bold": True})
pn.Button("Tap", style={"background_color": "#FF1E88E5", "color": "#FFFFFF"})
pn.Column(pn.Text("Content"), style={"background_color": "#FFF5F5F5"})
```

## Typed styles with `pn.style()`

[`pn.style(**props)`][pythonnative.style.style] returns a
[`pn.Style`][pythonnative.Style], a `TypedDict`. Values are plain
Python `dict` instances at run time, but static checkers (mypy,
pyright, Pylance) know every key, and editors autocomplete keys and
`Literal` values:

```python
import pythonnative as pn

heading: pn.Style = pn.style(
    font_size=28,
    font_weight="700",        # Literal: "100".."900" | "bold" | "normal"
    text_align="center",      # Literal: "left" | "center" | "right" | "justify"
    color="#0F172A",
)

pn.Text("Welcome", style=heading)
```

Why use `pn.style()` over a raw dict?

- **Autocomplete** for every supported key (`flex_direction`,
  `align_items`, `transform`, `shadow_offset`, and the rest).
- **Checked literals:** a typo like `align_items="centre"` is flagged
  before you run the app.
- **Checked keys:** `pn.style()` is typed with `Unpack[Style]`, so
  `pn.style(colour="red")` is a type error, not a silent no-op.

Because `Style` is `total=False`, every key is optional; include only
the ones you need. Plain dict literals are checked the same way when
they're passed straight to `style=` or annotated as `pn.Style`. In
development builds the factories also warn once about each unknown key
or bad value they see at run time. Release builds skip that check.

## Style lists

Pass a list to combine styles. Entries merge left to right, so later
entries win, and `None` entries are skipped. That makes conditional
styles a one-liner:

```python
pn.Text("Saved", style=[Styles.label, Styles.success if saved else None])
pn.View(content, style=[Styles.card, {"opacity": 0.5}])
```

A list is the only composition tool you need: there's no `compose` or
`flatten` helper to learn. When you need the merged dict itself (for
example, to read one key), call
[`pn.resolve_style`][pythonnative.style.resolve_style], which flattens a
style prop into a fresh dict.

### Styles in your own components

The type every built-in factory accepts is
[`pn.StyleProp`][pythonnative.style.StyleProp]:

```python
StyleProp = Style | Sequence[Style | None] | None
```

Annotate a `style` parameter with it when your component passes the
caller's style through unchanged. When the component layers the
caller's style over its own, take a single `pn.Style` instead, so the
list stays one level deep:

```python
import pythonnative as pn


class CardStyles(pn.StyleSheet):
    card = pn.style(padding=16, border_radius=12, background_color="#FFFFFF")


@pn.component
def Card(*children: pn.Node, style: pn.Style | None = None) -> pn.Node:
    return pn.View(*children, style=[CardStyles.card, style])


@pn.component
def Panel(*children: pn.Node, style: pn.StyleProp = None) -> pn.Node:
    return pn.ScrollView(*children, style=style)
```

Callers can then override any key of `card` without losing the keys
they don't override: `Card(pn.Text("Hi"), style={"padding": 24})`.

## Style sheets

Group the styles a module uses in a
[`StyleSheet`][pythonnative.StyleSheet] namespace. Subclass it and
assign styles as class attributes:

```python
import pythonnative as pn


class Styles(pn.StyleSheet):
    container = pn.style(padding=16, gap=12, align_items="stretch")
    title = pn.style(font_size=28, bold=True, color="#333333")
    subtitle = pn.style(font_size=14, color="#666666")


@pn.component
def Welcome() -> pn.Node:
    return pn.Column(
        pn.Text("Welcome", style=Styles.title),
        pn.Text("Subtitle", style=Styles.subtitle),
        style=Styles.container,
    )
```

- **Attribute access is typed.** `Styles.titel` is a static error, and
  your editor autocompletes style names. (A dict of styles would accept
  any string key.)
- **Styles are checked once.** In development builds each style's
  keys are validated when the class is defined, instead of every time
  an element is built.
- **It's a namespace, not an object.** Calling `Styles()` raises
  `TypeError`; refer to `Styles.title` directly.

[`pn.ABSOLUTE_FILL`][pythonnative.style.ABSOLUTE_FILL] is the common
"fill the parent" overlay style, like React Native's
`StyleSheet.absoluteFill`:

```python
pn.View(pn.Text("Loading..."), style=[pn.ABSOLUTE_FILL, {"background_color": "#00000088"}])
```

Style sheets hold fixed values. For styles built from theme tokens,
see [`use_styles`](#theme-dependent-styles-with-use_styles) below.

## Themes

A [`Theme`][pythonnative.Theme] is a frozen, keyword-only dataclass of
design tokens. Components read the active one with
[`use_theme`][pythonnative.use_theme], and the built-in navigators draw
their headers, tab bars, and drawers from the same tokens, so one theme
styles the whole app.

| Field | Type | Tokens |
| --- | --- | --- |
| `dark` | `bool` | Whether the theme is meant for a dark appearance |
| `colors` | [`Colors`][pythonnative.Colors] | `primary`, `background`, `surface`, `text`, `text_secondary`, `border`, `error`, `success`, `warning` |
| `typography` | [`Typography`][pythonnative.Typography] | `title`, `heading`, `body`, `label`, `caption`, each a `Style` |
| `spacing` | [`Spacing`][pythonnative.Spacing] | `xs` (4), `sm` (8), `md` (16), `lg` (24), `xl` (32) |
| `radii` | [`Radii`][pythonnative.Radii] | `sm` (4), `md` (8), `lg` (16), `full` (9999) |

```python
@pn.component
def Section(*children: pn.Node, title: str) -> pn.Node:
    theme = pn.use_theme()
    return pn.View(
        pn.Text(title, style=[theme.typography.heading, {"color": theme.colors.text}]),
        *children,
        style={
            "background_color": theme.colors.surface,
            "border_radius": theme.radii.md,
            "padding": theme.spacing.md,
            "gap": theme.spacing.sm,
        },
    )
```

Without a provider, `use_theme()` returns the built-in
[`LIGHT_THEME`][pythonnative.LIGHT_THEME] or
[`DARK_THEME`][pythonnative.DARK_THEME] for the current color scheme,
and re-renders the component when the scheme changes. Themed components
are therefore dark-mode aware by default.

### Custom themes

Provide your own light and dark themes with
[`ThemeProvider`][pythonnative.ThemeProvider] at the root of the app.
It picks `light` or `dark` from the effective color scheme. Derive a
theme from a built-in one with
[`dataclasses.replace`][dataclasses.replace]:

```python
from dataclasses import replace

import pythonnative as pn

LIGHT = replace(pn.LIGHT_THEME, colors=replace(pn.LIGHT_THEME.colors, primary="#5B21B6"))
DARK = replace(pn.DARK_THEME, colors=replace(pn.DARK_THEME.colors, primary="#A78BFA"))


@pn.component
def Home() -> pn.Node:
    theme = pn.use_theme()
    return pn.Text("Hello", style=[theme.typography.title, {"color": theme.colors.primary}])


@pn.component
def App() -> pn.Node:
    return pn.ThemeProvider(Home(), light=LIGHT, dark=DARK)
```

In an app with navigation, wrap the container,
`pn.ThemeProvider(pn.NavigationContainer(Root), light=LIGHT, dark=DARK)`,
so the navigators' headers and tab bars use the same colors. Pass the same theme as both `light` and `dark` to pin it regardless of
the appearance. A nested `ThemeProvider` overrides the theme for its
subtree only.

### Adding tokens

Themes are dataclasses, so you add tokens by subclassing. Keep
`frozen=True, kw_only=True`, give the new fields defaults, and read
the subclass with `use_theme(BrandTheme)`, which returns a
`BrandTheme` to your type checker:

```python
from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True, kw_only=True)
class BrandTheme(pn.Theme):
    accent: pn.Color = "#FF2D55"
    card_elevation: float = 4


LIGHT = BrandTheme(colors=replace(pn.LIGHT_THEME.colors, primary="#5B21B6"))
DARK = BrandTheme(dark=True, colors=replace(pn.DARK_THEME.colors, primary="#A78BFA"), accent="#FF6482")


@pn.component
def Badge(count: int) -> pn.Node:
    theme = pn.use_theme(BrandTheme)
    return pn.Text(str(count), style={"background_color": theme.accent, "color": "#FFFFFF"})


@pn.component
def App() -> pn.Node:
    return pn.ThemeProvider(Badge(count=3), light=LIGHT, dark=DARK)
```

`use_theme(BrandTheme)` raises `TypeError` when the active theme isn't
a `BrandTheme`, which usually means the app forgot its
`ThemeProvider`.

### Theme-dependent styles with `use_styles`

Building style dicts from tokens on every render is noisy and
allocates new dicts each time. [`use_styles`][pythonnative.use_styles]
calls a factory with the active theme once per theme and returns the
result. The usual factory is a small class whose `__init__` takes the
theme and assigns styles as attributes, so the styles are typed and
misspelled names are static errors:

```python
import pythonnative as pn


class RowStyles:
    def __init__(self, theme: pn.Theme) -> None:
        self.row = pn.style(
            padding=theme.spacing.md,
            gap=theme.spacing.xs,
            border_bottom_width=1,
            border_bottom_color=theme.colors.border,
        )
        self.title: pn.Style = {**theme.typography.label, "color": theme.colors.text}
        self.subtitle: pn.Style = {**theme.typography.caption, "color": theme.colors.text_secondary}


@pn.component
def MessageRow(sender: str, preview: str) -> pn.Node:
    styles = pn.use_styles(RowStyles)
    return pn.Column(
        pn.Text(sender, style=styles.title),
        pn.Text(preview, style=styles.subtitle),
        style=styles.row,
    )
```

`use_styles` accepts any callable that takes a theme, including a
plain function. A factory may annotate its parameter with your `Theme`
subclass (`def __init__(self, theme: BrandTheme)`) to read custom
tokens; `use_styles` passes it the active theme, so provide
`BrandTheme` instances with `ThemeProvider`. When the user switches to
dark mode, the component re-renders and the factory runs again with
the dark theme; otherwise every render reuses the same style objects.

Use a `StyleSheet` for styles that never change and `use_styles` for
styles that read the theme. Both combine freely in style lists.

### Dark mode

Three tools cover dark mode, from most to least common:

- **Theme tokens.** Components that read colors from the theme (with
  `use_theme` or `use_styles`) switch automatically.
- **Dynamic colors.** A [`DynamicColor`][pythonnative.DynamicColor],
  written `{"light": ..., "dark": ...}`, is resolved by the renderer
  itself, without a re-render. See [Colors](#colors).
- **The color scheme itself.**
  [`use_color_scheme`][pythonnative.use_color_scheme] returns the
  effective scheme (`"light"` or `"dark"`) and re-renders the component
  when it changes, including live when the user flips the system
  setting while the app is open.

```python
@pn.component
def Wallpaper() -> pn.Node:
    scheme = pn.use_color_scheme()
    return pn.Image(source="night.png" if scheme == "dark" else "day.png", style={"flex": 1})
```

An in-app appearance toggle overrides the system setting through the
[`appearance`](../api/appearance.md) module. `ThemeProvider`,
`use_theme`, and every renderer follow the override:

```python
pn.appearance.set_color_scheme("dark")  # force dark everywhere
pn.appearance.set_color_scheme(None)  # follow the system again
```

## Colors

Pass hex strings (`#RRGGBB` or `#AARRGGBB`) to color properties inside `style`:

```python
pn.Text("Hello", style={"color": "#FF3366"})
pn.Button("Tap", style={"background_color": "#FF1E88E5", "color": "#FFFFFF"})
```

Every color key is typed as [`Color`][pythonnative.Color]: a string, or
a [`DynamicColor`][pythonnative.DynamicColor] dictionary with a `light`
and a `dark` entry. iOS, Android, and the browser preview all resolve
the pair against the current color scheme when the style is applied and
switch when the appearance changes, without a re-render:

```python
pn.View(style=pn.style(background_color={"light": "#FFFFFF", "dark": "#000000"}))
```

## Text styling

`Text` accepts the full typography surface inside `style`:

| Prop | Value | Notes |
|---|---|---|
| `font_size` | number | In pt (iOS) / sp (Android) |
| `color` | hex string | `#RRGGBB` or `#AARRGGBB` |
| `bold` | bool | Shorthand for `font_weight: "bold"` |
| `font_weight` | `"normal"`, `"bold"`, `"100"`–`"900"` | |
| `font_family` | string | System font name or the family of a font under `app/assets/` (see [Assets](assets.md#fonts)) |
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

Text shadows render through `NSShadow` on iOS,
`TextView.setShadowLayer` on Android, and CSS `text-shadow` in the
browser preview:

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
callable, mirroring React Native's function-style prop. It receives a
[`PressState`][pythonnative.PressState] (a frozen dataclass with
`pressed: bool`) and is re-applied as the press state changes; a
single callable child receives the same state:

```python
pn.Pressable(
    lambda state: pn.Text("Saving" if state.pressed else "Save"),
    on_press=save,
    disabled=not valid,
    android_ripple=pn.Ripple(color="#33000000"),
    style=lambda state: pn.style(
        padding=12,
        border_radius=8,
        background_color="#1D4ED8" if state.pressed else "#3B82F6",
    ),
)
```

`disabled=True` suppresses every press callback and sets the disabled
accessibility state. [`Ripple`][pythonnative.Ripple] draws Android's
material ripple while pressed and is ignored on iOS and in the browser,
where `pressed_opacity` or the callable style provides the feedback.

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
| `border_style` | `"solid"` (default), `"dashed"`, or `"dotted"`, drawn the same way on every renderer |
| `shadow_color` | hex string (iOS and browser) |
| `shadow_offset` | `{"width": x, "height": y}` or `(x, y)` (iOS and browser) |
| `shadow_opacity` | 0.0 – 1.0 (iOS and browser) |
| `shadow_radius` | number (blur radius; iOS and browser) |
| `elevation` | number (Android Material shadow) |
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

Shadows follow React Native's platform split: the `shadow_*` keys draw
on iOS and in the browser preview, `elevation` draws Android's material
shadow, and each platform ignores the other's keys (Android no longer
silently accepts `shadow_offset`). A card that looks right everywhere
sets both:

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

`transform` ([`TransformSpec`][pythonnative.TransformSpec]) is a single
operation or an ordered list of operations, each a one-key mapping:

```python
pn.View(
    pn.Text("Tilted"),
    style={
        "transform": [{"rotate": 15}, {"scale": 1.1}, {"translate_x": 10}],
    },
)

pn.View(
    card,
    style={"transform": [{"perspective": 800}, {"rotate_y": "35deg"}]},
)
```

Supported operations on every renderer: `rotate` (degrees, or a string
with a `deg` or `rad` suffix), `rotate_x`, `rotate_y`, `rotate_z`,
`scale`, `scale_x`, `scale_y`, `translate_x`, `translate_y`, `skew_x`,
`skew_y`, and `perspective` (the distance for the 3D rotations that
follow it in the list). iOS composes the list into a `CATransform3D`;
Android applies skew through the animation matrix on API 29 and later
and ignores it below that with a one-time log. For animated transforms,
see [Animations](animations.md).

## Flex layout

PythonNative uses the shared Yoga flexbox engine, compiled into each mobile
runtime and provided as WebAssembly in the browser preview (see
[Layout engine](../concepts/layout.md)). `View` is
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
- `gap`: space between children (dp / pt). `row_gap` and `column_gap`
  set one axis.
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
- `inset`, `inset_horizontal`, `inset_vertical`: shorthands for all
  four edges, the horizontal pair, or the vertical pair, mirroring the
  padding vocabulary; explicit edge keys win. `pn.style(position="absolute", inset=0)`
  is the same overlay as `pn.ABSOLUTE_FILL`.
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
    style={"flex": 1, "gap": 8},
)
```

**Horizontal button bar:**

```python
pn.Row(
    pn.Button("Cancel", style={"flex": 1}),
    pn.Button("OK", style={"flex": 1, "background_color": "#007AFF", "color": "#FFF"}),
    style={"gap": 8, "padding": 16},
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
    style={"gap": 8, "padding": 16, "align_items": "stretch"},
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

### Gap

- `gap` sets the space between children in dp (Android) and points
  (iOS). `row_gap` and `column_gap` set one axis. Use the theme's
  [spacing scale](#themes) to keep gaps consistent.

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
    style=[pn.ABSOLUTE_FILL, {
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
layout pass in which it changed. The callback receives a
[`LayoutEvent`][pythonnative.LayoutEvent] with `x`, `y`, `width`, and
`height` in the parent's coordinate space:

```python
def handle_layout(frame: pn.LayoutEvent) -> None:
    set_width(frame.width)

pn.View(content, on_layout=handle_layout)
```

The same frame is available without a callback as `ref.current.frame`
on the element's [handle](../api/handles.md).

The callback runs post-commit, so setting state inside it is safe and
schedules a normal re-render. Use it for measure-then-position
patterns (tooltips, anchored popovers) or container-driven item
sizing.

## ScrollView

Wrap content in a [`ScrollView`][pythonnative.ScrollView]. Style the
frame with `style` and the scrollable content with
`content_container_style`; the children are wrapped in one inner
`View` carrying that style, so padding, gap, and alignment work on
every renderer:

```python
pn.ScrollView(
    pn.Text("Item 1"),
    pn.Text("Item 2"),
    horizontal=False,
    content_container_style=pn.style(padding=16, gap=8),
    content_inset=pn.EdgeInsets(bottom=80),   # keep the last row clear of a footer
    style=pn.style(flex=1),
)
```

`horizontal=True` scrolls along the x axis. `scroll_enabled=False`
freezes user scrolling while imperative scrolling through the
[`ScrollViewHandle`][pythonnative.ScrollViewHandle] still works;
`snap_to_interval` and `snap_to_alignment` build carousels;
`keyboard_should_persist_taps` decides whether a tap inside the scroll
view dismisses the keyboard (`"never"`, `"always"`, or `"handled"`);
and `deceleration_rate` (`"normal"`, `"fast"`, or a float) tunes the
fling. `on_scroll`, `on_scroll_begin_drag`, `on_scroll_end_drag`, and
`on_momentum_scroll_end` each receive a
[`ScrollEvent`][pythonnative.ScrollEvent]; `scroll_event_throttle` (in
milliseconds) caps how often `on_scroll` fires.

## Next steps

- See it in practice: [Forms](../examples/forms.md),
  [Lists](../examples/lists.md).
- Browse the API: [Style](../api/style.md),
  [Components](../api/components.md).
- Forward typed styles through your own widgets:
  [Custom native components](custom-native-components.md).
- Learn about reconciliation and how style props are diffed:
  [Reconciliation](../concepts/reconciliation.md).
