"""Demo screen for [`pn.Localization`][pythonnative.Localization].

``Localization.get_locales()`` returns the user's preferred
[`Locale`][pythonnative.Locale] records in order, ``get_timezone()`` the
IANA zone name, and ``is_rtl()`` whether the primary locale lays out
right-to-left. The values depend on the device settings, so the flow
asserts the lines are present and the derived flags.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def LocalizationDemo() -> pn.Node:
    """Render the preferred locales, time zone, and RTL flag."""
    locales = pn.Localization.get_locales()
    primary = locales[0] if locales else None
    timezone = pn.Localization.get_timezone()

    return DemoScreen(
        "Localization",
        "Localization.get_locales, get_timezone, and is_rtl.",
        DemoSection(
            "Localization module",
            ResultText("Locale count", len(locales)),
            ResultText("Has locale", "yes" if primary is not None else "no"),
            ResultText("Primary tag", primary.language_tag if primary else "(none)"),
            ResultText("Language", primary.language_code if primary else "(none)"),
            ResultText("Region", (primary.region_code or "(none)") if primary else "(none)"),
            ResultText("Primary RTL", "yes" if primary and primary.is_rtl else "no"),
            ResultText("Layout RTL", "yes" if pn.Localization.is_rtl() else "no"),
            ResultText("Timezone", timezone or "(unknown)"),
            ResultText("Has timezone", "yes" if timezone else "no"),
            Hint("Maestro asserts the 'Has locale' and 'Has timezone' flags."),
        ),
    )
