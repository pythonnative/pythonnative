# Layout engine

PythonNative ships its own pure-Python flexbox engine. It is a small,
React-Native-compatible re-implementation of the subset of the
[Yoga](https://www.yogalayout.com/) algorithm that real apps use.
Every screen on every platform is sized and positioned by the same
Python code; the native handlers only get told *what frame to apply*.

This page covers what the engine does, where it sits in the render
pipeline, what `style` keys it understands, and how to test layouts
without a device.

## Why a Python engine?

The handlers used to delegate to `LinearLayout` (Android) and
`UIStackView` (iOS), which made `View` / `Column` / `Row` look right
"on average" but came with three problems:

1. **Platform drift.** The two stacks have subtly different alignment
   semantics, padding handling, and weight rules. A layout that looked
   correct on iOS could be off by a few points on Android.
2. **No `position: "absolute"`.** Neither container natively supports
   removing a child from the flow and pinning it by edge offsets.
3. **Limited expressiveness.** `flex_basis`, `aspect_ratio`,
   percentage sizes, `min_*` / `max_*` constraints, and `align_self`
   were either missing or partial.

Centralising layout in Python fixes all three: the rules are written
once, exercised by unit tests, and produce identical frames on Android
and iOS.

## Where it sits in the render loop

```text
render -> commit (create / update native views via handlers)
      -> flush effects
      -> build LayoutNode tree from VNodes
      -> calculate_layout(viewport_w, viewport_h)
      -> backend.set_frame(view, x, y, w, h) for every node
```

The layout pass runs after the commit and effect phases, so by the
time it executes:

- All native views exist.
- All visual props are up to date.
- All effects have run (including any that may set state and trigger
  another render).

A render that does not change the tree still triggers a layout pass
when the viewport size changes (e.g., on rotation).

## The `LayoutNode` tree

The reconciler walks the [`VNode`][pythonnative.reconciler.VNode]
tree and builds a parallel tree of
[`LayoutNode`][pythonnative.layout.LayoutNode] objects. Each node
carries:

- The element `type` and the resolved `style` dict.
- A reference back to the `VNode` (so frames can be applied to its
  native handle).
- An optional `measure` callback for leaf widgets that need to ask
  their handler for an intrinsic content size.

The reconciler always wraps the user's root in a synthetic
*viewport node* sized to the current screen so that `flex: 1` / `100%`
at the top level "just work".

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

- iOS uses `UIView.sizeThatFits_(CGSize(max_w, max_h))`.
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

The layout engine is pure Python, so it is trivial to test in
isolation:

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
[`Reconciler.compute_layout_for_test`][pythonnative.reconciler.Reconciler.compute_layout_for_test]
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

Everything else from the React Native flexbox cheat-sheet is
supported.

## Next steps

- Browse the `style` keys you can use:
  [Component properties](../api/component-properties.md).
- Read about how the engine is wired in:
  [Reconciliation](reconciliation.md).
- See the platform side of `set_frame` /
  `measure_intrinsic`: [Native views](native-views.md).
