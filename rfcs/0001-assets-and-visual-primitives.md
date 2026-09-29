# RFC 0001: Assets and visual primitives

- Status: Implemented
- Author(s): Owen Carey, with Claude (Cursor)
- Created: 2026-09-17
- Implemented in: this pull request
- Supersedes / Superseded by: none

## Summary

PythonNative can render text, controls, lists, navigation, and animation
natively, but an app can't ship its own images or fonts, draw an icon, fill
a view with a gradient, blur a backdrop, or render vector artwork. This RFC
adds a bundled-asset pipeline (`app/assets/`, `pn.asset()`, density
variants, custom fonts), a cross-platform `Icon` component backed by the
Lucide icon set, an `Svg` component with typed shape primitives and an SVG
file loader, `LinearGradient` and `BlurView` containers, and the `Image`
features (`default_source`, `blur_radius`, `Images.get_size`,
`Images.prefetch`) that a production app expects. It removes the
platform-specific tab icon dictionary and the Android system drawable lookup
that the new icon vocabulary replaces.

## Motivation

The gap shows up on the first screen of any real app. Today:

- `pn.Image(source="logo.png")` documents "bundled resources," but nothing
  bundles them. On iOS the name reaches `UIImage(named:)` and fails because
  `app/` is a plain folder reference, not an asset catalog. On Android the
  runtime looks in `res/drawable`, which the builder never populates from
  the project. Density variants (`@2x`, `@3x`) don't exist.
- `font_family="Inter"` is accepted by the type checker and silently falls
  back to the system font, because no font file is ever registered.
- There is no icon component. Tab bars accept `{"ios": "house.fill",
  "android": "ic_menu_compass"}`, so every tab needs two platform names, the
  Android side is limited to a handful of `android.R.drawable` legacy icons,
  and inline icons next to text (the most common use) aren't possible at
  all.
- There are no vector primitives, no gradients, and no blur. These are
  the visual grammar of modern mobile design; React Native apps reach for
  `react-native-svg`, `expo-linear-gradient`, and `expo-blur` almost
  universally.

Every one of these is a blocker for making an app look finished, and they
share one foundation: a way to bundle files into the app and resolve them
at runtime on iOS, Android, and in the browser preview.

## Reference behavior

React Native resolves `require("./logo.png")` at bundle time: Metro picks
the `@2x`/`@3x` file for the device, ships it in the bundle, and the native
`Image` receives a resolved source with a `scale`. Fonts are linked into
the native projects (`UIAppFonts`, `assets/fonts`) and referenced by
family name. Icons, SVG, gradients, and blur come from community
packages.

PythonNative follows the same shape with a Python accent:

- No bundler step. `app/assets/` is copied into the app wholesale (it
  already is, because `app/` is the bundle), and native resolvers pick
  density variants at load time. Python never has to know the device
  scale.
- Assets are values, not `require()` calls: `pn.asset("images/logo.png")`
  returns a frozen `Asset` that serializes to an `asset://` URI. It's
  hashable, comparable, and works in dataclasses and `StyleSheet`s.
- Fonts are declared by dropping files into `app/assets/fonts/`. The
  build tool reads the font's own `name` and `OS/2` tables to learn the
  family, weight, and style, so `font_family="Poppins", font_weight=700`
  selects `Poppins-Bold.ttf` without a mapping file.
- Icons, SVG, gradients, and blur are built in rather than left to
  packages, because the plugin ecosystem doesn't exist yet and these are
  needed to build anything.

## Design

### Directory convention

```
my_app/
  pythonnative.toml
  assets/            # build-time inputs (icon.png, splash.png) - unchanged
  app/
    main.py
    assets/          # runtime assets bundled into the app - new
      images/
        logo.png
        logo@2x.png
        logo@3x.png
      fonts/
        Poppins-Regular.ttf
        Poppins-Bold.ttf
      icons/
        rocket.svg
```

