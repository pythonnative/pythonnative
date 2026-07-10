"""Demo screen for [`pn.Portal`][pythonnative.Portal].

A ``Portal`` renders its children into a full-screen overlay above
everything else while keeping them part of the component tree for
state, context, and events. The demo toggles a floating banner and
proves both directions of the wiring: state from the screen flows
into the portal (the banner shows the counter), and events from the
portal flow back (the banner's own button bumps the counter).
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def PortalDemo() -> pn.Element:
    """Render a toggleable floating banner hosted in a Portal."""
    shown, set_shown = pn.use_state(False)
    count, set_count = pn.use_state(0)

    banner = pn.Portal(
        pn.Column(
            pn.Text(
                f"Floating banner (count {count})",
                style=pn.style(color="#FFFFFF", font_size=15, bold=True),
            ),
            pn.Button("Bump from portal", on_press=lambda: set_count(count + 1)),
            style=pn.style(
                position="absolute",
                left=24,
                right=24,
                bottom=40,
                background_color="#1F6FEB",
                border_radius=12,
                padding=16,
                spacing=8,
            ),
        ),
    )

    return demo_screen(
        "Portal",
        "Render children into an overlay above the screen content.",
        section(
            "Overlay",
            result_text("Banner shown", "yes" if shown else "no"),
            result_text("Portal count", count),
            buttons_row(
                pn.Button("Show banner", on_press=lambda: set_shown(True)),
                pn.Button("Hide banner", on_press=lambda: set_shown(False)),
            ),
            hint(
                "The banner floats over the whole screen (including this "
                "card) while its button stays wired to this component's "
                "state."
            ),
        ),
        banner if shown else None,
    )
