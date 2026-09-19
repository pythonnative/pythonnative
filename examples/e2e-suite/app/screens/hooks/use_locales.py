"""Demo screen for [`pn.use_locales`][pythonnative.use_locales].

The hook returns the user's preferred [`Locale`][pythonnative.Locale]
records and re-renders when the device's language settings change. The
values depend on the device, so the flow asserts the derived flags.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def UseLocalesDemo() -> pn.Element:
    """Render the locales reported by use_locales."""
    locales = pn.use_locales()
    primary = locales[0] if locales else None

    return demo_screen(
        "use_locales",
        "Preferred locales, returned reactively by the hook.",
        section(
            "Locales",
            result_text("Hook locale count", len(locales)),
            result_text("Hook has locale", "yes" if primary is not None else "no"),
            result_text("Hook primary tag", primary.language_tag if primary else "(none)"),
            result_text("Hook tag has language", "yes" if primary and primary.language_code else "no"),
            hint("Maestro asserts the 'Hook has locale' flag; the tag varies per device."),
        ),
    )
