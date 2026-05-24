"""Demo screen for [`pn.StyleSheet`][pythonnative.StyleSheet] and
[`pn.style`][pythonnative.style].

A small style sheet is created locally; the screen reuses each entry
in a different element so flows can confirm the StyleSheet entries
resolve to working styles.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

_sheet = pn.StyleSheet.create(
    pill=pn.style(
        padding=8,
        background_color="#0EA5E9",
        border_radius=999,
    ),
    pill_label=pn.style(color="#FFFFFF", font_weight="600"),
    danger=pn.style(
        padding=8,
        background_color="#DC2626",
        border_radius=8,
    ),
    danger_label=pn.style(color="#FFFFFF", font_weight="700"),
)


@pn.component
def StyleSheetDemo() -> pn.Element:
    """Render two elements styled via shared StyleSheet entries."""
    return demo_screen(
        "StyleSheet",
        "Reusable styles via StyleSheet.create + pn.style.",
        section(
            "Pills",
            pn.View(
                pn.Text("stylesheet-pill", style=_sheet["pill_label"]),
                style=_sheet["pill"],
            ),
            pn.View(
                pn.Text("stylesheet-danger", style=_sheet["danger_label"]),
                style=_sheet["danger"],
            ),
            hint("Maestro asserts both labels are visible."),
        ),
    )
