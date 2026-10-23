# Layout engine

PythonNative uses Yoga 3.2.1 for flexbox layout. The vendored C++ source
compiles into the renderer core, the C++ library every target links: the
iOS and Android apps, the `pythonnative._core` extension that tests load,
and the browser preview's WebAssembly build. Layout runs in the core, on
the thread that commits, never on the platform UI thread. One set of rules
therefore lays out devices, the preview, and headless tests.

## Layout and commits

Rendering commits view creation, relationships, and props. The core
validates the commit, applies it to its shadow tree, lays out the roots
that changed, and returns the changed frames of observed views (those with
a ref or an `on_layout` callback) in the acknowledgement. Layout effects
run after those frames are published, followed by passive effects. The UI
thread mounts the commit afterward, with each view's frame.

Native changes can invalidate geometry too: a container reports a new
size, an image finishes loading, or the font scale changes. The platform
reports these to the core without waiting. The core relayouts on a
worker, queues a frame-only mount transaction, and sends Python the
observed frames as a `layout` message. See
[The native bridge](bridge.md#threads-and-the-deadlock-rule) for the
threads involved.

### Surfaces and detached roots

The surface's screen roots lay out against the viewport Python's host
reports in each commit. Some subtrees live in platform containers instead
of in their parent's box: the children of `VirtualList`, `Modal`, and
`ScreenStack`, `Portal` content, and navigation header slots. Each is a
detached root that lays out against the size its container reports
through `pn_core_report_container`. Until a container reports, its root
uses its parent container's size or the viewport. List rows lay out
against the list's width (vertical lists) or height (horizontal lists),
with the other axis unbounded. Providers and component ownership continue
through those containers.

## Measurement

Leaves declare how the core sizes them in their contract. A leaf is a
measured view with no children; containers size from their style and
children.

| Mode | Components | How |
| --- | --- | --- |
| `container` | `View`, `Row`, `Column`, `ScrollView`, `Pressable`, `Modal`, `Screen`, and the other containers | Style and children only; never measured |
| `text` | `Text` | Thread-safe platform text layout through the platform's `measure` callback, plus the first baseline for `align_items: "baseline"` |
| `image` | `Image` | Computed in the core from the intrinsic size the platform reports once the image loads (`pn_core_report_intrinsic`), scaled down to fit |
| `svg` | `Svg` | Computed in the core from `view_box` (24 by 24 without one) |
| `fill` | `VirtualList` | Takes the available space |
| `intrinsic` | `Button`, `TextInput`, `Switch`, `Slider`, `ProgressBar`, `ActivityIndicator`, `Checkbox`, `Picker`, `SegmentedControl`, `DatePicker`, `TabBar` | A prototype widget configured with the props and measured on the UI thread |

An `intrinsic` measurement keeps the platform's own sizing (UIKit's
`sizeThatFits`, Android's `View.measure`) by making one synchronous hop
to the UI thread from the core's worker. The UI thread never waits for
the core, so the hop can't deadlock. A text input whose content changes
asks the core to re-measure it, and a font scale or content size change
re-measures every leaf. The engine respects the size a leaf returns,
then clamps it to the active `min_*` and `max_*` constraints.

Custom components choose a mode with
[`define_component(..., measurement=...)`][pythonnative.sdk.define_component]:
`"intrinsic"` (the default), `"native"` for a manager that can measure
from props on any thread, or `"container"`. See
[Custom native components](../guides/custom-native-components.md#measurement).

## View flattening

A `View`, `Row`, `Column`, or `Spacer` that only affects layout isn't
mounted. Each contract field says whether it allows flattening. Layout
style keys do, apart from `display` and border widths; everything else
blocks it, including paint props (background, border, shadow, opacity,
transform, `overflow`), event handlers, gestures, animated bindings, and
accessibility and test props, which screen readers and Maestro use to
address views. An `on_layout` callback or a ref doesn't block flattening,
because the core answers layout events and `measure_in_window` from its
shadow tree.

The core mounts a flattened view's children into its nearest mounted
ancestor at the flattened position, offsetting their frames by the
flattened ancestors' positions. When an update adds a blocking prop, the
core creates the view and moves its mounted descendants into it in the
same transaction; removing the prop reverses that. Commands addressed to
a flattened view fail with "view #N isn't mounted (it only affects
layout)". Your component tree, refs, and test queries are unchanged:
flattening only changes what the platform mounts.

## Installation and app builds

The host build of the core is the `pythonnative._core` extension in the
platform-specific PythonNative wheel. Precompiled wheels cover CPython
3.13 and 3.14 on macOS (Intel and Apple Silicon), Linux with glibc (x86-64
and ARM64), and Windows (x86-64). Pip or uv selects the matching wheel.
Building from a source distribution requires a C++20 compiler.

Device builds compile the core, with the Yoga release it embeds, for the
application target. Xcode builds it as the `PNCore` Swift package for
iOS devices or simulators; Gradle invokes CMake and the Android NDK to
build `libpncore.so` for the configured Android ABIs. The mobile apps
don't load the desktop Python extension. See the [iOS](../guides/ios.md)
and [Android](../guides/android.md) guides for toolchain setup.

## Style keys

The core lays out with the following style keys, listed as
`pythonnative.style.LAYOUT_STYLE_KEYS`:

| Group | Keys |
|---|---|
| Sizing | `width`, `height`, `min_width`, `max_width`, `min_height`, `max_height`, `aspect_ratio` |
| Flex | `flex`, `flex_grow`, `flex_shrink`, `flex_basis`, `align_self` |
| Container | `flex_direction`, `justify_content`, `align_items`, `gap`, `row_gap`, `column_gap` |
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

Scrolling containers (`ScrollView`, `VirtualList`, and `ScreenStack`)
clip their content and shrink to the available space unless their style
says otherwise. A `ScrollView`'s children can be larger than the
viewport; the platform scroll view sizes its content to them.

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

Headless tests lay out with the shipping core. Render a component and
read the frames it computed:

```python
import pytest

import pythonnative as pn
from pythonnative.testing import render


def test_row_distributes_flex_children():
    result = render(
        pn.Row(
            pn.View(test_id="a", style={"flex": 1, "height": 20}),
            pn.View(test_id="b", style={"flex": 2, "height": 20}),
            style={"width": 310, "gap": 10},
        )
    )
    a, b = result.get_by_test_id("a"), result.get_by_test_id("b")
    assert a.frame[2] == pytest.approx(100)
    assert b.frame[0] == pytest.approx(110)
```

The fake platform measures leaves with fixed sizes, so geometry tests are
deterministic. See [Testing layouts](../guides/testing.md#testing-layouts).

## Limits

The engine intentionally does **not** implement:

- `position: "fixed"`.
- Float / inline / table / grid layouts.

Wrapping (`flex_wrap: "wrap"` / `"wrap_reverse"`) and RTL flipping
(`direction: "rtl"`, with `start` / `end` edge insets resolving against
the inherited direction) are both supported.

Supported properties follow the public `Style` annotations and the pinned Yoga
version. Platform font metrics can produce different intrinsic sizes, so test
text and control sizes on your deployment targets.

## Next steps

- Browse the `style` keys you can use:
  [Component properties](../api/component-properties.md).
- Read about how the engine is wired in:
  [Reconciliation](reconciliation.md).
- See the platform side of frames and measurement:
  [Native views](native-views.md).