`app/assets/` is the only runtime asset root. It lives under `app/` so it
is bundled by the existing staging code on both platforms and synced to
devices by the existing dev server file sync, with no new configuration.

### Python API

```python
import pythonnative as pn

logo = pn.asset("images/logo.png")           # Asset(path="images/logo.png")
logo.uri                                     # "asset://images/logo.png"
logo.read_bytes()                            # bytes, on every platform

pn.Image(source=logo, style=pn.style(width=120, height=40))
pn.Image(source="https://...", default_source=pn.asset("images/placeholder.png"), blur_radius=8)

size = await pn.Images.get_size(logo)        # ImageSize(width=..., height=...)
await pn.Images.prefetch("https://example.com/hero.jpg")

pn.Text("Hello", style=pn.style(font_family="Poppins", font_weight=700))

pn.Icon("heart", size=24, color="#E11D48")
pn.Icon("settings", size=20, stroke_width=1.5, style=pn.style(margin_right=8))

pn.Svg(
    pn.svg.Circle(cx=12, cy=12, r=10, fill="#0EA5E9"),
    pn.svg.Path(d="M4 12h16", stroke="white", stroke_width=2),
    view_box="0 0 24 24",
    style=pn.style(width=48, height=48),
)
pn.svg.load(pn.asset("icons/rocket.svg"), style=pn.style(width=64, height=64))

pn.LinearGradient(
    pn.Text("Welcome"),
    colors=["#6366F1", "#EC4899"],
    start_point=(0, 0), end_point=(1, 1),
    style=pn.style(padding=24, border_radius=16),
)

pn.BlurView(pn.Text("Over the image"), blur_type="light", intensity=80, style=pn.style(padding=16))
```

Modules and types:

- `pythonnative.assets`: `Asset`, `asset()`, `assets_root()`, `FontFace`,
  `font_faces()`, `scan()` (manifest generation used by the builder and
  the dev server), `read_font_face()` (TTF/OTF `name` and `OS/2` table
  reader). `Asset.path` is validated: relative, forward slashes, no `..`,
  no leading slash.
- `pythonnative.icons`: `Icon` component, `IconName` (a `Literal` of every
  Lucide icon name, generated), `icon_names()`, `icon_shapes(name)`.
- `pythonnative.svg`: shape dataclasses `Path`, `Circle`, `Ellipse`,
  `Rect`, `Line`, `Polyline`, `Polygon`, `G`; `parse(markup)` and
  `load(asset_or_path)` return `Svg` elements.
- `pythonnative.components.graphics`: `Svg`, `LinearGradient`, `BlurView`
  factories, exported from `pythonnative` like every other component.
- `pythonnative.native_modules.images`: `Images.get_size`,
  `Images.prefetch`, `Images.clear_cache`, and the `ImageSize` record.
- `Image` gains `default_source` and `blur_radius`; `source` accepts
  `str | Asset`.
- `ScreenOptions.tab_bar_icon` becomes `IconName | Asset`.

`Asset` is a frozen dataclass whose wire form is a string. The SDK type
system gains a small hook for this case: a class that defines a
`__native_schema__()` classmethod is compiled to that schema instead of to
a record, and unions that collapse to identical alternatives are
deduplicated. Factories convert `Asset` to its URI before building the
element, so the reconciler diffs plain strings.

### Wire contract

- `Image.source` and `Image.default_source` are strings. `asset://<path>`
  is a new scheme alongside `http(s)://`, `file://`, `data:`, and absolute
  paths. Bare names no longer resolve to platform resources.
- `Image.blur_radius` is a number in logical points.
- `Svg` is a leaf component with `shapes` (a list of `SvgShape` records:
  `kind`, geometry fields, paint fields, `transform`), `view_box`,
  `preserve_aspect_ratio`, and default paint props. Shapes are data, not
  child views: one native view draws every shape, the same way `Text`
  flattens rich spans instead of nesting views.
