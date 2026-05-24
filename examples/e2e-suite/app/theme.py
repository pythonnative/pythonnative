"""Shared styles for the E2E suite app.

Every demo screen reuses the same handful of styles so flows can rely
on consistent layout (no surprise scrolling, predictable spacing). The
exact visual style is unimportant; what matters is that text labels
are large enough for Maestro to find them and that controls don't
overlap.
"""

import pythonnative as pn

styles = pn.StyleSheet.create(
    screen=pn.style(spacing=12, padding=16, align_items="stretch"),
    title=pn.style(font_size=22, bold=True, color="#0F172A"),
    subtitle=pn.style(font_size=14, color="#475569"),
    section_title=pn.style(font_size=16, font_weight="600", color="#0F172A"),
    label=pn.style(font_size=14, color="#1F2937"),
    result=pn.style(font_size=15, font_weight="600", color="#047857"),
    hint=pn.style(font_size=12, color="#6B7280"),
    card=pn.style(
        padding=12,
        spacing=8,
        background_color="#F8FAFC",
        border_radius=8,
        border_width=1,
        border_color="#E2E8F0",
    ),
    row=pn.style(spacing=8, align_items="center"),
)
