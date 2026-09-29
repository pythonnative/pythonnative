"""Demo screen for [`pn.BlurView`][pythonnative.BlurView].

A ``BlurView`` blurs whatever is drawn behind it. Here it floats over a
gradient so the effect is visible. Maestro asserts the text inside the
blur renders; the blur itself isn't inspected.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


@pn.component
def BlurViewDemo() -> pn.Element:
    """Float light and dark blur panels over a colorful gradient."""
    panel = pn.style(width=130, height=70, border_radius=12, align_items="center", justify_content="center")
    return demo_screen(
        "BlurView",
        "A container that blurs the content behind it.",
        section(
            "Over a gradient",
            pn.LinearGradient(
                pn.Row(
                    pn.BlurView(pn.Text("light", style=pn.style(color="#111827")), blur_type="light", style=panel),
                    pn.BlurView(pn.Text("dark", style=pn.style(color="#F9FAFB")), blur_type="dark", style=panel),
                    style=pn.style(spacing=12),
                ),
                pn.BlurView(
                    pn.Text("intensity 40", style=pn.style(color="#111827")),
                    blur_type="regular",
                    intensity=40,
                    style=pn.style(**{**panel, "width": 272, "margin_top": 12}),
                ),
                colors=["#F97316", "#DB2777", "#4F46E5"],
                start_point=(0, 0),
                end_point=(1, 1),
                style=pn.style(padding=16, border_radius=16, align_items="center"),
            ),
            hint("iOS: UIVisualEffectView. Android: a blurred snapshot of the backdrop. Browser: backdrop-filter."),
        ),
    )