- `LinearGradient` is a container with `colors`, `locations`,
  `start_point`, and `end_point`. (Expo calls the last two `start` and
  `end`; PythonNative can't, because every element merges its style into
  the same prop dict and `start` and `end` are already the RTL-aware
  position insets.)
- `BlurView` is a container with `blur_type` and `intensity`.
- `TabBar.items[].icon` becomes an `IconSpec` record: `{"shapes": [...],
  "view_box": ...}` for vector icons or `{"uri": "asset://..."}` for
  bundled images. Python resolves icon names before they cross the bridge
  so the native side never needs the icon table.
- New native modules: `Assets` (`configure`, `read`, `exists`) and
  `Images` (`get_size`, `prefetch`, `clear_cache`). Both are declared as
  protocols in `sdk/services.py` and generated into Swift and Kotlin
  adapters like the existing modules.
- `PROTOCOL_VERSION` is unchanged; the additions are schema-level and the
  contract fingerprint covers them.

### Asset resolution

Native resolvers own lookup. Given `asset://images/logo.png` and a device
scale `s`:

1. If a dev overlay is configured (debug builds connected to `pn start`),
   look under `<overlay>/app/assets/` first, so a synced change wins over
   the bundled copy.
2. Otherwise look in the bundle: `<Bundle.main.resourcePath>/app/assets/`
   on iOS, the `pn_assets/` folder of the APK's Android assets on Android.
3. Pick the density variant: an exact `@{s}x` match, else the nearest
   variant above `s`, else the highest available, else the base file.
   Images decoded from a variant carry its scale so their logical size is
   the base size.

The builder writes a manifest (`pn_assets.json`: every asset path, the
variants available for each base name, and the parsed font faces) next to
the staged assets so the bundle lookup is a dictionary hit rather than a
filesystem probe. In development, Python computes the same manifest from
the overlay and pushes it to native through `Assets.configure` at startup
and after every sync that touches `app/assets/`. Images already showing
an `asset://` source reload when their file changes.

On Android, `app/assets/` is staged into the APK's real asset folder and
excluded from the Chaquopy Python source root, so it isn't packaged twice
and font files can be opened through `AssetManager` without extraction.

### Fonts

`pythonnative.assets.read_font_face()` parses the `name` table (family,
subfamily, PostScript name) and the `OS/2` table (`usWeightClass`,
`fsSelection` italic bit) of a TrueType or OpenType file, with `head`
`macStyle` as a fallback. The resulting `FontFace(family, weight, italic,
postscript_name, path)` records are the font manifest.

- iOS registers each face with `CTFontManagerRegisterFontsForURL` at
  startup (and on overlay updates) and resolves `font_family` plus weight
  and italic to the PostScript name of the closest registered face. When
  no bundled face matches, `UIFont(name:)` and then the system font are
  used, as today.
- Android loads each face with `Typeface.createFromAsset` (bundle) or
  `Typeface.createFromFile` (overlay) into a cache keyed by family, and
  `TextStyle` picks the nearest weight and italic match. Rich-text spans
  use a `MetricAffectingSpan` that applies the `Typeface` directly, so
  custom faces work inside spans on API 24 and later.
- The browser preview loads `/assets/fonts.css`, an `@font-face` sheet the
  dev server generates from the same manifest.

### Icons

`Icon(name, size=24, color=None, stroke_width=2, fill=None)` is a Python
component that expands a Lucide icon name into an `Svg` element sized
`size` by `size` with the icon's stroke paint. The icon data lives in
`pythonnative/icons/_lucide.json`, generated from the Lucide repository by
`scripts/generate-icons.py`, which also writes the `IconName` `Literal` so
editors autocomplete names and type checkers reject typos. Lucide is
chosen because it is ISC licensed, consistently drawn on a 24-unit grid,
stroke based (so one `color` prop works for every icon), and has over
1,500 icons.

