"""Demo screen for ``tab_bar_style``, ``tab_bar_visible``, and ``freeze_on_blur``.

A module-level tab navigator styles its bar with a
[`TabBarStyle`][pythonnative.TabBarStyle], hides the bar while the
``Hidden`` tab is focused (``tab_bar_visible=False``), and freezes the
``TabA`` subtree while it is blurred (``freeze_on_blur=True``). To make
freezing observable, every tab takes a typed ``tick`` param and reports
the tick it last rendered with. "Advance tick" calls ``set_params(tick=...)``
on every mounted tab: the plain ``TabB`` re-renders with the new params
immediately, while the blurred ``TabA`` keeps its last render and catches
up when it regains focus. The jump buttons live in the persistent demo
body (see ``drawer_navigator.py``) and call ``jump_to`` on the focused
tab's [`TabNavigation`][pythonnative.navigation.TabNavigation].
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText
from pythonnative.navigation import TabNavigation


class _Bus:
    """One mutable object shared with the tabs for the demo's lifetime.

    A fresh context value on every render would re-render every tab and
    defeat the freeze, so the demo provides the same object throughout.

    Attributes:
        focused: The focused tab's handle, for the jump buttons.
        tabs: Every mounted tab's handle by label, for ``set_params``.
        report: Records the tick a tab last rendered with.
    """

    def __init__(self, report: Callable[[str, int], None]) -> None:
        self.focused: Optional[TabNavigation] = None
        self.tabs: Dict[str, pn.Navigation] = {}
        self.report = report


_BusContext: pn.Context[Optional[_Bus]] = pn.create_context(None)

_TAB_BAR_STYLE: pn.TabBarStyle = {
    "background_color": "#0F172A",
    "active_tint_color": "#38BDF8",
    "inactive_tint_color": "#94A3B8",
    "translucent": False,
    "show_labels": True,
}


def _make_tab(label: str) -> pn.Component[[int]]:
    """Build a tab screen that reports the ``tick`` param it last rendered with."""

    @pn.component
    def TabScreen(tick: int = 0) -> pn.Node:
        nav = pn.use_navigation()
        bus = pn.use_context(_BusContext)

        def register() -> Optional[Callable[[], None]]:
            if bus is None:
                return None
            tabs = bus.tabs
            tabs[label] = nav

            def unregister() -> None:
                tabs.pop(label, None)

            return unregister

        pn.use_effect(register, [bus, nav])

        def on_focus() -> None:
            if bus is not None and isinstance(nav, TabNavigation):
                bus.focused = nav

        pn.use_focus_effect(on_focus, [bus, nav])

        def report() -> None:
            if bus is not None:
                bus.report(label, tick)

        pn.use_effect(report, [bus, tick])
        return pn.Column(
            pn.Text(f"{label} body", style=pn.style(font_size=16, font_weight="700")),
            pn.Text(f"{label} rendered tick {tick}", style=pn.style(color="#475569")),
            style=pn.style(padding=16, gap=6),
        )

    return TabScreen


TabA = _make_tab("TabA")
TabB = _make_tab("TabB")
Hidden = _make_tab("Hidden")

DemoTabs = pn.TabNavigator(
    pn.Screen(TabA, name="TabA", title="TabA", freeze_on_blur=True),
    pn.Screen(TabB, name="TabB", title="TabB", lazy=False),
    pn.Screen(Hidden, name="Hidden", title="TabH", tab_bar_visible=False),
    tab_bar_style=_TAB_BAR_STYLE,
)
"""A styled tab bar with a frozen tab and a tab that hides the bar."""


@pn.component
def TabOptionsDemo() -> pn.Node:
    """Render a styled tab bar with a hidden-bar tab and a frozen tab."""
    tick, set_tick = pn.use_state(0)
    seen, set_seen = pn.use_state({"TabA": -1, "TabB": -1, "Hidden": -1})

    def make_bus() -> _Bus:
        def report(label: str, rendered_tick: int) -> None:
            set_seen(lambda current: {**current, label: rendered_tick})

        return _Bus(report)

    bus = pn.use_memo(make_bus, [])

    def jump(target: pn.Component[[int]]) -> Callable[[], None]:
        def _run() -> None:
            if bus.focused is not None:
                bus.focused.jump_to(target)

        return _run

    def advance() -> None:
        set_tick(tick + 1)
        for handle in list(bus.tabs.values()):
            handle.set_params(tick=tick + 1)

    last: Dict[str, int] = seen
    return DemoScreen(
        "Tab options",
        "tab_bar_style, tab_bar_visible=False, and freeze_on_blur on a nested tab navigator.",
        DemoSection(
            "Nested tabs",
            ResultText("Tick", tick),
            ResultText("TabA last tick", last["TabA"]),
            ResultText("TabB last tick", last["TabB"]),
            pn.View(
                _BusContext.Provider(DemoTabs(), value=bus),
                style=pn.style(height=260, border_radius=8, background_color="#F8FAFC", overflow="hidden"),
            ),
            # Two rows: three buttons in one row overflow the card on a
            # 390 pt phone and Maestro can't tap a clipped button.
            ButtonsRow(
                pn.Button("Jump to TabA", on_press=jump(TabA)),
                pn.Button("Jump to TabB", on_press=jump(TabB)),
            ),
            ButtonsRow(
                pn.Button("Jump to Hidden", on_press=jump(Hidden)),
                pn.Button("Advance tick", on_press=advance),
            ),
            Hint("A blurred TabA keeps its last tick until it is focused again; TabB follows every tick."),
        ),
    )
