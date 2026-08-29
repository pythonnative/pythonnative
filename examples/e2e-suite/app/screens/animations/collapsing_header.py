"""Demo screen for scroll-driven animation via ``Animated.event``.

A fixed-height scroll area sits under an absolutely positioned header.
``Animated.event`` binds the scroll offset to an ``AnimatedValue``;
``Animated.diff_clamp`` plus interpolation slides the header out of the
way as the list scrolls down and brings it back on any upward scroll,
the same pattern React Native apps use for collapsing toolbars. The
event listener mirrors the offset into React state so Maestro can
assert the header flipped from "expanded" to "collapsed".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section

HEADER_HEIGHT = 56.0


@pn.component
def CollapsingHeaderDemo() -> pn.Element:
    """Render a collapsing header driven by the scroll offset."""
    scroll_y = pn.use_animated_value(0.0)
    header_state, set_header_state = pn.use_state("expanded")

    # diff_clamp tracks scroll *deltas*, so the header hides after 56 pt
    # of downward travel and re-shows on any upward travel, regardless
    # of absolute position.
    clamped = pn.Animated.diff_clamp(scroll_y, 0.0, HEADER_HEIGHT)
    header_shift = clamped.interpolate([0.0, HEADER_HEIGHT], [0.0, -HEADER_HEIGHT])

    def on_scroll(payload: dict) -> None:
        y = float(payload.get("y", 0.0))
        state = "collapsed" if y > 80.0 else "expanded"
        if state != header_state:
            set_header_state(state)

    rows = [
        pn.Text(
            f"HeaderRow {i}",
            style=pn.style(font_size=15, padding=8, background_color="#F1F5F9"),
        )
        for i in range(1, 61)
    ]

    return demo_screen(
        "Collapsing header",
        "Scroll down to slide the header away via Animated.event.",
        section(
            "Collapsing header demo",
            result_text("Header state", header_state),
            pn.View(
                pn.ScrollView(
                    pn.Column(
                        # Spacer so the first rows start below the header.
                        pn.View(style=pn.style(height=HEADER_HEIGHT)),
                        *rows,
                        style=pn.style(spacing=4),
                    ),
                    on_scroll=pn.Animated.event(on_scroll, y=scroll_y),
                    style=pn.style(height=400),
                ),
                pn.Animated.View(
                    pn.Text(
                        "Collapsing toolbar",
                        style=pn.style(color="#FFFFFF", font_weight="700"),
                    ),
                    style=pn.style(
                        position="absolute",
                        top=0,
                        left=0,
                        right=0,
                        height=HEADER_HEIGHT,
                        z_index=2,
                        transform=[{"translate_y": header_shift}],
                        background_color="#4F46E5",
                        justify_content="center",
                        padding_left=16,
                    ),
                ),
                style=pn.style(height=400, border_width=1, border_color="#CBD5E1"),
            ),
            hint("Maestro scrolls the list and asserts 'Header state: collapsed'."),
        ),
    )
