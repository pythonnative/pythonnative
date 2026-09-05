# Collapsing header and bottom sheet

This example combines the interaction toolkit into the two patterns
that define "native feel": a collapsing header driven by the scroll
offset, and a draggable bottom sheet that snaps open or closed based
on release velocity. It exercises `Animated.event`,
`Animated.diff_clamp`, `interpolate`, animated operators, `z_index`,
`pointer_events`, and the `Pan` gesture with a spring release.

Paste it into `app/main.py` of a project scaffolded with `pn init`,
then run `pn preview` (or `pn run ios` / `pn run android`).

```python
import pythonnative as pn
from pythonnative import gestures

HEADER_HEIGHT = 64.0
SHEET_HEIGHT = 280.0


@pn.component
def CollapsingHeaderPage():
    scroll_y = pn.use_animated_value(0.0)

    # The header hides after 64 points of downward travel and comes
    # back on any upward travel: diff_clamp tracks scroll deltas, and
    # the interpolation maps the clamped total onto a negative shift.
    clamped = pn.Animated.diff_clamp(scroll_y, 0.0, HEADER_HEIGHT)
    header_shift = clamped.interpolate([0.0, HEADER_HEIGHT], [0.0, -HEADER_HEIGHT])
    # Fade the title out during the first half of the travel; "clamp"
    # pins the opacity at 0.0 for the rest.
    title_opacity = clamped.interpolate(
        [0.0, HEADER_HEIGHT / 2], [1.0, 0.0], extrapolate="clamp"
    )

    rows = [
        pn.Text(
            f"Row {i}",
            style={"padding": 14, "background_color": "#F8FAFC"},
        )
        for i in range(1, 41)
    ]

    return pn.View(
        pn.ScrollView(
            pn.Column(
                pn.View(style={"height": HEADER_HEIGHT}),  # header spacer
                *rows,
                style={"spacing": 2},
            ),
            on_scroll=pn.Animated.event(y=scroll_y),
            style={"flex": 1},
        ),
        pn.Animated.View(
            pn.Animated.Text(
                "Inbox",
                style={
                    "opacity": title_opacity,
                    "color": "#FFFFFF",
                    "font_size": 20,
                    "font_weight": "700",
                },
            ),
            style={
                "position": "absolute",
                "top": 0, "left": 0, "right": 0,
                "height": HEADER_HEIGHT,
                "z_index": 2,
                "transform": [{"translate_y": header_shift}],
                "background_color": "#4F46E5",
                "justify_content": "center",
                "padding_left": 16,
            },
        ),
        style={"flex": 1},
    )


@pn.component
def BottomSheet(*children, open: bool = False, on_close=None):
    # 0.0 = fully open, SHEET_HEIGHT = fully hidden.
    slide = pn.use_animated_value(0.0 if open else SHEET_HEIGHT)
    drag_origin = pn.use_ref(0.0)

    def _sync_open():
        target = 0.0 if open else SHEET_HEIGHT
        pn.Animated.spring(slide, to=target, stiffness=260, damping=24).start()

    pn.use_effect(_sync_open, [open])

    def on_pan_begin(event):
        drag_origin.current = float(slide)

    def on_pan_change(event):
        # Follow the finger, but never above the open position.
        slide.set_value(
            max(0.0, min(SHEET_HEIGHT, drag_origin.current + event.translation_y))
        )

    def on_pan_end(event):
        # Fast downward flick or past the midpoint: dismiss.
        dismiss = event.velocity_y > 800 or float(slide) > SHEET_HEIGHT / 2
        target = SHEET_HEIGHT if dismiss else 0.0
        pn.Animated.spring(slide, to=target, stiffness=260, damping=24).start()
        if dismiss and on_close is not None:
            on_close()

    # The scrim fades with the sheet position (derived, no listener),
    # and stops intercepting touches entirely while hidden.
    scrim_opacity = 1.0 - slide / SHEET_HEIGHT

    return pn.View(
        pn.Animated.View(
            style=[pn.StyleSheet.absolute_fill(), {
                "background_color": "#0F172A",
                "opacity": scrim_opacity * 0.4,
                "pointer_events": "none",
            }],
        ),
        pn.Animated.View(
            pn.View(  # grab handle
                style={
                    "width": 40, "height": 4,
                    "border_radius": 2,
                    "background_color": "#CBD5E1",
                    "align_self": "center",
                    "margin": {"top": 8, "bottom": 12},
                },
            ),
            *children,
            gestures=[gestures.Pan(
                on_begin=on_pan_begin,
                on_change=on_pan_change,
                on_end=on_pan_end,
            )],
            style={
                "position": "absolute",
                "left": 0, "right": 0, "bottom": 0,
                "height": SHEET_HEIGHT,
                "z_index": 3,
                "transform": [{"translate_y": slide}],
                "background_color": "#FFFFFF",
                "border_top_left_radius": 16,
                "border_top_right_radius": 16,
                "padding": 16,
            },
        ),
        style=[pn.StyleSheet.absolute_fill(), {"pointer_events": "box_none"}],
    )


@pn.component
def App():
    sheet_open, set_sheet_open = pn.use_state(False)

    return pn.View(
        CollapsingHeaderPage(),
        pn.View(
            pn.Button("Open sheet", on_press=lambda: set_sheet_open(True)),
            style={"position": "absolute", "bottom": 24, "right": 16, "z_index": 2},
        ),
        BottomSheet(
            pn.Text("Sheet content", style={"font_size": 17, "font_weight": "600"}),
            pn.Text("Drag down to dismiss, or flick it away."),
            open=sheet_open,
            on_close=lambda: set_sheet_open(False),
        ),
        style={"flex": 1},
    )
```

## How it works

**Collapsing header.** `Animated.event(y=scroll_y)` writes the scroll
offset into `scroll_y` on every scroll event, with no Python listener
required for the animation itself. `Animated.diff_clamp` turns the
absolute offset into clamped travel, so the header reacts to scroll
*direction* rather than position, matching the behavior of toolbar
hiding in native mail and browser apps. The title opacity is derived
with plain arithmetic on the animated node; both derived nodes update
whenever the driver moves.

**Bottom sheet.** The `Pan` gesture writes the drag position into
`slide` directly, so the sheet tracks the finger with no
reconciliation per frame. On release, the velocity decides between
snapping open and dismissing, and `Animated.spring` handles the
settle. The scrim's opacity is `1.0 - slide / SHEET_HEIGHT`, another
derived node, and `pointer_events` keeps the scrim and the sheet's
wrapper from swallowing touches meant for the page underneath.

**Stacking.** The header, the floating button, and the sheet all use
`position: "absolute"` with `z_index` to define the stacking order
explicitly.

## Related reading

- The [Animations guide](../guides/animations.md) covers
  interpolation, operators, `Animated.event`, and `diff_clamp` in
  detail.
- The [Gestures guide](../guides/gestures.md) covers `Pan`, `Fling`,
  and gesture composition.
- The [Styling guide](../guides/styling.md#interaction-surface)
  documents `pointer_events`, `hit_slop`, and `on_layout`.
