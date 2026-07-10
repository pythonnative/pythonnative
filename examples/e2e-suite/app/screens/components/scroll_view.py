"""Demo screen for [`pn.ScrollView`][pythonnative.ScrollView].

Renders a tall column of numbered rows inside a fixed-height scroll
view. Maestro asserts the first row, scrolls, and then asserts a row
that was initially off-screen.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@pn.component
def ScrollViewDemo() -> pn.Element:
    """Render a fixed-height ScrollView with 60 numbered rows.

    60 rows (not 30) so the last row's *unclipped* accessibility frame
    lands beyond the physical screen even on the tallest simulators
    (e.g. iPhone Pro Max at 956 pt). ScrollView children keep their
    content-coordinate frames in the accessibility tree when clipped,
    and Maestro treats anything inside the screen bounds as visible,
    so a shorter list lets ``scrollUntilVisible`` short-circuit with
    zero swipes and the on_scroll assertion below never flips.
    """
    rows = list(range(1, 61))
    scrolled, set_scrolled = pn.use_state(False)

    def on_scroll(payload: dict) -> None:
        # Flip once on the first scroll event (payload carries the
        # ``{"x", "y"}`` content offset). After the re-render the
        # reconciler swaps in this fresh callback (now closing over
        # ``scrolled=True``), so subsequent events are cheap no-ops.
        if not scrolled:
            set_scrolled(True)

    return demo_screen(
        "ScrollView",
        "Scroll vertically to reveal rows beyond the visible area.",
        section(
            "Tall content",
            result_text("Scrolled", "ON" if scrolled else "OFF"),
            # The ScrollView is intentionally large enough to overlap
            # the screen's vertical center on both the iOS and Android
            # CI emulators. Maestro's ``scrollUntilVisible`` always
            # swipes from the screen center; a smaller (e.g. 200 dp)
            # container near the top of the page leaves screen center
            # outside its bounds, and the swipe scrolls the outer page
            # ScrollView instead of this one. Keep this >= ~350 dp so
            # the test exercises the inner scroll path on both
            # platforms.
            pn.ScrollView(
                pn.Column(
                    *[
                        pn.Text(
                            f"ScrollRow {i}",
                            style=pn.style(font_size=15, padding=8, background_color="#F1F5F9"),
                        )
                        for i in rows
                    ],
                    style=pn.style(spacing=4),
                ),
                on_scroll=on_scroll,
                style=pn.style(height=400, border_width=1, border_color="#CBD5E1"),
            ),
            hint("Maestro scrolls to reveal a row from later in the list."),
        ),
    )
