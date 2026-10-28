"""Demo screen for ``screen_options``, ``Group``, ``use_screen_options``, ``pop_to``, and ``before_remove``.

A module-level stack navigator layers its options the way React
Navigation does: the navigator's ``screen_options`` apply to every
screen, a [`Group`][pythonnative.Group] overrides them for its members,
and each [`Screen`][pythonnative.Screen] overrides both. The Plain
screen sets its title from its own render with
[`use_screen_options`][pythonnative.use_screen_options], which layers
over all the static options. The Python-drawn header shows the winning
title.

The controls live in the persistent demo body (see
``drawer_navigator.py`` for why) and drive the focused screen's handle
through a context bus: push each screen, ``pop_to(StackHome)`` from deep
in the stack, and toggle a ``before_remove`` guard on the Preview screen
that vetoes removal while enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText
from pythonnative.navigation import NavigationEvent


@dataclass(frozen=True)
class _Bus:
    """Shared with the nested screens through :data:`_BusContext`.

    Attributes:
        handle: Receives the focused screen's navigation handle.
        guard: The current veto switch, read by the Preview screen's listener.
        report: Mirrors the focused route's name and the stack depth into the demo body.
        veto: Counts vetoes and records the vetoed action.
    """

    handle: pn.Ref[Optional[pn.Navigation]]
    guard: pn.Ref[bool]
    report: Callable[[str, int], None]
    veto: Callable[[str], None]


_BusContext: pn.Context[Optional[_Bus]] = pn.create_context(None)


def use_report_focus() -> pn.Navigation:
    """Publish the calling screen's handle and position on the bus whenever it gains focus."""
    nav = pn.use_navigation()
    bus = pn.use_context(_BusContext)

    def on_focus() -> None:
        if bus is not None:
            bus.handle.current = nav
            bus.report(nav.route.name, len(nav.get_state().routes))

    pn.use_focus_effect(on_focus, [bus, nav])
    return nav


def _body(label: str, *extra: pn.Node) -> pn.Element:
    return pn.Column(
        pn.Text(f"{label} screen body", style=pn.style(font_size=16, font_weight="700")),
        *extra,
        style=pn.style(padding=16, gap=6),
    )


@pn.component
def StackHome() -> pn.Node:
    """The stack's first screen; its own ``title`` beats the navigator's."""
    use_report_focus()
    return _body("Home")


@pn.component
def StackCompose() -> pn.Node:
    """A grouped screen that takes the group's title."""
    use_report_focus()
    return _body("Compose")


@pn.component
def StackPreview() -> pn.Node:
    """A grouped screen whose own title beats the group's, guarded by ``before_remove``."""
    nav = use_report_focus()
    bus = pn.use_context(_BusContext)

    def subscribe() -> Optional[Callable[[], None]]:
        if bus is None:
            return None

        def before_remove(event: NavigationEvent) -> None:
            if bus.guard.current:
                event.prevent_default()
                bus.veto(str(event.data.get("action", "unknown")))

        return nav.add_listener("before_remove", before_remove)

    pn.use_effect(subscribe, [bus, nav])
    return _body("Preview", pn.Text("Guarded by before_remove while the guard is on.", style=pn.style(color="#475569")))


@pn.component
def StackPlain() -> pn.Node:
    """An ungrouped screen that sets its title from its render."""
    nav = use_report_focus()
    pn.use_screen_options(title=f"Nav {nav.route.name}")
    return _body("Plain")


DemoStack = pn.StackNavigator(
    pn.Screen(StackHome, name="Home", title="Home!"),
    pn.Group(
        pn.Screen(StackCompose, name="Compose"),
        pn.Screen(StackPreview, name="Preview", title="Preview!"),
        # Card presentation on purpose: a modal group would present the
        # nested screen as a sheet over this demo (see the presentation
        # demo for the modal styles).
        title="Grouped",
        header_back_title="Home",
    ),
    pn.Screen(StackPlain, name="Plain"),
    screen_options=pn.ScreenOptions(title="Nav default", header_back_title="Back"),
)
"""The nested stack: navigator, group, screen, and render-time options layered."""


@pn.component
def StackOptionsDemo() -> pn.Node:
    """Render a nested stack with layered options, pop_to, and a removal guard."""
    handle_ref: pn.Ref[Optional[pn.Navigation]] = pn.use_ref(None)
    guard_ref = pn.use_ref(False)
    focused, set_focused = pn.use_state("Home")
    depth, set_depth = pn.use_state(1)
    guard, set_guard = pn.use_state(False)
    vetoes, set_vetoes = pn.use_state(0)
    last_veto, set_last_veto = pn.use_state("none")
    guard_ref.current = guard

    def make_bus() -> _Bus:
        def report(name: str, count: int) -> None:
            set_focused(name)
            set_depth(count)

        def veto(action: str) -> None:
            set_vetoes(lambda n: n + 1)
            set_last_veto(action)

        return _Bus(handle=handle_ref, guard=guard_ref, report=report, veto=veto)

    # One bus for the demo's lifetime: a fresh context value on every render
    # would re-render every screen and re-run their focus effects.
    bus = pn.use_memo(make_bus, [])

    def act(run: Callable[[pn.Navigation], object]) -> Callable[[], None]:
        def _run() -> None:
            if handle_ref.current is not None:
                run(handle_ref.current)

        return _run

    return DemoScreen(
        "Stack options",
        "screen_options, Group, use_screen_options, pop_to, and a before_remove guard on a nested stack.",
        DemoSection(
            "Nested stack",
            ResultText("Focused route", focused),
            ResultText("Depth", depth),
            ResultText("Guard", "ON" if guard else "OFF"),
            ResultText("Vetoes", vetoes),
            ResultText("Last veto", last_veto),
            # The controls sit above the nested stack: a short screen can't show
            # the readouts, the stack, and three rows of buttons at once, and the
            # flow reads the stack's header titles from its top edge.
            ButtonsRow(
                pn.Button("Push Compose", on_press=act(lambda nav: nav.push(StackCompose()))),
                pn.Button("Push Preview", on_press=act(lambda nav: nav.push(StackPreview()))),
            ),
            ButtonsRow(
                pn.Button("Push Plain", on_press=act(lambda nav: nav.push(StackPlain()))),
                pn.Button("Pop to Home", on_press=act(lambda nav: nav.pop_to(StackHome))),
            ),
            ButtonsRow(
                pn.Button("Enable guard", on_press=lambda: set_guard(True)),
                pn.Button("Disable guard", on_press=lambda: set_guard(False)),
            ),
            pn.View(
                _BusContext.Provider(DemoStack(), value=bus),
                style=pn.style(height=200, border_radius=8, background_color="#F8FAFC", overflow="hidden"),
            ),
            Hint("Header titles: render beats screen beats group beats navigator. The guard vetoes pop_to."),
        ),
    )