Tab bar icons take the same names or an `Asset`. Native tab bar managers
rasterize the shapes into a template image at the platform's tab icon
size.

### SVG

`Svg` draws a list of shapes in `view_box` coordinates, scaled into the
view's frame with `preserve_aspect_ratio` (`"meet"` by default, or
`"slice"` or `"none"`). Supported shapes are the SVG basic shapes plus
`Path` with the full path grammar (`M L H V C S Q T A Z`, absolute and
relative) and `G` for grouping with a `transform`. Paint props are `fill`,
`fill_opacity`, `fill_rule`, `stroke`, `stroke_width`, `stroke_opacity`,
`stroke_linecap`, `stroke_linejoin`, `stroke_dasharray`, and `opacity`.
Transforms accept the SVG transform list grammar (`translate`, `scale`,
`rotate`, `skewX`, `skewY`, `matrix`).

`pn.svg.parse(markup)` and `pn.svg.load(asset)` turn an SVG document's
supported elements into an `Svg` element; unsupported elements
(`<text>`, gradients, filters, `<use>`, CSS classes) are skipped. This
covers exported icons and simple illustrations, which is the practical
target; full SVG rendering is a non-goal.

Each platform has one path parser: `PNSVGPath` in Swift (producing
`CGPath`), `SvgPath` in Kotlin (producing `android.graphics.Path`), and
the browser uses the DOM's own SVG renderer by emitting `<svg>` markup. The
Swift and Kotlin parsers have unit tests covering every command and the
arc conversion.

### LinearGradient and BlurView

`LinearGradient` is a container view whose background is a
`CAGradientLayer` on iOS, a `LinearGradient` shader drawable on Android,
and a CSS `linear-gradient()` in the browser. `start_point` and
`end_point` are unit coordinates in the view's box, the same model as
Expo's `start` and `end`.

`BlurView` is a `UIVisualEffectView` on iOS with `blur_type` mapping to
`UIBlurEffect.Style` and `intensity` (0 to 100) applied through an
animator paused at that fraction. Android has no system backdrop blur
below API 31 and no view-scoped one at all, so the Android implementation
snapshots the screen content beneath the view at reduced resolution, blurs
it with a two-pass box blur, and draws the result with a tint. The browser
uses `backdrop-filter: blur()`. The documentation states the Android
approximation plainly.

### Tooling

- `Builder` stages `app/assets/` and writes the manifest for each
  platform; Android excludes the directory from the Python source root.
- The dev server serves `/asset/<path>?scale=<n>` (redirecting to the
  chosen density variant so the page can read the scale from the final
  URL) and `/assets/fonts.css`.
- The dev client pushes `Assets.configure` after syncs that touch
  `app/assets/`, and `bootstrap.start` does the same in debug builds so
  a previously synced overlay is honored on a cold start.
- `scripts/generate-icons.py` refreshes the icon data from a Lucide
  release tag.
- `pn doctor` is unchanged; a missing asset is reported by `Image.on_error`
  and in the console.

## Removals

- `ScreenOptions.tab_bar_icon` no longer accepts a `{"ios": ..., "android":
  ...}` dictionary, SF Symbol names, or `android.R.drawable` names. The
  Kotlin `android.R.drawable` reflection lookup and the Swift
  `UIImage(systemName:)` lookup are deleted. One icon vocabulary works on
  every platform, which is the point of the framework.
- `Image` bare resource names (`source="logo"`) no longer probe
  `UIImage(named:)` or `res/drawable`. The only bundled form is
  `asset://` (usually written as `pn.asset(...)`).
- The browser preview's hard-coded emoji tab icon table is deleted in
  favor of rendering the same vector shapes as native.
- Documentation claims about "bundled resources" and "system font names"
  are rewritten to describe what actually works.

No compatibility shims are kept. The project is pre-1.0 and these paths
never worked end to end.

