"""Demo screen for [`pn.AccessibilityInfo`][pythonnative.AccessibilityInfo].

Reads the screen-reader and Reduce Motion settings, subscribes to
[`AccessibilityEvent`][pythonnative.AccessibilityEvent] changes, posts an
announcement, and moves accessibility focus to a target through its
``ref``. Neither setting is on in the CI emulators, so the flow asserts the
"no" readouts, then drives the two imperative calls and asserts their
counters (they are no-ops without a screen reader but must not raise).
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def AccessibilityInfoDemo() -> pn.Element:
    """Render accessibility settings plus announce / focus controls."""
    target_ref = pn.use_ref(None)
    announcements, set_announcements = pn.use_state(0)
    focus_calls, set_focus_calls = pn.use_state(0)
    changes, set_changes = pn.use_state(0)
    screen_reader = pn.AccessibilityInfo.is_screen_reader_enabled()
    reduce_motion = pn.AccessibilityInfo.is_reduce_motion_enabled()

    def subscribe():
        def on_change(event: pn.AccessibilityEvent) -> None:
            del event
            set_changes(lambda n: n + 1)

        return pn.AccessibilityInfo.add_listener(on_change)

    pn.use_effect(subscribe, [])

    def announce() -> None:
        pn.AccessibilityInfo.announce("Announcement from the E2E suite")
        set_announcements(announcements + 1)

    def focus_target() -> None:
        if target_ref.current is not None:
            pn.AccessibilityInfo.set_accessibility_focus(target_ref)
            set_focus_calls(focus_calls + 1)

    return demo_screen(
        "AccessibilityInfo",
        "Screen reader / reduce motion readers, announce, and focus.",
        section(
            "AccessibilityInfo module",
            result_text("Screen reader", "yes" if screen_reader else "no"),
            result_text("Reduce motion", "yes" if reduce_motion else "no"),
            result_text("Setting changes", changes),
            result_text("Announcements", announcements),
            result_text("Focus calls", focus_calls),
            pn.View(
                pn.Text("a11y-focus-target", style=pn.style(color="#FFFFFF", font_weight="700")),
                ref=target_ref,
                accessible=True,
                accessibility_label="a11y-focus-target",
                style=pn.style(padding=14, background_color="#8B5CF6", border_radius=10, align_items="center"),
            ),
            buttons_row(
                pn.Button("Announce", on_press=announce),
                pn.Button("Focus target", on_press=focus_target),
            ),
            hint("Both calls are safe no-ops when no screen reader is running."),
        ),
    )
