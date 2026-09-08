# Layout engine

PythonNative uses Yoga 3.2.1 for flexbox layout on every renderer. The vendored
C++ source compiles into the Python host binding, Swift runtime, and Android
runtime. The browser preview uses Yoga WebAssembly from the same release.
Native leaf widgets supply intrinsic sizes and text baselines.

## Layout and commits

Rendering first commits view creation, relationships, and props. The native
layout pass then computes geometry and returns changed frames as a batch.
Layout effects run after those frames exist, followed by passive effects.
Viewport changes, text edits, and image completion can invalidate geometry.

Native screens and recycled rows own their physical content rectangles. Yoga
lays out each detached logical root within its native container's available
space. Providers and component ownership continue through those containers.

## Headless layout

Headless tests use `LayoutNode` and `calculate_layout()` through the host Yoga
binding. Stub intrinsic measurements make geometry tests deterministic. Real
font metrics and platform control sizes must also be tested on devices.

## Installation and app builds

The host binding is included in the platform-specific PythonNative wheel.
Precompiled wheels cover CPython 3.13 and 3.14 on macOS (Intel and Apple
Silicon), Linux with glibc (x86-64 and ARM64), and Windows (x86-64). Pip or uv
selects the matching wheel. Building from a source distribution requires a
C++20 compiler.

Device builds compile the bundled Yoga source for the application target.
Xcode builds the `YogaCore` Swift package for iOS devices or simulators;
Gradle invokes CMake and the Android NDK for the configured Android ABIs.
The mobile renderer calls this native library through Swift or Kotlin, so it
doesn't load the desktop Python extension. See the [iOS](../guides/ios.md)
and [Android](../guides/android.md) guides for toolchain setup.

## Style keys

The engine recognises (and the reconciler routes to it) the following
style keys, listed as `pythonnative.layout.LAYOUT_STYLE_KEYS`:

| Group | Keys |
|---|---|
| Sizing | `width`, `height`, `min_width`, `max_width`, `min_height`, `max_height`, `aspect_ratio` |
| Flex | `flex`, `flex_grow`, `flex_shrink`, `flex_basis`, `align_self` |
| Container | `flex_direction`, `justify_content`, `align_items`, `spacing`, `gap` |
| Spacing | `margin`, `padding` |
| Position | `position`, `top`, `right`, `bottom`, `left` |

Numbers are interpreted as dp (Android) / pt (iOS). Percentage
strings (`"50%"`, `"100%"`) are resolved against the parent's
content box.

`flex: N` is shorthand for `flex_grow: N`, `flex_shrink: 1`,
`flex_basis: 0` (matching React Native semantics).

`margin` and `padding` accept either a number (applied to all sides)
or a dict with any of `horizontal`, `vertical`, `left`, `top`,
`right`, `bottom`.

## Intrinsic measurement

Leaf widgets (`Text`, `Button`, `Image`, `TextInput`, `Switch`,
`Slider`, `ProgressBar`, `ActivityIndicator`) ask their backend for
an intrinsic size when neither dimension is fixed. The handler
implements `measure_intrinsic(view, max_w, max_h)`:

- iOS uses the native manager and `UIView.sizeThatFits` with UIKit text metrics.
- Android wraps `View.measure(...)` with `MeasureSpec.AT_MOST` /
  `UNSPECIFIED`.

The engine respects whatever size the widget returns, then clamps it
to the active `min_*` / `max_*` constraints.

`ScrollView` is a special case: the engine deliberately makes the
scroll axis unbounded so that children can be larger than the
viewport, and the wrapper itself is clipped to the available space.

## Absolute positioning

Setting `position: "absolute"` on a child takes it out of the flex
flow. Its size and position come from a combination of `top` /
`right` / `bottom` / `left` and explicit `width` / `height`:

```python
pn.View(
    pn.View(style={
        "position": "absolute",
        "top": 0, "left": 0,
        "width": 40, "height": 40,
        "background_color": "#F00",
    }),
    pn.View(style={
        "position": "absolute",
        "bottom": 8, "right": 8,
        "width": 40, "height": 40,
        "background_color": "#0A0",
    }),
    pn.View(style={  # centered, sized by both edges
        "position": "absolute",
        "top": "25%", "left": "25%",
        "right": "25%", "bottom": "25%",
        "background_color": "#00F",
    }),
    style={"width": 200, "height": 200, "background_color": "#EEE"},
)
```

Absolute children are still constrained by the parent's padding box;
edge offsets are measured from the inside of the padding, just like
in CSS.

## Testing layouts

Use the host Yoga binding to test layout without a simulator or emulator:

```python
from pythonnative.layout import LayoutNode, calculate_layout

root = LayoutNode(
    style={"flex_direction": "row", "padding": 10, "spacing": 5,
           "width": 200, "height": 100},
    children=[
        LayoutNode(style={"width": 50, "height": 20}),
        LayoutNode(style={"flex": 1, "height": 20}),
    ],
)
calculate_layout(root, 400, 300)

assert root.children[0].x == 10  # padding-left
assert root.children[1].x == 65  # 10 + 50 + 5
assert root.children[1].width == 125  # 200 - 10 - 10 - 50 - 5
```

The reconciler also exposes
[`Reconciler.compute_layout_for_test`][pythonnative.reconciler.core.Reconciler.compute_layout_for_test]
so you can render a real component tree (with the mock registry) and
inspect the computed `LayoutNode` tree without having to dig into
private attributes.

## Limits

The engine intentionally does **not** implement:

- `position: "fixed"`.
- Float / inline / table / grid layouts.

Wrapping (`flex_wrap: "wrap"` / `"wrap_reverse"`) and RTL flipping
(`direction: "rtl"`, with `start` / `end` edge insets resolving against
the inherited direction) are both supported.

Supported properties follow the public `Style` annotations and the pinned Yoga
version. Platform font metrics can produce different intrinsic sizes.

## Next steps

- Browse the `style` keys you can use:
  [Component properties](../api/component-properties.md).
- Read about how the engine is wired in:
  [Reconciliation](reconciliation.md).
- See the platform side of `set_frame` /
  `measure_intrinsic`: [Native views](native-views.md).
