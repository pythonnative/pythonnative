"""Demo screen for [`pn.Pressable`][pythonnative.Pressable].

A Pressable wraps a colored View. Tapping toggles the background
color and bumps a counter so Maestro can assert ``on_press`` fired.
The same target exercises the RFC 0002 additions: a
[`PressState`][pythonnative.PressState] render function and style
callable, ``delay_long_press``, ``android_ripple``, and ``disabled``.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def PressableDemo() -> pn.Element:
    """Render a Pressable that toggles its background and tracks tap count."""
    count, set_count = pn.use_state(0)
    long_presses, set_long_presses = pn.use_state(0)
    disabled, set_disabled = pn.use_state(False)
    color = "#0EA5E9" if count % 2 == 0 else "#10B981"

    def on_press() -> None:
        set_count(count + 1)

    def render_label(state: pn.PressState) -> pn.Element:
        # The single callable child receives the live PressState; the
        # label flips while a finger is down and reads "Tap me
        # (Pressable)" the rest of the time so Maestro can target it.
        return pn.Text(
            "Pressing..." if state.pressed else "Tap me (Pressable)",
            style=pn.style(color="#FFFFFF", font_weight="700"),
        )

    def target_style(state: pn.PressState) -> pn.Style:
        return pn.style(
            padding=18,
            background_color=color,
            border_radius=12,
            align_items="center",
            opacity=0.6 if state.pressed else (0.4 if disabled else 1.0),
        )

    return demo_screen(
        "Pressable",
        "Tap the colored area; the press counter and background flip.",
        section(
            "Tap target",
            result_text("Presses", count),
            result_text("Long presses", long_presses),
            result_text("Disabled", "yes" if disabled else "no"),
            pn.Pressable(
                render_label,
                on_press=on_press,
                on_long_press=lambda: set_long_presses(long_presses + 1),
                delay_long_press=300,
                disabled=disabled,
                android_ripple=pn.Ripple(color="#33000000", borderless=False),
                style=target_style,
                accessibility_label="pressable-target",
            ),
            buttons_row(
                pn.Button("Disable pressable", on_press=lambda: set_disabled(True)),
                pn.Button("Enable pressable", on_press=lambda: set_disabled(False)),
            ),
            hint("Maestro taps and long-presses the area, then checks a disabled press is ignored."),
        ),
    )
