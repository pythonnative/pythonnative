"""Demo screen for [`pn.Keyboard`][pythonnative.Keyboard].

Focusing the field brings up the software keyboard; ``Keyboard.add_listener``
mirrors every [`KeyboardEvent`][pythonnative.KeyboardEvent] into the
readouts, ``Keyboard.is_visible()`` answers the current state, and the
"Dismiss keyboard" button (above the field) calls ``Keyboard.dismiss()``,
which resigns the focused input so ``on_blur`` fires and the visibility
readout flips back to "no".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def KeyboardDemo() -> pn.Element:
    """Render a text field plus Keyboard module readouts and a dismiss button."""
    text, set_text = pn.use_state("")
    focused, set_focused = pn.use_state(False)
    events, set_events = pn.use_state(0)
    visible, set_visible = pn.use_state(pn.Keyboard.is_visible())
    last_height, set_last_height = pn.use_state(0)
    dismiss_calls, set_dismiss_calls = pn.use_state(0)

    def subscribe():
        def on_event(event: pn.KeyboardEvent) -> None:
            set_events(lambda n: n + 1)
            set_visible(event.visible)
            set_last_height(int(event.height))

        return pn.Keyboard.add_listener(on_event)

    pn.use_effect(subscribe, [])

    def dismiss() -> None:
        pn.Keyboard.dismiss()
        set_dismiss_calls(dismiss_calls + 1)
        set_visible(pn.Keyboard.is_visible())

    return demo_screen(
        "Keyboard",
        "Keyboard.is_visible, add_listener, and dismiss.",
        section(
            "Keyboard module",
            # The button sits above the field: the software keyboard covers
            # the lower half of a short screen while the field is focused.
            pn.Button("Dismiss keyboard", on_press=dismiss),
            result_text("Focused", "ON" if focused else "OFF"),
            result_text("Keyboard visible", "yes" if visible else "no"),
            result_text("Keyboard events", events),
            result_text("Last height positive", "yes" if last_height > 0 else "no"),
            result_text("Dismiss calls", dismiss_calls),
            pn.TextInput(
                value=text,
                on_change=set_text,
                placeholder="Focus me for the keyboard",
                on_focus=lambda: set_focused(True),
                on_blur=lambda: set_focused(False),
                style=pn.style(
                    padding=10,
                    border_radius=6,
                    border_width=1,
                    border_color="#CBD5E1",
                    background_color="#FFFFFF",
                    font_size=16,
                ),
            ),
            hint("Maestro focuses the field, then dismisses the keyboard from Python."),
        ),
    )
