"""Demo screen for [`pn.Localization`][pythonnative.Localization].

``Localization.get_locales()`` returns the user's preferred
[`Locale`][pythonnative.Locale] records in order, ``get_timezone()`` the
IANA zone name, and ``is_rtl()`` whether the primary locale lays out
right-to-left. The values depend on the device settings, so the flow
asserts the lines are present and the derived flags.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def LocalizationDemo() -> pn.Element:
    """Render the preferred locales, time zone, and RTL flag."""
    locales = pn.Localization.get_locales()
    primary = locales[0] if locales else None
    timezone = pn.Localization.get_timezone()

    return demo_screen(
        "Localization",
        "Localization.get_locales, get_timezone, and is_rtl.",
        section(
            "Localization module",
            result_text("Locale count", len(locales)),
            result_text("Has locale", "yes" if primary is not None else "no"),
            result_text("Primary tag", primary.language_tag if primary else "(none)"),
            result_text("Language", primary.language_code if primary else "(none)"),
            result_text("Region", (primary.region_code or "(none)") if primary else "(none)"),
            result_text("Primary RTL", "yes" if primary and primary.is_rtl else "no"),
            result_text("Layout RTL", "yes" if pn.Localization.is_rtl() else "no"),
            result_text("Timezone", timezone or "(unknown)"),
            result_text("Has timezone", "yes" if timezone else "no"),
            hint("Maestro asserts the 'Has locale' and 'Has timezone' flags."),
        ),
    )
