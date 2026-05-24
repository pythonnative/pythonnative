"""Demo screen for [`pn.Fragment`][pythonnative.Fragment].

A Fragment returned from a helper function should inline its
children into the surrounding parent. The demo asserts both fragment
texts appear inside the same card, with no extra wrapper element.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section


def _twin_lines() -> pn.Element:
    """Return two Text elements wrapped in a Fragment.

    Returning a Fragment from a plain helper lets the surrounding
    parent (a Column inside ``section``) flatten the siblings without
    introducing an extra container.
    """
    return pn.Fragment(
        pn.Text("Fragment line 1", style=pn.style(font_weight="600")),
        pn.Text("Fragment line 2", style=pn.style(color="#0369A1")),
    )


@pn.component
def FragmentDemo() -> pn.Element:
    """Render a card containing the two lines from ``_twin_lines``."""
    return demo_screen(
        "Fragment",
        "Fragment merges multiple children into the parent without a wrapper view.",
        section(
            "Fragment inside a card",
            _twin_lines(),
            hint("Both lines should appear inside the single card above."),
        ),
    )
