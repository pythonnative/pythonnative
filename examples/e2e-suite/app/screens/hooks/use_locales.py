"""Demo screen for [`pn.use_locales`][pythonnative.use_locales].

The hook returns the user's preferred [`Locale`][pythonnative.Locale]
records and re-renders when the device's language settings change. The
values depend on the device, so the flow asserts the derived flags.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def UseLocalesDemo() -> pn.Node:
    """Render the locales reported by use_locales."""
    locales = pn.use_locales()
    primary = locales[0] if locales else None

    return DemoScreen(
        "use_locales",
        "Preferred locales, returned reactively by the hook.",
        DemoSection(
            "Locales",
            ResultText("Hook locale count", len(locales)),
            ResultText("Hook has locale", "yes" if primary is not None else "no"),
            ResultText("Hook primary tag", primary.language_tag if primary else "(none)"),
            ResultText("Hook tag has language", "yes" if primary and primary.language_code else "no"),
            Hint("Maestro asserts the 'Hook has locale' flag; the tag varies per device."),
        ),
    )
