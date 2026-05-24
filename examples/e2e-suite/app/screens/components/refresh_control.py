"""Demo screen for [`pn.RefreshControl`][pythonnative.RefreshControl].

Pull-to-refresh is awkward to drive from Maestro on every platform,
so this demo also exposes a "Trigger refresh" button that runs the
same code path. Maestro taps the button and asserts the refresh state
flips, then settles back to idle.
"""

from __future__ import annotations

import threading

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def RefreshControlDemo() -> pn.Element:
    """Render a ScrollView with a RefreshControl plus a manual trigger button."""
    refreshing, set_refreshing = pn.use_state(False)
    count, set_count = pn.use_state(0)

    def start_refresh() -> None:
        set_refreshing(True)

        def _done() -> None:
            set_refreshing(False)
            set_count(count + 1)

        threading.Timer(0.6, _done).start()

    return demo_screen(
        "RefreshControl",
        "Pull down to refresh, or use the button to trigger the same code path.",
        section(
            "Refresh state",
            result_text("Refreshing", "yes" if refreshing else "no"),
            result_text("Refresh runs", count),
            pn.Button("Trigger refresh", on_click=start_refresh),
            hint("Maestro taps 'Trigger refresh' and asserts the runs counter."),
        ),
        pn.ScrollView(
            pn.Column(
                pn.Text("Scrollable content", style=pn.style(font_size=15)),
                pn.Text("Pull down here to refresh", style=pn.style(font_size=13, color="#6B7280")),
                style=pn.style(spacing=8, padding=12),
            ),
            refresh_control=pn.RefreshControl(refreshing=refreshing, on_refresh=start_refresh),
            style=pn.style(height=160, background_color="#F8FAFC", border_radius=8),
        ),
    )
