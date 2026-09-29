# Assets, Fonts, Icons, and Vector Graphics

Files your app ships with (images, fonts, SVGs, data) live under
`app/assets/`. PythonNative bundles that folder into the iOS app bundle and
the Android APK, serves it in the browser preview, and syncs changes to a
connected device during `pn start`. In code, every asset is addressed by
its path relative to `app/assets/`:

```python
import pythonnative as pn

logo = pn.asset("images/logo.png")
pn.Image(source=logo, style=pn.style(width=120, height=40))
```

Nothing is configured per platform, and no platform tooling (asset
catalogs, `res/drawable-*` folders) is involved.

## Bundled images

```text
app/
└── assets/
    └── images/
        ├── logo.png
        ├── logo@2x.png
        └── logo@3x.png
```

`pn.asset("images/logo.png")` resolves to the density variant closest to
the screen: an exact `@2x` match on a 2x display, otherwise the next
denser file (so the image is downsampled rather than upsampled),
otherwise the densest one available. The logical size of the image is
always the size of the `1x` file, so layout doesn't change from device to
device.

`Image` accepts an `Asset` or a string anywhere it takes a source, and
gains two related props:

```python
pn.Image(
    source="https://example.com/photo.jpg",
    default_source=pn.asset("images/placeholder.png"),  # shown while loading, kept on error
    blur_radius=6,                                       # blur the decoded image
    style=pn.style(width=200, height=120),
)
```

`default_source` must be a local source (an asset, file path, or
`data:` URI).

### Reading assets from Python

`Asset` also works for data files:

```python
config = json.loads(pn.asset("data/config.json").read_text())
pn.asset("data/optional.json").exists()  # -> bool
```

On iOS and in the browser preview the file is read directly. On Android
the APK's assets have no filesystem path, so `read_bytes()` goes through
the native `Assets` module. Prefer parsing once (at module import or in a
`use_memo`) over reading inside a render.

### Measuring and prefetching

[`Images`][pythonnative.Images] measures or warms an image without
displaying it:

```python
size = await pn.Images.get_size(pn.asset("images/hero.png"))   # ImageSize(width, height)
await pn.Images.prefetch("https://example.com/photo.jpg")      # -> True
pn.Images.clear_cache()
```

Both coroutines run on the framework loop, so they are natural inside an
`async def` effect or an `async` event handler.

## Fonts

Drop `.ttf` or `.otf` files anywhere under `app/assets/` and refer to them
by the family name inside the file:

```text
app/assets/fonts/Inter-Regular.ttf
app/assets/fonts/Inter-Bold.ttf
app/assets/fonts/Inter-Italic.ttf
```

```python
pn.Text("Hello", style=pn.style(font_family="Inter", font_weight="700", italic=True))
```

`pn build` parses each font's name and `OS/2` tables and records the
family, weight, and italic flag in the asset manifest. At runtime the
closest registered face for `font_family` + `font_weight` + `italic` is
used; weights that aren't bundled fall back to the nearest one, and a
family that isn't bundled falls through to the platform's system fonts
as before. Rich-text spans (`Text` inside `Text`) accept `font_family`
too.

`pythonnative.assets.font_faces()` lists what the runtime found, which is
handy in a debug screen.

## Icons

