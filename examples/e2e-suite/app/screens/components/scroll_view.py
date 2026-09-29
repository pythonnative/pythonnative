"""Demo screen for [`pn.ScrollView`][pythonnative.ScrollView].

Renders a tall column of numbered rows inside a fixed-height scroll
view. Maestro asserts the first row, scrolls, and then asserts a row
that was initially off-screen. A second, horizontal ScrollView below it
covers the RFC 0002 additions: ``horizontal``, ``content_container_style``,
``snap_to_interval``, ``deceleration_rate``, the drag and momentum
callbacks, and the typed [`ScrollEvent`][pythonnative.ScrollEvent].
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section

_TILE_WIDTH = 140


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
    offset_y, set_offset_y = pn.use_state(0)
    drag_events, set_drag_events = pn.use_state(0)
    momentum_events, set_momentum_events = pn.use_state(0)
    horizontal_x, set_horizontal_x = pn.use_state(0)

    def on_scroll(event: pn.ScrollEvent) -> None:
        # Flip once on the first scroll event. After the re-render the
        # reconciler swaps in this fresh callback (now closing over
        # ``scrolled=True``), so subsequent events only track the offset.
        if not scrolled:
            set_scrolled(True)
        set_offset_y(int(event.y))

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
                scroll_event_throttle=32,
                style=pn.style(height=400, border_width=1, border_color="#CBD5E1"),
            ),
            result_text("Offset y positive", "yes" if offset_y > 0 else "no"),
            hint("Maestro scrolls to reveal a row from later in the list."),
        ),
        section(
            "Horizontal + snapping",
            result_text("Drag", "ON" if drag_events > 0 else "OFF"),
            result_text("Momentum ends", momentum_events),
            result_text("Snapped x", horizontal_x),
            pn.ScrollView(
                *[
                    pn.View(
                        pn.Text(f"HRow {i}", style=pn.style(color="#FFFFFF", font_weight="700")),
                        style=pn.style(
                            width=_TILE_WIDTH - 12,
                            height=72,
                            border_radius=10,
                            background_color="#6366F1" if i % 2 else "#0EA5E9",
                            align_items="center",
                            justify_content="center",
                        ),
                    )
                    for i in range(1, 13)
                ],
                horizontal=True,
                # Applied by wrapping the tiles in one inner View, so the
                # padding and gap work on every renderer.
                content_container_style=pn.style(padding_horizontal=6, gap=12, align_items="center"),
                snap_to_interval=_TILE_WIDTH,
                snap_to_alignment="start",
                deceleration_rate="fast",
                shows_scroll_indicator=False,
                on_scroll_begin_drag=lambda e: set_drag_events(lambda n: n + 1),
                on_scroll_end_drag=lambda e: set_horizontal_x(int(e.x)),
                on_momentum_scroll_end=lambda e: set_momentum_events(lambda n: n + 1),
                style=pn.style(height=96, border_width=1, border_color="#CBD5E1"),
            ),
            hint("Swipe the tiles left; the drag callback flips 'Drag' to ON."),
        ),
    )
