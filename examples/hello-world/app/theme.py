"""Shared styles for the hello-world demo.

Centralizing the most-reused text and layout styles keeps each screen
file focused on its own behaviour. Screen-specific styles
(``flex_box``, ``abs_canvas``, ``chip``, ``field``, etc.) stay inline
in the screen that owns them so each file remains self-contained.
"""

import pythonnative as pn

styles = pn.StyleSheet.create(
    title={"font_size": 24, "bold": True},
    subtitle={"font_size": 16, "color": "#666666"},
    section_title={"font_size": 18, "font_weight": "600", "color": "#0F172A"},
    hint={"font_size": 13, "color": "#6B7280"},
    section={"spacing": 16, "padding": 20, "align_items": "stretch"},
)
