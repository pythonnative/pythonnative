"""Settings tab: Platform info, native alerts, and a push to the showcase.

Demonstrates the imperative ``pn.Alert`` API, runtime queries via
``pn.Platform`` and ``pn.use_window_dimensions``, and how to drive
the root stack from inside a tab via ``pn.use_navigation``.
"""

import pythonnative as pn
from app.theme import styles


@pn.component
def SettingsScreen() -> pn.Element:
    nav = pn.use_navigation()
    dims = pn.use_window_dimensions()

    def _show_alert() -> None:
        # Fire-and-forget; no await needed for a simple notice.
        pn.Alert.show("Hello!", "This is a native alert dialog.")

    def _confirm_destructive() -> None:
        async def _run() -> None:
            ok = await pn.Alert.confirm(
                "Delete item?",
                message="This action cannot be undone.",
                confirm_label="Delete",
                cancel_label="Keep",
            )
            print(f"[SettingsScreen] {'confirmed' if ok else 'cancelled'}")

        pn.run_async(_run())

    def _view_showcase() -> None:
        nav.navigate("Showcase", message="Visual showcase")

    return pn.ScrollView(
        pn.Column(
            pn.StatusBar(bar_style="dark"),
            pn.Text("Settings", style=styles["title"]),
            pn.Text(f"PythonNative v{pn.__version__}", style=styles["subtitle"]),
            pn.Text(
                f"Running on {pn.Platform.OS} {pn.Platform.Version}",
                style=styles["subtitle"],
            ),
            pn.Text(
                f"Window: {dims.width:.0f} × {dims.height:.0f}",
                style=styles["subtitle"],
            ),
            pn.Button("Show alert", on_press=_show_alert),
            pn.Button("Confirm destructive", on_press=_confirm_destructive),
            pn.Button("Visual showcase", on_press=_view_showcase),
            style=styles["section"],
        )
    )
