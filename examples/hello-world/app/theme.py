"""Shared styles for the hello-world demo.

Centralizing the most-reused text and layout styles keeps each screen
file focused on its own behaviour. Screen-specific styles
(``flex_box``, ``abs_canvas``, ``chip``, ``field``, etc.) stay inline
in the screen that owns them so each file remains self-contained.

Each entry is built with :func:`pythonnative.style` so the values are
fully type-checked: pass ``align_items="centre"`` (typo) and
mypy/pyright will flag it against the ``AlignItems`` ``Literal``.
"""

import pythonnative as pn

styles = pn.StyleSheet.create(
    title=pn.style(font_size=24, bold=True),
    subtitle=pn.style(font_size=16, color="#666666"),
    section_title=pn.style(font_size=18, font_weight="600", color="#0F172A"),
    hint=pn.style(font_size=13, color="#6B7280"),
    section=pn.style(spacing=16, padding=20, align_items="stretch"),
)
