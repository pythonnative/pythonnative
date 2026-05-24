"""Demo screen for flex layout primitives.

Three sibling boxes in a row: a fixed-width box, a ``flex: 1`` box,
and another fixed-width box. The middle box should stretch to fill
the available space. Maestro asserts the three labels appear in the
expected order.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def FlexLayoutDemo() -> pn.Element:
    """Render three flex children in a row, with the middle one stretching."""
    return demo_screen(
        "Flex layout",
        "Three siblings: fixed, flex:1, fixed.",
        section(
            "Row with flex",
            pn.Row(
                pn.View(
                    pn.Text("flex-fixed-left", style=pn.style(color="#FFFFFF")),
                    style=pn.style(width=80, background_color="#0EA5E9", padding=8),
                ),
                pn.View(
                    pn.Text("flex-grow", style=pn.style(color="#FFFFFF")),
                    style=pn.style(flex=1, background_color="#22C55E", padding=8),
                ),
                pn.View(
                    pn.Text("flex-fixed-right", style=pn.style(color="#FFFFFF")),
                    style=pn.style(width=80, background_color="#0EA5E9", padding=8),
                ),
                style=pn.style(spacing=4, height=64),
            ),
            hint("Maestro asserts the three labels are visible together."),
        ),
    )
