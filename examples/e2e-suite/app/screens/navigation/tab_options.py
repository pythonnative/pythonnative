"""Demo screen for ``tab_bar_style``, ``tab_bar_visible``, and ``freeze_on_blur``.

A nested Tab navigator styles its bar with a
[`TabBarStyle`][pythonnative.TabBarStyle], hides the bar while the
``Hidden`` tab is focused (``tab_bar_visible=False``), and freezes the
``TabA`` subtree while it is blurred (``freeze_on_blur=True``). To make
freezing observable, every tab renders the demo's ``tick`` counter and
reports the tick it last rendered with: while ``TabA`` is blurred and the
tick advances, its reported tick stays behind; the plain ``TabB`` follows
immediately; ``TabA`` catches up when it regains focus. The jump buttons
live in the persistent demo body (see ``drawer_navigator.py``).
"""

from __future__ import annotations

from typing import Any, Callable, Dict

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_Tab = pn.create_tab_navigator()
_Bus: pn.Context[Dict[str, Any]] = pn.create_context({})

_TAB_BAR_STYLE: pn.TabBarStyle = {
    "background_color": "#0F172A",
    "active_tint_color": "#38BDF8",
    "inactive_tint_color": "#94A3B8",
    "translucent": False,
    "show_labels": True,
}


def _make_tab(label: str) -> Callable[[], pn.Element]:
    @pn.component
    def TabScreen() -> pn.Element:
        nav = pn.use_navigation()
        bus = pn.use_context(_Bus)
        tick = bus["tick"]

        def on_focus() -> None:
            bus["ref"].current = nav

        pn.use_focus_effect(on_focus, [])

        def report():
            bus["report"](label, tick)
            return None

        pn.use_effect(report, [tick])
        return pn.Column(
            pn.Text(f"{label} body", style=pn.style(font_size=16, font_weight="700")),
            pn.Text(f"{label} rendered tick {tick}", style=pn.style(color="#475569")),
            style=pn.style(padding=16, spacing=6),
        )

    return TabScreen


_TabA = _make_tab("TabA")
_TabB = _make_tab("TabB")
_Hidden = _make_tab("Hidden")


@pn.component
def TabOptionsDemo() -> pn.Element:
    """Render a styled tab bar with a hidden-bar tab and a frozen tab."""
    handle_ref = pn.use_ref(None)
    tick, set_tick = pn.use_state(0)
    seen, set_seen = pn.use_state({"TabA": -1, "TabB": -1, "Hidden": -1})

    def report(label: str, rendered_tick: int) -> None:
        set_seen(lambda current: {**current, label: rendered_tick})

    # One stable dict for the whole demo: a fresh context value on every
    # render would force every consumer to re-render and defeat the freeze,
    # so the tick is written into the same object instead.
    bus = pn.use_memo(lambda: {"ref": handle_ref, "tick": tick, "report": report}, [])
    bus["tick"] = tick

    def jump(name: str) -> Callable[[], None]:
        def _run() -> None:
            handle = handle_ref.current
            if handle is not None:
                handle.jump_to(name)

        return _run

    return demo_screen(
        "Tab options",
        "tab_bar_style, tab_bar_visible=False, and freeze_on_blur on a nested tab navigator.",
        section(
            "Nested tabs",
            result_text("Tick", tick),
            result_text("TabA last tick", seen["TabA"]),
            result_text("TabB last tick", seen["TabB"]),
            pn.View(
                _Bus.Provider(
                    _Tab.Navigator(
                        _Tab.Screen("TabA", _TabA, title="TabA", freeze_on_blur=True),
                        _Tab.Screen("TabB", _TabB, title="TabB", lazy=False),
                        _Tab.Screen("Hidden", _Hidden, title="TabH", tab_bar_visible=False),
                        tab_bar_style=_TAB_BAR_STYLE,
                    ),
                    value=bus,
                ),
                style=pn.style(height=260, border_radius=8, background_color="#F8FAFC", overflow="hidden"),
            ),
            # Two rows: three buttons in one row overflow the card on a
            # 390 pt phone and Maestro can't tap a clipped button.
            buttons_row(
                pn.Button("Jump to TabA", on_press=jump("TabA")),
                pn.Button("Jump to TabB", on_press=jump("TabB")),
            ),
            buttons_row(
                pn.Button("Jump to Hidden", on_press=jump("Hidden")),
                pn.Button("Advance tick", on_press=lambda: set_tick(tick + 1)),
            ),
            hint("A blurred TabA keeps its last tick until it is focused again; TabB follows every tick."),
        ),
    )
