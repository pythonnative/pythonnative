"""Demo screen for a shared-element push between two stack screens (``shared_tag``).

The list screen shows a small colored tile; "Open detail" pushes the same
demo with ``detail=True`` onto the root stack, where the tile is a large
hero. Both views carry ``shared_tag="motion-hero"``, so during the push
(and the pop back) the native stack flies the tile between the two
frames, blending its corner radius and color. The hero sets
``shared_transition`` to a spring. Each screen's readout says which one
is showing, so Maestro can assert the push and the pop landed.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText
from pythonnative.motion import SharedTransition

SHARED_TAG = "motion-hero"
_FLIGHT = SharedTransition(spring=pn.Spring(damping_ratio=0.9, duration=450))


@pn.component
def SharedElementDemo(detail: bool = False) -> pn.Node:
    """Render the thumbnail (list) or hero (detail) side of the shared element."""
    nav = pn.use_navigation()

    if detail:
        body = DemoSection(
            "Detail screen",
            ResultText("Showing", "detail"),
            pn.View(
                pn.Text("Hero tile", style=pn.style(color="#FFFFFF", font_weight="700", font_size=20)),
                shared_tag=SHARED_TAG,
                shared_transition=_FLIGHT,
                style=pn.style(
                    height=220,
                    border_radius=4,
                    background_color="#7C3AED",
                    align_items="center",
                    justify_content="center",
                ),
            ),
            Hint("'Back to list' pops this screen; the hero flies back into the thumbnail."),
        )
    else:
        body = DemoSection(
            "List screen",
            ResultText("Showing", "list"),
            pn.View(
                pn.Text("Thumb", style=pn.style(color="#FFFFFF", font_weight="700")),
                shared_tag=SHARED_TAG,
                style=pn.style(
                    width=88,
                    height=88,
                    border_radius=44,
                    background_color="#A855F7",
                    align_items="center",
                    justify_content="center",
                ),
            ),
            ButtonsRow(pn.Button("Open detail", on_press=lambda: nav.push(SharedElementDemo(detail=True)))),
            Hint("Maestro opens the detail screen, asserts 'Showing: detail', and pops back."),
        )
    return DemoScreen("Shared element", "A tile flies between two stack screens with shared_tag.", body)
