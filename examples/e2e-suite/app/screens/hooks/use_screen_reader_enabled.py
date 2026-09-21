"""Demo screen for [`pn.use_screen_reader_enabled`][pythonnative.use_screen_reader_enabled].

The hook mirrors whether VoiceOver / TalkBack is running and re-renders
when that changes. CI emulators run without a screen reader, so the flow
asserts "no"; the demo also shows the extra hint text an app would render
for screen-reader users.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def UseScreenReaderEnabledDemo() -> pn.Element:
    """Render the screen-reader flag and a conditional helper line."""
    enabled = pn.use_screen_reader_enabled()

    return demo_screen(
        "use_screen_reader_enabled",
        "Screen reader state, returned reactively by the hook.",
        section(
            "Screen reader",
            result_text("Screen reader", "yes" if enabled else "no"),
            pn.Text(
                "Extra guidance for screen-reader users" if enabled else "Visual layout in use",
                style=pn.style(font_size=14, color="#1F2937"),
            ),
            hint("Maestro asserts 'Screen reader: no' on the stock emulator."),
        ),
    )
