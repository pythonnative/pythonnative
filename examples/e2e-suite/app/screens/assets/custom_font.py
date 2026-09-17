"""Demo screen for bundled fonts.

Any ``.ttf`` or ``.otf`` under ``app/assets/`` is registered at startup,
and ``font_family`` refers to it by the family name inside the file
(here ``"Pacifico"``, from ``app/assets/fonts/Pacifico-Regular.ttf``).
Nothing is configured per platform.

Maestro asserts the text that reports what the runtime found in the
manifest; the glyph shapes themselves aren't inspected.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section
from pythonnative.assets import font_faces


@pn.component
def CustomFontDemo() -> pn.Element:
    """Render text in a bundled font and list the registered faces."""
    faces = font_faces()
    families = sorted({face.family for face in faces})
    return demo_screen(
        "Custom font",
        "Fonts under app/assets/ are available to font_family by their family name.",
        section(
            "Pacifico",
            pn.Text(
                "Hello from a bundled font",
                style=pn.style(font_family="Pacifico", font_size=28, color="#0F766E"),
            ),
            pn.Text(
                "Rich text ",
                pn.Text("mixes faces", style=pn.style(font_family="Pacifico", font_size=20)),
                pn.Text(" inside one Text."),
                style=pn.style(font_size=16),
            ),
            hint("The same family name works on iOS, Android, and in the browser preview."),
        ),
        section(
            "Registered faces",
            result_text("Bundled families", ", ".join(families) or "none"),
            result_text("Face count", len(faces)),
            result_text("Pacifico weight", next((face.weight for face in faces if face.family == "Pacifico"), "n/a")),
        ),
    )
