"""Demo screen for the interaction-surface style props.

Covers four additions in one screen:

- ``pointer_events="none"``: a translucent overlay covers a button, but
  taps pass through it and the counter still increments.
- ``hit_slop``: a deliberately tiny pressable counts taps that land in
  its expanded slop area (and, trivially, on the label itself).
- Per-corner border radius: a box with four distinct corner radii.
- ``z_index``: two overlapping boxes where the later styling (not
  document order) decides which one is on top.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def InteractionPropsDemo() -> pn.Element:
    """Render pointer_events, hit_slop, corner-radius, and z_index demos."""
    through_taps, set_through_taps = pn.use_state(0)
    slop_taps, set_slop_taps = pn.use_state(0)

    pass_through = pn.View(
        pn.Button(
            "Tap through overlay",
            on_press=lambda: set_through_taps(through_taps + 1),
        ),
        # The overlay fully covers the button. With pointer_events="none"
        # it must be invisible to hit testing, so the tap reaches the
        # button underneath.
        pn.View(
            style=pn.style(
                position="absolute",
                top=0,
                left=0,
                right=0,
                bottom=0,
                background_color="#F9731633",
                pointer_events="none",
            ),
        ),
        style=pn.style(align_self="flex_start"),
    )

    slop_target = pn.Pressable(
        pn.Text("Slop target", style=pn.style(font_size=13)),
        on_press=lambda: set_slop_taps(slop_taps + 1),
        hit_slop=16,
        style=pn.style(background_color="#E2E8F0", padding=2, align_self="flex_start"),
    )

    corner_box = pn.View(
        style=pn.style(
            width=120,
            height=80,
            background_color="#0EA5E9",
            border_top_left_radius=4,
            border_top_right_radius=16,
            border_bottom_right_radius=32,
            border_bottom_left_radius=8,
        ),
    )

    z_stack = pn.View(
        pn.View(
            pn.Text("on top", style=pn.style(color="#FFFFFF", font_weight="700")),
            style=pn.style(
                position="absolute",
                top=0,
                left=0,
                width=100,
                height=60,
                z_index=2,
                background_color="#8B5CF6",
                align_items="center",
                justify_content="center",
            ),
        ),
        pn.View(
            pn.Text("underneath", style=pn.style(color="#FFFFFF")),
            style=pn.style(
                position="absolute",
                top=24,
                left=48,
                width=100,
                height=60,
                z_index=1,
                background_color="#64748B",
                align_items="center",
                justify_content="center",
            ),
        ),
        style=pn.style(height=100),
    )

    return demo_screen(
        "Interaction props",
        "pointer_events, hit_slop, per-corner radius, and z_index.",
        section(
            "pointer_events='none' overlay",
            result_text("Through taps", through_taps),
            pass_through,
        ),
        section(
            "hit_slop",
            result_text("Slop taps", slop_taps),
            slop_target,
        ),
        section(
            "Per-corner border radius",
            corner_box,
        ),
        section(
            "z_index",
            z_stack,
            hint("The purple box renders above despite equal stacking context."),
        ),
    )
