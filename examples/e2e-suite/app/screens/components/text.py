"""Demo screen for [`pn.Text`][pythonnative.Text].

Exercises the simplest element factory in isolation, including
``style`` font sizing, bold, color, and a few combined styles, plus the
RFC 0002 additions: ``ellipsize_mode`` truncation, ``selectable`` text,
``on_press`` on a label, and a pressable nested span. Maestro asserts
that several text labels render together and taps the pressable ones.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section

_LONG_LINE = (
    "This deliberately long single line keeps going and going so the "
    "renderer has to truncate it somewhere in the middle of the text."
)


@pn.component
def TextDemo() -> pn.Element:
    """Render a handful of [`Text`][pythonnative.Text] variants."""
    label_presses, set_label_presses = pn.use_state(0)
    span_presses, set_span_presses = pn.use_state(0)

    return demo_screen(
        "Text",
        "Plain text, bold text, sized text, and colored text in one place.",
        section(
            "Plain text",
            pn.Text("Plain text line"),
            hint("Renders with default body style."),
        ),
        section(
            "Bold text",
            pn.Text("Bold text line", style=pn.style(bold=True, font_size=18)),
        ),
        section(
            "Sized + colored text",
            pn.Text(
                "Sized and colored line",
                style=pn.style(font_size=20, color="#DC2626", font_weight="600"),
            ),
        ),
        section(
            "Multi-line text",
            pn.Text(
                "First paragraph that should wrap if it is long enough to "
                "exceed the available horizontal space inside its parent.",
                style=pn.style(font_size=14, color="#1F2937", line_height=20),
            ),
        ),
        section(
            "Truncation + selection",
            pn.Text(
                _LONG_LINE,
                ellipsize_mode="middle",
                accessibility_label="truncated-middle",
                style=pn.style(font_size=14, max_lines=1),
            ),
            pn.Text(
                "Selectable text line",
                selectable=True,
                allow_font_scaling=False,
                style=pn.style(font_size=14, color="#1F2937"),
            ),
            hint("The long line truncates with an ellipsis in the middle."),
        ),
        section(
            "Pressable text",
            result_text("Label presses", label_presses),
            result_text("Span presses", span_presses),
            pn.Text(
                "Tap this whole label",
                on_press=lambda: set_label_presses(label_presses + 1),
                style=pn.style(font_size=16, color="#2563EB", font_weight="600"),
            ),
            pn.Text(
                pn.Text(
                    "Tap this span",
                    on_press=lambda: set_span_presses(span_presses + 1),
                    style=pn.style(color="#2563EB", font_weight="600"),
                ),
                # Hug the text: presses outside a span's glyphs go to the
                # outer Text (React Native semantics), and Maestro taps the
                # element's center.
                style=pn.style(font_size=16, align_self="flex_start"),
            ),
            hint("Maestro taps the label and the span and asserts both counters."),
        ),
        section(
            "Rich text (nested spans)",
            pn.Text(
                "Rich start ",
                pn.Text("bold middle", style=pn.style(bold=True)),
                pn.Text(" red end", style=pn.style(color="#DC2626")),
                style=pn.style(font_size=15),
            ),
            hint("One native label built from three styled spans."),
        ),
    )
