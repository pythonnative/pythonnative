"""Demo screen for [`pn.batch_updates`][pythonnative.batch_updates].

Two ``use_state`` updates wrapped in ``batch_updates`` should produce
exactly one extra render, regardless of how many setters fire. The
demo tracks the render count to expose this.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def BatchUpdatesDemo() -> pn.Element:
    """Render a screen tracking render counts across batched vs unbatched setters."""
    renders = pn.use_ref(0)
    renders.current += 1

    a, set_a = pn.use_state(0)
    b, set_b = pn.use_state(0)

    def update_both_unbatched() -> None:
        set_a(a + 1)
        set_b(b + 1)

    def update_both_batched() -> None:
        with pn.batch_updates():
            set_a(a + 1)
            set_b(b + 1)

    return demo_screen(
        "batch_updates",
        "Compare batched vs unbatched setter calls by render count.",
        section(
            "State values",
            result_text("a", a),
            result_text("b", b),
            result_text("Render count", renders.current),
            buttons_row(
                pn.Button("Unbatched bump", on_press=update_both_unbatched),
                pn.Button("Batched bump", on_press=update_both_batched),
            ),
            hint("Tapping 'Batched bump' increases render count by 1; 'Unbatched bump' may increase by 2."),
        ),
    )
