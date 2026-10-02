"""Forms screen: TextInput, Picker, RefreshControl, and KeyboardAvoidingView.

Two levels deep on the native stack; demonstrates that
``KeyboardAvoidingView`` lifts content above the keyboard on both
platforms, that ``RefreshControl`` integrates with the underlying
``UIRefreshControl`` / ``SwipeRefreshLayout``, and that a screen can
set its own title from state with ``pn.use_screen_options``.
"""

import asyncio
from typing import Any

import pythonnative as pn
from app.theme import AppStyles

FRUIT_OPTIONS: list[dict[str, Any]] = [
    {"value": "apple", "label": "Apple"},
    {"value": "banana", "label": "Banana"},
    {"value": "cherry", "label": "Cherry"},
    {"value": "durian", "label": "Durian"},
]


@pn.component
def FormsScreen() -> pn.Node:
    nav = pn.use_navigation()
    styles = pn.use_styles(AppStyles)
    theme = pn.use_theme()
    name, set_name = pn.use_state("")
    notes, set_notes = pn.use_state("")
    fruit, set_fruit = pn.use_state("apple")
    refreshing, set_refreshing = pn.use_state(False)

    # The navigation bar title follows the name field as you type.
    pn.use_screen_options(title=f"Hi, {name.strip()}" if name.strip() else "Forms")

    async def refresh() -> None:
        set_refreshing(True)
        await asyncio.sleep(0.8)
        set_refreshing(False)

    return pn.KeyboardAvoidingView(
        pn.ScrollView(
            pn.Column(
                pn.Text("Forms", style=styles.title),
                pn.Text("You navigated two levels deep.", style=styles.hint),
                pn.Text(
                    "Single-line input, multiline TextInput, Picker, and pull-to-refresh.",
                    style=styles.hint,
                ),
                pn.Text("Name", style=styles.section_title),
                pn.TextInput(
                    value=name,
                    placeholder="Your name",
                    placeholder_color=theme.colors.text_secondary,
                    on_change=set_name,
                    auto_capitalize="words",
                    return_key_type="next",
                    style=styles.field,
                ),
                pn.Text("Notes (multiline)", style=styles.section_title),
                pn.TextInput(
                    value=notes,
                    placeholder="A few sentences…",
                    placeholder_color=theme.colors.text_secondary,
                    on_change=set_notes,
                    multiline=True,
                    max_length=500,
                    style=[styles.field, {"height": 120}],
                ),
                pn.Text("Favorite fruit", style=styles.section_title),
                pn.Picker(
                    value=fruit,
                    items=FRUIT_OPTIONS,
                    on_change=set_fruit,
                    placeholder="Pick a fruit…",
                    style=styles.field,
                ),
                pn.Text(f"You picked: {fruit}", style=styles.hint),
                pn.Button("Refresh", on_press=refresh),
                pn.Text("Refreshing…" if refreshing else "Idle.", style=styles.hint),
                pn.Button("Back to Showcase", on_press=nav.go_back),
                style=styles.section,
            ),
            refresh_control=pn.RefreshControl(refreshing=refreshing, on_refresh=refresh),
        ),
    )
