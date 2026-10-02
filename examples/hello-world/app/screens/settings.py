"""Settings tab: a persisted appearance setting, platform info, native alerts, and a push.

Demonstrates reading app-wide state from context, the imperative
``pn.Alert`` API (including an ``async`` handler that awaits a
confirmation), runtime queries via ``pn.Platform`` and
``pn.use_window_dimensions``, and pushing a root-stack screen from
inside a tab.
"""

import pythonnative as pn
from app.preferences import APPEARANCES, AppearanceContext
from app.screens.showcase import ShowcaseScreen
from app.theme import AppStyles


@pn.component
def SettingsScreen() -> pn.Node:
    nav = pn.use_navigation()
    dims = pn.use_window_dimensions()
    styles = pn.use_styles(AppStyles)
    theme = pn.use_theme()
    appearance = pn.use_context(AppearanceContext)

    def show_alert() -> None:
        # Fire-and-forget; no await needed for a simple notice.
        pn.Alert.show("Hello!", "This is a native alert dialog.")

    async def confirm_destructive() -> None:
        confirmed = await pn.Alert.confirm(
            "Delete item?",
            message="This action cannot be undone.",
            confirm_label="Delete",
            cancel_label="Keep",
        )
        print(f"[SettingsScreen] {'confirmed' if confirmed else 'cancelled'}")

    return pn.ScrollView(
        pn.Column(
            pn.StatusBar(bar_style="light" if theme.dark else "dark"),
            pn.Text("Settings", style=styles.title),
            pn.Text("Appearance", style=styles.section_title),
            pn.SegmentedControl(
                segments=[choice.capitalize() for choice in APPEARANCES],
                selected_index=APPEARANCES.index(appearance.value),
                on_change=lambda index: appearance.set(APPEARANCES[index]),
                accessibility_label="Appearance",
            ),
            pn.Text("Saved on this device and applied at launch.", style=styles.hint),
            pn.Text("About", style=styles.section_title),
            pn.Text(f"PythonNative v{pn.__version__}", style=styles.subtitle),
            pn.Text(f"Running on {pn.Platform.OS} {pn.Platform.Version}", style=styles.subtitle),
            pn.Text(f"Window: {dims.width:.0f} × {dims.height:.0f}", style=styles.subtitle),
            pn.Button("Show alert", on_press=show_alert),
            pn.Button("Confirm destructive", on_press=confirm_destructive),
            pn.Button("Visual showcase", on_press=lambda: nav.push(ShowcaseScreen())),
            style=styles.section,
        )
    )
