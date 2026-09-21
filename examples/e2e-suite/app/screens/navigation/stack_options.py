"""Demo screen for navigator ``screen_options``, ``Group``, ``pop_to``, and ``before_remove``.

A nested Stack navigator layers its options the way React Navigation
does: ``Navigator(screen_options=callable)`` applies to every screen, a
[`ScreenGroup`][pythonnative.ScreenGroup] from ``Stack.Group(...)``
overrides it for its members, and each ``Screen`` overrides both. The
Python-drawn header shows the winning title. The controls live in the
persistent demo body (see ``drawer_navigator.py`` for why) and drive the
active screen's handle through a context bus: push each screen,
``pop_to("Home")`` from deep in the stack, and toggle a ``before_remove``
guard on the Preview screen that vetoes removal while enabled.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_Stack = pn.create_stack_navigator()

# Shared with the nested screens: ``ref`` receives the focused screen's
# navigation handle, ``guard`` is the current veto switch, ``report``
# mirrors the focused route into the demo body, ``veto`` counts vetoes.
_Bus: pn.Context[Dict[str, Any]] = pn.create_context({})


def _make_screen(label: str) -> Callable[[], pn.Element]:
    @pn.component
    def Screen() -> pn.Element:
        nav = pn.use_navigation()
        bus = pn.use_context(_Bus)

        def on_focus() -> None:
            bus["ref"].current = nav
            bus["report"](nav.route.name, len(nav.get_state().routes))

        pn.use_focus_effect(on_focus, [])
        return pn.Column(
            pn.Text(f"{label} screen body", style=pn.style(font_size=16, font_weight="700")),
            style=pn.style(padding=16),
        )

    return Screen


@pn.component
def _PreviewScreen() -> pn.Element:
    nav = pn.use_navigation()
    bus = pn.use_context(_Bus)

    def on_focus() -> None:
        bus["ref"].current = nav
        bus["report"](nav.route.name, len(nav.get_state().routes))

    pn.use_focus_effect(on_focus, [])

    def subscribe():
        def before_remove(event: Any) -> None:
            if bus["guard"].current:
                event.prevent_default()
                bus["veto"](event.data.get("action", "unknown"))

        return nav.add_listener("before_remove", before_remove)

    pn.use_effect(subscribe, [])
    return pn.Column(
        pn.Text("Preview screen body", style=pn.style(font_size=16, font_weight="700")),
        pn.Text("Guarded by before_remove while the guard is on.", style=pn.style(color="#475569")),
        style=pn.style(padding=16, spacing=6),
    )


_Home = _make_screen("Home")
_Compose = _make_screen("Compose")
_Plain = _make_screen("Plain")


@pn.component
def StackOptionsDemo() -> pn.Element:
    """Render a nested stack with layered options, pop_to, and a removal guard."""
    handle_ref = pn.use_ref(None)
    guard_ref = pn.use_ref(False)
    focused, set_focused = pn.use_state("Home")
    depth, set_depth = pn.use_state(1)
    guard, set_guard = pn.use_state(False)
    vetoes, set_vetoes = pn.use_state(0)
    last_veto, set_last_veto = pn.use_state("none")
    guard_ref.current = guard

    def report(name: str, count: int) -> None:
        set_focused(name)
        set_depth(count)

    def veto(action: str) -> None:
        set_vetoes(lambda n: n + 1)
        set_last_veto(action)

    bus = {"ref": handle_ref, "guard": guard_ref, "report": report, "veto": veto}

    def act(method: str, *args: Any) -> Callable[[], None]:
        def _run() -> None:
            handle = handle_ref.current
            if handle is not None:
                getattr(handle, method)(*args)

        return _run

    return demo_screen(
        "Stack options",
        "screen_options, Group, pop_to, and a before_remove guard on a nested stack.",
        section(
            "Nested stack",
            result_text("Focused route", focused),
            result_text("Depth", depth),
            result_text("Guard", "ON" if guard else "OFF"),
            result_text("Vetoes", vetoes),
            result_text("Last veto", last_veto),
            # The controls sit above the nested stack: a short screen can't show
            # the readouts, the stack, and three rows of buttons at once, and the
            # flow reads the stack's header titles from its top edge.
            buttons_row(
                pn.Button("Push Compose", on_press=act("push", "Compose")),
                pn.Button("Push Preview", on_press=act("push", "Preview")),
            ),
            buttons_row(
                pn.Button("Push Plain", on_press=act("push", "Plain")),
                pn.Button("Pop to Home", on_press=act("pop_to", "Home")),
            ),
            buttons_row(
                pn.Button("Enable guard", on_press=lambda: set_guard(True)),
                pn.Button("Disable guard", on_press=lambda: set_guard(False)),
            ),
            pn.View(
                _Bus.Provider(
                    _Stack.Navigator(
                        _Stack.Screen("Home", _Home, title="Home!"),
                        _Stack.Group(
                            _Stack.Screen("Compose", _Compose),
                            _Stack.Screen("Preview", _PreviewScreen, title="Preview!"),
                            # Card presentation on purpose: a modal group would present
                            # the nested screen as a sheet over this demo (see the
                            # presentation demo for the modal styles).
                            screen_options={"title": "Grouped", "header_back_title": "Home"},
                        ),
                        _Stack.Screen("Plain", _Plain),
                        screen_options=lambda route: {"title": f"Nav {route.name}", "header_back_title": "Back"},
                    ),
                    value=bus,
                ),
                style=pn.style(height=200, border_radius=8, background_color="#F8FAFC", overflow="hidden"),
            ),
            hint("Header titles: screen beats group beats navigator. The guard vetoes pop_to."),
        ),
    )
