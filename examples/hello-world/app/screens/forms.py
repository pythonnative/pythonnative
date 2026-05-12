"""Forms screen: TextInput, Picker, RefreshControl, and KeyboardAvoidingView.

Two levels deep on the native stack; demonstrates that
``KeyboardAvoidingView`` properly lifts content above the keyboard
on both platforms and that ``RefreshControl`` integrates with the
underlying ``UIRefreshControl`` / ``SwipeRefreshLayout``.
"""

import threading

import pythonnative as pn
from app.theme import styles

local_styles = pn.StyleSheet.create(
    field={
        "padding": 12,
        "border_radius": 8,
        "border_width": 1,
        "border_color": "#D1D5DB",
        "background_color": "#FFFFFF",
        "font_size": 16,
    },
)

FRUIT_OPTIONS = [
    {"value": "apple", "label": "Apple"},
    {"value": "banana", "label": "Banana"},
    {"value": "cherry", "label": "Cherry"},
    {"value": "durian", "label": "Durian"},
]


@pn.component
def FormsScreen() -> pn.Element:
    nav = pn.use_navigation()
    name, set_name = pn.use_state("")
    notes, set_notes = pn.use_state("")
    fruit, set_fruit = pn.use_state("apple")
    refreshing, set_refreshing = pn.use_state(False)

    def go_back() -> None:
        nav.go_back()

    def fake_refresh() -> None:
        set_refreshing(True)

        def _done() -> None:
            set_refreshing(False)

        threading.Timer(0.8, _done).start()

    return pn.KeyboardAvoidingView(
        pn.ScrollView(
            pn.Column(
                pn.Text("Forms", style=styles["title"]),
                pn.Text("You navigated two levels deep.", style=styles["hint"]),
                pn.Text(
                    "Single-line input, multiline TextInput, Picker, and pull-to-refresh.",
                    style=styles["hint"],
                ),
                pn.Text("Name", style=styles["section_title"]),
                pn.TextInput(
                    value=name,
                    placeholder="Your name",
                    on_change=set_name,
                    auto_capitalize="words",
                    return_key_type="next",
                    style=local_styles["field"],
                ),
                pn.Text("Notes (multiline)", style=styles["section_title"]),
                pn.TextInput(
                    value=notes,
                    placeholder="A few sentences…",
                    on_change=set_notes,
                    multiline=True,
                    max_length=500,
                    style={**local_styles["field"], "height": 120},
                ),
                pn.Text("Favorite fruit", style=styles["section_title"]),
                pn.Picker(
                    value=fruit,
                    items=FRUIT_OPTIONS,
                    on_change=set_fruit,
                    placeholder="Pick a fruit…",
                    style=local_styles["field"],
                ),
                pn.Text(f"You picked: {fruit}", style=styles["hint"]),
                pn.Button("Refresh", on_click=fake_refresh),
                pn.Text(
                    "Refreshing…" if refreshing else "Idle.",
                    style=styles["hint"],
                ),
                pn.Button("Back to Showcase", on_click=go_back),
                style=styles["section"],
            ),
            refresh_control=pn.RefreshControl(refreshing=refreshing, on_refresh=fake_refresh),
        ),
    )