[`Icon`][pythonnative.Icon] renders one of the bundled
[Lucide](https://lucide.dev) icons (ISC license, included in the wheel)
as a vector, so it looks the same on every platform:

```python
pn.Icon("heart")                                 # 24 pt, label color
pn.Icon("settings", size=20, color="#6B7280")
pn.Icon("star", fill="#F59E0B", color="#F59E0B")  # solid variant
pn.Icon("menu", stroke_width=1.5)
```

Names are checked at type-check time (`IconName` is a `Literal` of every
name) and at call time (`KeyError` for an unknown name). Browse the set at
[lucide.dev/icons](https://lucide.dev/icons). Tab bars take the same
names:

```python
Tab.Screen("Home", HomeScreen, tab_bar_icon="house")
Tab.Screen("Profile", ProfileScreen, tab_bar_icon=pn.asset("images/avatar-tab.png"))
```

An asset used as a tab icon is drawn as a template image and tinted with
the tab bar's colors.

## Vector graphics

[`Svg`][pythonnative.components.Svg] draws a list of shapes from
[`pythonnative.svg`](../api/graphics.md#svg-shapes-and-parsing) in a single native view:

```python
from pythonnative import svg

pn.Svg(
    svg.Circle(cx=32, cy=32, r=28, fill="#FDE68A", stroke="#B45309", stroke_width=4),
    svg.Path(d="M20 36 q12 14 24 0", stroke="#B45309", stroke_width=4, fill="none"),
    view_box="0 0 64 64",
    style=pn.style(width=96, height=96),
)
```

Shapes: `Path`, `Circle`, `Ellipse`, `Rect`, `Line`, `Polyline`,
`Polygon`, and `G` groups. Each accepts `fill`, `fill_opacity`,
`fill_rule`, `stroke`, `stroke_width`, `stroke_opacity`,
`stroke_linecap`, `stroke_linejoin`, `stroke_dasharray`, `opacity`, and
`transform` (the SVG `transform` grammar). `"currentColor"` resolves to
the `Svg`'s `color` style, or the label color.

Exported `.svg` files load with `svg.load`:

```python
logo = svg.load(pn.asset("vectors/logo.svg"), style=pn.style(width=96, height=96))
```

The parser understands the shape elements above, `<g>`, presentation
attributes and inline `style="..."`, and the root `viewBox`. Text,
gradients, filters, `<use>`, and CSS classes are skipped. That covers
icons and simple illustrations, which is the intended scope.

Native rendering uses Core Graphics on iOS and `Canvas` on Android; the
browser preview emits an inline `<svg>`.

## Gradients and blur

[`LinearGradient`][pythonnative.components.LinearGradient] and
[`BlurView`][pythonnative.components.BlurView] are containers, so children lay out
inside them exactly like a `View`:

```python
pn.LinearGradient(
    pn.Text("Welcome", style=pn.style(color="#FFFFFF")),
    colors=["#6366F1", "#EC4899"],
    start_point=(0, 0),   # unit coordinates: (0, 0) top-left, (1, 1) bottom-right
    end_point=(1, 1),
    locations=[0.0, 1.0],
    style=pn.style(padding=24, border_radius=16),
)

pn.BlurView(
    pn.Text("Now playing"),
    blur_type="dark",   # "light", "dark", "regular", or a system_* material
    intensity=80,       # 0 to 100
    style=pn.style(padding=16, border_radius=12),
)
```

`BlurView` is a `UIVisualEffectView` on iOS and `backdrop-filter` in the
browser. Android has no view-scoped backdrop blur, so the view snapshots
the content beneath it at reduced resolution, blurs the snapshot, and
tints it. That looks right over static backgrounds and approximates
animated ones.

## How bundling works

- `pn build` (and `pn run`) copies `app/assets/` into the iOS bundle as a
  folder reference and into the APK's assets, and writes a
  `pn_assets.json` manifest next to it: every file, the density variants
  of each base name, and the parsed font faces. Native lookup is a
  dictionary hit, not a filesystem probe.
- On Android, `app/assets/` is excluded from the Python source root so
  it isn't packaged twice.
- During `pn start`, the dev client syncs `app/assets/` to the device
  with the rest of `app/`, recomputes the manifest, and pushes it through
  the `Assets` module. Images showing a changed asset reload; new fonts
  register without a restart.
- The browser preview serves `/assets/<path>`, the manifest, and an
  `@font-face` sheet generated from the same manifest.

Asset paths are case-sensitive on device. macOS filesystems usually
aren't, so an image that shows in the browser preview but not on a phone
is most often a case mismatch between the code and the file name.
