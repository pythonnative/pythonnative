"""Demo screen for [`pn.KeyboardAvoidingView`][pythonnative.KeyboardAvoidingView].

The actual keyboard-avoidance behavior depends on the platform and on
whether a TextInput is focused; Maestro can't easily reproduce the
edge cases. The demo confirms the component instantiates without
error and renders its children. A nested TextInput is included so the
mount path matches the production usage.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint


@pn.component
def KeyboardAvoidingViewDemo() -> pn.Node:
    """Render KeyboardAvoidingView with a TextInput inside it."""
    value, set_value = pn.use_state("")
    return DemoScreen(
        "KeyboardAvoidingView",
        "TextInput inside a KeyboardAvoidingView; mainly a smoke test.",
        DemoSection(
            "Body",
            pn.KeyboardAvoidingView(
                pn.Column(
                    pn.Text("KAV body label", style=pn.style(font_weight="600")),
                    pn.TextInput(
                        value=value,
                        placeholder="Tap to focus the keyboard",
                        on_change=set_value,
                        style=pn.style(
                            padding=10,
                            border_radius=6,
                            border_width=1,
                            border_color="#CBD5E1",
                            background_color="#FFFFFF",
                        ),
                    ),
                    style=pn.style(gap=8),
                )
            ),
            Hint("Maestro asserts 'KAV body label' is visible after mount."),
        ),
    )
