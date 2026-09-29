"""Demo screen for [`DynamicColor`][pythonnative.DynamicColor] and ``inset``.

A box paints its background from a ``{"light": ..., "dark": ...}`` color
pair; the demo flips the app's color scheme through
``pn.appearance.set_color_scheme`` and mirrors the resolved scheme so
Maestro can assert the flip happened on every renderer. A second box
positions an absolutely placed child with the ``inset`` shorthand added
in RFC 0002. The scheme is reset when the demo unmounts so later flows
start from the system default.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_DYNAMIC_BACKGROUND: pn.DynamicColor = {"light": "#0EA5E9", "dark": "#1E3A8A"}
_DYNAMIC_TEXT: pn.DynamicColor = {"light": "#0F172A", "dark": "#F8FAFC"}


@pn.component
def DynamicColorDemo() -> pn.Element:
    """Render a scheme-aware box and an inset-positioned child."""
    scheme = pn.use_color_scheme()

    def reset_scheme() -> None:
        return pn.appearance.set_color_scheme(None)

    pn.use_effect(lambda: reset_scheme, [])

    return demo_screen(
        "Dynamic color",
        "Light/dark color pairs resolve against the current scheme.",
        section(
            "DynamicColor",
            result_text("Scheme", scheme),
            pn.View(
                pn.Text(
                    "dynamic-color-box",
                    style=pn.style(color={"light": "#FFFFFF", "dark": "#BFDBFE"}, font_weight="700"),
                ),
                style=pn.style(
                    padding=16,
                    border_radius=10,
                    background_color=_DYNAMIC_BACKGROUND,
                    border_width=2,
                    border_color=_DYNAMIC_TEXT,
                    align_items="center",
                ),
            ),
            buttons_row(
                pn.Button("Use dark scheme", on_press=lambda: pn.appearance.set_color_scheme("dark")),
                pn.Button("Use light scheme", on_press=lambda: pn.appearance.set_color_scheme("light")),
            ),
            hint("The box repaints from the pair when the scheme flips."),
        ),
        section(
            "inset shorthand",
            pn.View(
                pn.View(
                    pn.Text("inset-child", style=pn.style(color="#FFFFFF", font_weight="600")),
                    style=pn.style(
                        position="absolute",
                        inset=10,
                        background_color="#F97316",
                        border_radius=6,
                        align_items="center",
                        justify_content="center",
                    ),
                ),
                style=pn.style(height=90, background_color="#E2E8F0", border_radius=8),
            ),
            hint("inset=10 pins the orange child 10dp from every edge of the grey box."),
        ),
    )
