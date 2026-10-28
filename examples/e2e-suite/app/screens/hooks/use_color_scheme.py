"""Demo screen for [`pn.use_color_scheme`][pythonnative.use_color_scheme].

Shows the effective color scheme and drives it through
[`pn.appearance.set_color_scheme`][pythonnative.appearance.set_color_scheme]
overrides. Maestro forces dark, asserts the hook re-rendered, forces
light, then restores the system setting.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseColorSchemeDemo() -> pn.Node:
    """Render the effective scheme with appearance-override buttons."""
    scheme = pn.use_color_scheme()
    return DemoScreen(
        "use_color_scheme",
        "Effective color scheme; an appearance override wins over the system.",
        DemoSection(
            "Scheme",
            ResultText("Scheme", scheme),
            ButtonsRow(
                pn.Button(
                    "Force dark",
                    on_press=lambda: pn.appearance.set_color_scheme("dark"),
                ),
                pn.Button(
                    "Force light",
                    on_press=lambda: pn.appearance.set_color_scheme("light"),
                ),
            ),
            pn.Button(
                "Follow system",
                on_press=lambda: pn.appearance.set_color_scheme(None),
            ),
            Hint("Maestro forces each scheme and asserts the Scheme line."),
        ),
    )
