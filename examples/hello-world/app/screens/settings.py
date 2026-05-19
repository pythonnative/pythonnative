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
        pn.Alert.show(
            title="Hello!",
            message="This is a native alert dialog.",
            buttons=[
                {"label": "OK", "style": "default"},
            ],
        )

    def _confirm_destructive() -> None:
        pn.Alert.confirm(
            title="Delete item?",
            message="This action cannot be undone.",
            confirm_label="Delete",
            cancel_label="Keep",
            on_confirm=lambda: print("[SettingsScreen] confirmed"),
            on_cancel=lambda: print("[SettingsScreen] cancelled"),
        )

    def _view_showcase() -> None:
        nav.navigate("Showcase", {"message": "Visual showcase"})

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
                f"Window: {dims['width']:.0f} × {dims['height']:.0f}",
                style=styles["subtitle"],
            ),
            pn.Button("Show alert", on_click=_show_alert),
            pn.Button("Confirm destructive", on_click=_confirm_destructive),
            pn.Button("Visual showcase", on_click=_view_showcase),
            style=styles["section"],
        )
    )
