"""Home tab: state hooks, a reusable child component, and a push to the showcase.

Designed as the obvious "first thing a new user reads"; it shows
``use_state``, ``use_effect``, theme-aware styles, an in-Python child
component, and the canonical ``nav.push(Screen(...))`` call that pushes
a real native screen onto the stack.
"""

from collections.abc import Callable

import emoji

import pythonnative as pn
from app.screens.showcase import ShowcaseScreen
from app.theme import AppStyles, DemoTheme

MEDALS = [":1st_place_medal:", ":2nd_place_medal:", ":3rd_place_medal:"]


class Styles(pn.StyleSheet):
    """Styles that don't depend on the theme.

    ``pn.style(...)`` returns a typed ``pn.Style``, so a bad key or value
    (``align_items="centre"``) is a type error, and ``Styles.medal`` is
    checked by attribute name.
    """

    medal = pn.style(font_size=32)
    button_row = pn.style(gap=8, align_items="center")
    title_row = pn.style(gap=10, align_items="center")


@pn.component
def CounterBadge(initial: int = 0) -> pn.Node:
    """Reusable counter component with its own hook-based state.

    State is preserved across Fast Refresh: edit the medal list or
    tweak this component, save, and the on-screen tap count stays
    where you left it.
    """
    count, set_count = pn.use_state(initial)
    styles = pn.use_styles(AppStyles)
    medal = emoji.emojize(MEDALS[count] if count < len(MEDALS) else ":star:")

    print(f"[CounterBadge] render count={count}")

    def handle_tap() -> None:
        print(f"[CounterBadge] Tap me clicked; {count} -> {count + 1}")
        set_count(count + 1)

    def handle_reset() -> None:
        print(f"[CounterBadge] Reset clicked from count={count}")
        set_count(0)

    return pn.View(
        pn.Text(f"Tapped {count} times", style=styles.subtitle),
        pn.Text(medal, style=Styles.medal),
        pn.Row(
            pn.Button("Tap me", on_press=handle_tap),
            pn.Button("Reset", on_press=handle_reset),
            style=Styles.button_row,
        ),
        style=[styles.card, {"align_items": "center"}],
    )


@pn.component
def HomeScreen() -> pn.Node:
    """Counter demo and push-navigation entry point.

    ``nav.push(ShowcaseScreen(...))`` builds the destination through the
    screen's own signature, so a misspelled or missing param is a type
    error. The tab navigator doesn't have that screen, so it forwards
    the push to the root stack, which pushes a real native screen.
    """
    nav = pn.use_navigation()
    styles = pn.use_styles(AppStyles)
    theme = pn.use_theme(DemoTheme)

    def on_mount() -> Callable[[], None]:
        print("[HomeScreen] mounted")
        return lambda: print("[HomeScreen] unmounted")

    pn.use_effect(on_mount, [])

    def view_showcase() -> None:
        print("[HomeScreen] pushing Showcase")
        nav.push(ShowcaseScreen(message="Greetings from Home"))

    return pn.ScrollView(
        pn.Column(
            pn.Row(
                # Vector icons ship with the framework and draw identically on
                # every platform; ``color`` defaults to the label color.
                pn.Icon("sparkles", size=28, color=theme.accent),
                pn.Text("Hello from PythonNative Demo!", style=[styles.title, {"flex_shrink": 1}]),
                style=Styles.title_row,
            ),
            pn.Text(
                "Run `pn start`, edit this text, and save. Every connected target "
                "(browser preview, simulators, devices) updates without a rebuild, "
                "and the counter below keeps its value across the refresh.",
                style=styles.hint,
            ),
            CounterBadge(),
            pn.Button("View Showcase", on_press=view_showcase),
            style=styles.section,
        )
    )
