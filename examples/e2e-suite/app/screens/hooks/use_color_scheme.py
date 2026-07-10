"""Demo screen for [`pn.use_color_scheme`][pythonnative.use_color_scheme].

Shows the effective color scheme and drives it through
[`pn.appearance.set_color_scheme`][pythonnative.appearance.set_color_scheme]
overrides. Maestro forces dark, asserts the hook re-rendered, forces
light, then restores the system setting.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UseColorSchemeDemo() -> pn.Element:
    """Render the effective scheme with appearance-override buttons."""
    scheme = pn.use_color_scheme()
    return demo_screen(
        "use_color_scheme",
        "Effective color scheme; an appearance override wins over the system.",
        section(
            "Scheme",
            result_text("Scheme", scheme),
            buttons_row(
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
            hint("Maestro forces each scheme and asserts the Scheme line."),
        ),
    )
