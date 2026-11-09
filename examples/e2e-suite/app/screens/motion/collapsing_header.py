"""Demo screen for a collapsing header driven by an ``on_scroll`` worklet.

A fixed-height scroll area sits under an absolutely positioned header.
The scroll view's ``on_scroll`` is a [`@pn.worklet`][pythonnative.worklet],
so the core runs it on the UI thread and the event never reaches Python.
It writes the offset into a shared value; an animated style slides the
header up by the clamped offset and fades it out. A
[`use_animated_reaction`][pythonnative.use_animated_reaction] watches the
offset cross 80 points and reports it with
[`run_on_python`][pythonnative.run_on_python], which is the only thing
Python hears about the scroll, so Maestro can assert the header flipped
from "expanded" to "collapsed".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

HEADER_HEIGHT = 56.0
COLLAPSE_AT = 80.0


@pn.component
def CollapsingHeaderDemo() -> pn.Node:
    """Render a header that slides away as the list scrolls."""
    scroll_y = pn.use_shared_value(0.0)
    header_state, set_header_state = pn.use_state("expanded")

    @pn.worklet
    def track(event: pn.ScrollEvent) -> None:
        scroll_y.value = event.y

    def collapsed_changed(collapsed: bool) -> None:
        set_header_state("collapsed" if collapsed else "expanded")

    pn.use_animated_reaction(
        lambda: scroll_y.value > COLLAPSE_AT,
        lambda collapsed, _previous: pn.run_on_python(collapsed_changed, collapsed),
    )
    header = pn.use_animated_style(
        lambda: {
            "transform": [{"translate_y": -pn.clamp(scroll_y.value, 0, HEADER_HEIGHT)}],
            "opacity": pn.interpolate(scroll_y.value, (0, HEADER_HEIGHT), (1, 0), "clamp"),
        }
    )

    rows = [
        pn.Text(f"HeaderRow {i}", style=pn.style(font_size=15, padding=8, background_color="#F1F5F9"))
        for i in range(1, 61)
    ]

    return DemoScreen(
        "Collapsing header",
        "Scroll down to slide the header away with an on_scroll worklet.",
        DemoSection(
            "Collapsing header demo",
            ResultText("Header state", header_state),
            pn.View(
                pn.ScrollView(
                    pn.Column(
                        # Spacer so the first rows start below the header.
                        pn.View(style=pn.style(height=HEADER_HEIGHT)),
                        *rows,
                        style=pn.style(gap=4),
                    ),
                    on_scroll=track,
                    style=pn.style(height=400),
                ),
                pn.View(
                    pn.Text("Collapsing toolbar", style=pn.style(color="#FFFFFF", font_weight="700")),
                    style=[
                        pn.style(
                            position="absolute",
                            top=0,
                            left=0,
                            right=0,
                            height=HEADER_HEIGHT,
                            z_index=2,
                            background_color="#4F46E5",
                            justify_content="center",
                            padding_left=16,
                        ),
                        header,
                    ],
                ),
                style=pn.style(height=400, border_width=1, border_color="#CBD5E1"),
            ),
            Hint("Maestro scrolls the list and asserts 'Header state: collapsed'."),
        ),
    )
