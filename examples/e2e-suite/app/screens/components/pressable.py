"""Demo screen for [`pn.Pressable`][pythonnative.Pressable].

A Pressable wraps a colored View. Tapping toggles the background
color and bumps a counter so Maestro can assert ``on_press`` fired.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def PressableDemo() -> pn.Element:
    """Render a Pressable that toggles its background and tracks tap count."""
    count, set_count = pn.use_state(0)
    color = "#0EA5E9" if count % 2 == 0 else "#10B981"

    def on_press() -> None:
        set_count(count + 1)

    return demo_screen(
        "Pressable",
        "Tap the colored area; the press counter and background flip.",
        section(
            "Tap target",
            result_text("Presses", count),
            pn.Pressable(
                pn.View(
                    pn.Text(
                        "Tap me (Pressable)",
                        style=pn.style(color="#FFFFFF", font_weight="700"),
                    ),
                    style=pn.style(
                        padding=18,
                        background_color=color,
                        border_radius=12,
                        align_items="center",
                    ),
                ),
                on_press=on_press,
                pressed_opacity=0.7,
            ),
            hint("Maestro taps the area and asserts the Presses count increases."),
        ),
    )