## Alternatives considered

- Resolving assets in Python and sending `file://` paths. Rejected:
  Android bundles assets inside the APK with no file path, and Python
  would need the device scale for variant selection. Native resolvers keep
  Python platform-free.
- Native XML parsing for SVG files. Rejected: it would mean three SVG
  parsers (Swift, Kotlin, browser). Parsing in Python with `xml.etree` and
  shipping shapes over the wire needs one parser and one set of tests, at
  the cost of `Asset.read_bytes()` crossing the bridge on Android.
- A view per SVG shape. Rejected: a 40-shape illustration would be 40
  native views and 40 Yoga nodes. Shapes as data match the existing `Text`
  spans design and keep layout cheap.
- SF Symbols on iOS and Material icons on Android. Rejected as the
  primary API because names don't match and designs drift between
  platforms; a bundled cross-platform set gives one name and one look.
  Platform icon fonts can arrive later as an `Icon` `set=` option.
- Variable fonts. Deferred; static faces cover the common case, and both
  platforms need extra work to select axis values.
- A `[assets]` table in `pythonnative.toml` for runtime assets. Rejected:
  a directory convention needs no configuration and the dev server
  already syncs it.

## Non-goals

- Full SVG rendering (text, gradients, filters, masks, `<use>`, CSS).
- Icon sets other than Lucide, and platform-native icon fonts.
- Variable fonts and font feature settings.
- Image caching policy controls, progressive JPEG, animated GIF/WebP.
- Radial and angular gradients (the wire shape leaves room for them).
- A true Android backdrop blur; the approximation is documented.
- Asset hashing or content-addressed cache busting in release builds.

## Testing and rollout

- Python: unit tests for `Asset` validation, manifest scanning and
  variant grouping, the TTF/OTF face reader (against a fixture font),
  icon lookup and `Icon` output, every `svg` shape and the parser,
  `LinearGradient` and `BlurView` factories, `Image` changes, the
  `Images` fallback size reader, dev server routes, and builder staging.
- Swift: XCTest coverage for `PNSVGPath` (every command, arcs,
  transforms), `PNAssets` variant selection, and the new managers'
  creation and measurement.
- Kotlin: JUnit coverage for `SvgPath` and `PNAssets` variant selection.
- E2E: new demos and Maestro flows for bundled images, custom fonts,
  `Icon`, `Svg`, `LinearGradient`, and `BlurView`, plus an `Images`
  module demo; `hello-world` moves its tab icons to Lucide names and
  draws an `Icon` on its home screen.
- Docs: guides for assets and fonts, icons, and vector graphics; API pages
  for the new modules; `mkdocs build --strict` passes.
- `./scripts/check.sh` and `scripts/check-e2e-coverage.py` pass.

## Decisions recorded during implementation

- The generated `IconName` literal is used only in Python signatures.
  `ScreenOptions.tab_bar_icon` is annotated `str | Asset` on the wire side
  and validated at runtime, so the contract JSON and the generated Swift
  and Kotlin enums don't carry 1,500 cases.
- `Icon` is a composed component rather than a native element type. A
  native `Icon` manager would duplicate `Svg` on three platforms for no
  rendering benefit.
- `Svg(shapes=...)` is typed `Sequence[SvgShape]` because that type is
  what the contract generator reads; `svg.load` and `Icon` pass the
  already-flattened wire dicts through with a cast rather than widening
  the signature (which would have generated a union type on the native
  side for no benefit).
- Android `BlurView` snapshots the window content beneath the view at
  1/6 resolution on each root redraw, box-blurs it in two passes, and
  only invalidates itself when the blurred snapshot's checksum changes, so
  a static screen settles instead of redrawing forever.
- `pn_assets.json` is the single source of truth for variants and fonts
  on every platform; native runtimes only probe the filesystem when a
  path has no manifest entry (dev overlay files added since the last
  manifest push).
