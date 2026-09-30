"""Demo screen for [`pn.StyleSheet`][pythonnative.StyleSheet] and
[`pn.style`][pythonnative.style].

A small style sheet is declared as a class namespace; the screen reuses
each entry in a different element, reads them by attribute (so a
misspelled style is a static error), and composes one with a style list
over [`ABSOLUTE_FILL`][pythonnative.ABSOLUTE_FILL], so flows can confirm
the entries resolve to working styles.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


class Sheet(pn.StyleSheet):
    """The demo's styles, validated once in dev mode."""

    pill = pn.style(padding=8, background_color="#0EA5E9", border_radius=999)
    pill_label = pn.style(color="#FFFFFF", font_weight="600")
    danger = pn.style(padding=8, background_color="#DC2626", border_radius=8)
    danger_label = pn.style(color="#FFFFFF", font_weight="700")
    frame = pn.style(height=48, border_radius=8, background_color="#E2E8F0")
    overlay = pn.style(background_color="#0F172A", opacity=0.2, border_radius=8)


@pn.component
def StyleSheetDemo() -> pn.Node:
    """Render elements styled via shared StyleSheet entries."""
    return DemoScreen(
        "StyleSheet",
        "Reusable styles via a pn.StyleSheet class and pn.style.",
        DemoSection(
            "Pills",
            pn.View(pn.Text("stylesheet-pill", style=Sheet.pill_label), style=Sheet.pill),
            pn.View(pn.Text("stylesheet-danger", style=Sheet.danger_label), style=Sheet.danger),
            pn.View(pn.View(style=[pn.ABSOLUTE_FILL, Sheet.overlay]), style=Sheet.frame),
            Hint("Maestro asserts both labels are visible."),
        ),
    )
