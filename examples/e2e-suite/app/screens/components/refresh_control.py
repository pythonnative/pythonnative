"""Demo screen for [`pn.RefreshControl`][pythonnative.RefreshControl].

The RefreshControl is attached to the *page* scroll view, like a real
feed screen: a pull-down at the top of the page exercises the native
refresh wiring (UIRefreshControl on iOS, SwipeRefreshLayout on
Android) with the full screen of finger travel the gesture needs to
cross the activation threshold. The "Trigger refresh" button runs the
same code path programmatically.
"""

from __future__ import annotations

import threading

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def RefreshControlDemo() -> pn.Node:
    """Render a page with a pull-to-refresh control plus a manual trigger button."""
    refreshing, set_refreshing = pn.use_state(False)
    count, set_count = pn.use_state(0)

    def start_refresh() -> None:
        set_refreshing(True)

        def _done() -> None:
            set_refreshing(False)
            set_count(count + 1)

        threading.Timer(0.6, _done).start()

    return DemoScreen(
        "RefreshControl",
        "Pull the page down to refresh, or use the button for the same code path.",
        DemoSection(
            "Refresh state",
            ResultText("Refreshing", "yes" if refreshing else "no"),
            ResultText("Refresh runs", count),
            pn.Button("Trigger refresh", on_press=start_refresh),
            Hint("Maestro pulls the page down, then taps 'Trigger refresh'."),
        ),
        refresh_control=pn.RefreshControl(refreshing=refreshing, on_refresh=start_refresh),
    )
