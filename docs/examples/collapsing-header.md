# Collapsing header and bottom sheet

This example combines two patterns that define "native feel": a header
that slides away as you scroll down and comes back as soon as you
scroll up, and a bottom sheet that follows the finger and snaps to a
detent. Both run on the UI thread as [Motion](../guides/motion.md)
worklets, so they keep up with the finger even while Python is busy.
It exercises an `on_scroll` worklet, shared values,
`use_animated_style`, `interpolate`, `clamp`, `with_timing`, `z_index`,
`pointer_events`, and [`BottomSheet`][pythonnative.BottomSheet].

Paste it into `app/main.py` of a project scaffolded with `pn init`,
then run `pn preview` (or `pn run ios` / `pn run android`).

```python
import pythonnative as pn

HEADER_HEIGHT = 64.0


@pn.component
def CollapsingHeaderPage() -> pn.Node:
    # Where the list was on the last scroll event, and how far the
    # header is hidden: 0 is fully shown, HEADER_HEIGHT fully hidden.
    last_y = pn.use_shared_value(0.0)
    hidden = pn.use_shared_value(0.0)

    @pn.worklet
    def track(event: pn.ScrollEvent) -> None:
        delta = event.y - last_y.value
        last_y.value = event.y
        if event.y <= 0:
            hidden.value = 0.0  # always show it at the top, including the bounce
        else:
            hidden.value = pn.clamp(hidden.value + delta, 0, HEADER_HEIGHT)

    @pn.worklet
    def settle(event: pn.ScrollEvent) -> None:
        # Don't leave the header half hidden when the finger lifts.
        target = HEADER_HEIGHT if hidden.value > HEADER_HEIGHT / 2 else 0.0
        hidden.value = pn.with_timing(target, duration=150)

    header = pn.use_animated_style(lambda: {"transform": [{"translate_y": -hidden.value}]})
    # Fade the title out during the first half of the travel; "clamp"
    # holds the opacity at 0 for the rest.
    title = pn.use_animated_style(
        lambda: {"opacity": pn.interpolate(hidden.value, (0, HEADER_HEIGHT / 2), (1, 0), "clamp")}
    )

    rows = [
        pn.Text(f"Row {i}", style={"padding": 14, "background_color": "#F8FAFC"})
        for i in range(1, 41)
    ]

    return pn.View(
        pn.ScrollView(
            pn.Column(
                pn.View(style={"height": HEADER_HEIGHT}),  # header spacer
                *rows,
                style={"gap": 2},
            ),
            on_scroll=track,
            on_scroll_end_drag=settle,
            style={"flex": 1},
        ),
        pn.View(
            pn.Text(
                "Inbox",
                style=[{"color": "#FFFFFF", "font_size": 20, "font_weight": "700"}, title],
            ),
            style=[
                {
                    "position": "absolute",
                    "top": 0, "left": 0, "right": 0,
                    "height": HEADER_HEIGHT,
                    "z_index": 2,
                    "background_color": "#4F46E5",
                    "justify_content": "center",
                    "padding_left": 16,
                },
                header,
            ],
        ),
        style={"flex": 1},
    )


@pn.component
def App() -> pn.Node:
    sheet = pn.use_ref()
    detent, set_detent = pn.use_state(-1)

    return pn.View(
        CollapsingHeaderPage(),
        pn.View(
            pn.Button("Open sheet", on_press=lambda: sheet.current.snap_to(0)),
            style={"position": "absolute", "bottom": 24, "right": 16, "z_index": 2},
        ),
        pn.BottomSheet(
            pn.Column(
                pn.Text("Sheet content", style={"font_size": 17, "font_weight": "600"}),
                pn.Text(f"Detent {detent}" if detent >= 0 else "Closed"),
                pn.Text("Drag the handle up to expand, or flick it down to dismiss."),
                style={"gap": 8, "padding": 16},
            ),
            snap_points=("40%", "85%"),
            index=-1,  # start closed
            on_change=set_detent,
            on_close=lambda: set_detent(-1),
            ref=sheet,
        ),
        style={"flex": 1},
    )
```

## How it works

**Collapsing header.** `track` is a worklet, so the core runs it on the
UI thread every time the list scrolls, and the scroll events never
reach Python. It turns the absolute scroll offset into the header's
hidden distance: each event adds the change in offset, and
`clamp` keeps the total between 0 and the header's height. The header
therefore reacts to the scroll *direction* rather than the position,
like the toolbars of native mail and browser apps. Both animated styles
read `hidden`, so the core reruns them whenever `track` writes it, and
the platform moves the header and fades the title before the frame is
drawn. Animating `transform` and `opacity` keeps every frame free of
layout work (see
[Animatable properties](../guides/motion.md#animatable-properties)).

**Snapping.** `settle` runs when the finger lifts. It's a decision, not
a mapping: it looks at where the header is and assigns a `with_timing`
animation to the nearest end. Because it's a worklet too, the header
settles in the same frame the finger lifts, however busy Python is.

**Bottom sheet.** [`BottomSheet`][pythonnative.BottomSheet] is built
from the same pieces: a `Pan` gesture whose callbacks are worklets, a
shared value for its offset, and a spring that
[`snap_point`][pythonnative.snap_point] aims at the detent the release
velocity projects to. Python hears about the result through
`on_change` and `on_close`, which the sheet calls with
`run_on_python` once a drag settles. The button opens it through the
[`BottomSheetHandle`][pythonnative.BottomSheetHandle] in `ref`.

**Stacking.** The header, the floating button, and the sheet all use
`position: "absolute"` with `z_index` to define the stacking order
explicitly. The sheet presents in a [`Portal`][pythonnative.Portal], so
it covers everything else, and its backdrop ignores touches while it's
closed.

## Related reading

- The [Motion guide](../guides/motion.md) covers worklets, shared
  values, animations, and event worklets in detail.
- The [Gestures guide](../guides/gestures.md) covers `Pan`, `Fling`,
  and gesture composition.
- The [Styling guide](../guides/styling.md#interaction-surface)
  documents `pointer_events`, `hit_slop`, and `on_layout`.
