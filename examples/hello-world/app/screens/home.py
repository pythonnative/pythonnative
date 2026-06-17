"""Home tab: state hooks, a reusable child component, and a push to the showcase.

Designed as the obvious "first thing a new user reads"; it shows
``use_state``, ``use_effect``, and an in-Python child component, plus
the canonical ``nav.navigate(...)`` call that pushes a real native
screen onto the stack.
"""

from typing import Callable

import emoji

import pythonnative as pn
from app.theme import styles

MEDALS = [":1st_place_medal:", ":2nd_place_medal:", ":3rd_place_medal:"]

# ``pn.style(...)`` returns a fully-typed ``pn.Style`` TypedDict so each
# entry below benefits from IDE autocomplete and mypy/pyright checking
# against the supported style keys and ``Literal`` value sets (e.g.
# ``align_items``).
local_styles = pn.StyleSheet.create(
    medal=pn.style(font_size=32),
    card=pn.style(
        spacing=12,
        padding=16,
        background_color="#F8F9FA",
        align_items="center",
    ),
    button_row=pn.style(spacing=8, align_items="center"),
)


@pn.component
def counter_badge(initial: int = 0) -> pn.Element:
    """Reusable counter component with its own hook-based state.

    State is preserved across Fast Refresh: edit the medal list or
    tweak this component, save, and the on-screen tap count stays
    where you left it.
    """
    count, set_count = pn.use_state(initial)
    medal = emoji.emojize(MEDALS[count] if count < len(MEDALS) else ":star:")

    print(f"[counter_badge] render count={count}")

    def handle_tap() -> None:
        print(f"[counter_badge] Tap me clicked; {count} -> {count + 1}")
        set_count(count + 1)

    def handle_reset() -> None:
        print(f"[counter_badge] Reset clicked from count={count}")
        set_count(0)

    return pn.View(
        pn.Text(f"Tapped {count} times", style=styles["subtitle"]),
        pn.Text(medal, style=local_styles["medal"]),
        pn.Row(
            pn.Button("Tap me", on_click=handle_tap),
            pn.Button("Reset", on_click=handle_reset),
            style=local_styles["button_row"],
        ),
        style=local_styles["card"],
    )


@pn.component
def HomeScreen() -> pn.Element:
    """Counter demo + push-navigation entry point.

    ``nav.navigate("Showcase", ...)`` goes through the inner Tab handle,
    forwards to the outer Stack handle (root navigator), and pushes a
    real native screen via the host's ``_push`` API.
    """
    nav = pn.use_navigation()

    def _on_mount() -> Callable[[], None]:
        print("[HomeScreen] mounted")
        return lambda: print("[HomeScreen] unmounted")

    pn.use_effect(_on_mount, [])

    def view_showcase() -> None:
        print("[HomeScreen] navigating to Showcase")
        nav.navigate("Showcase", {"message": "Greetings from Home"})

    return pn.ScrollView(
        pn.Column(
            pn.Text("Hello from PythonNative Demo!", style=styles["title"]),
            pn.Text(
                "Try `pn run android --hot-reload`, edit this text, and save. "
                "The running app should update without a rebuild, and the counter "
                "below should preserve its value across the refresh.",
                style=styles["hint"],
            ),
            counter_badge(),
            pn.Button("View Showcase", on_click=view_showcase),
            style=styles["section"],
        )
    )
