"""Demo screen for the accessibility props added in RFC 0002.

A stepper-like target carries ``accessibility_value`` (a
[`AccessibilityValue`][pythonnative.AccessibilityValue] record),
``accessibility_actions`` ([`AccessibilityAction`][pythonnative.AccessibilityAction]
records), an ``on_accessibility_action`` handler, a ``polite`` live region,
and a decoy view hidden with ``important_for_accessibility``. Screen
readers can't be scripted from Maestro, so the flow drives the same
handler through visible buttons and asserts the mirrored value; the
props themselves are validated by mounting on every renderer.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_ACTIONS: list[pn.AccessibilityAction] = [
    {"name": "increment", "label": "Increase the value"},
    {"name": "decrement", "label": "Decrease the value"},
    {"name": "activate"},
]


@pn.component
def AccessibilityPropsDemo() -> pn.Node:
    """Render a target with value, actions, importance, and a live region."""
    value, set_value = pn.use_state(5)
    last_action, set_last_action = pn.use_state("none")

    def on_action(name: str) -> None:
        set_last_action(name)
        if name == "increment":
            set_value(lambda v: min(10, v + 1))
        elif name == "decrement":
            set_value(lambda v: max(0, v - 1))

    accessibility_value: pn.AccessibilityValue = {"min": 0, "max": 10, "now": value, "text": f"{value} of 10"}

    return DemoScreen(
        "Accessibility props",
        "accessibility_value, accessibility_actions, and important_for_accessibility.",
        DemoSection(
            "Adjustable target",
            ResultText("Value", value),
            ResultText("Last action", last_action),
            pn.View(
                pn.Text(f"a11y-target {value}", style=pn.style(color="#FFFFFF", font_weight="700")),
                accessibility_label="a11y-target",
                accessibility_role="adjustable",
                accessibility_value=accessibility_value,
                accessibility_actions=_ACTIONS,
                on_accessibility_action=on_action,
                accessibility_live_region="polite",
                style=pn.style(
                    padding=16,
                    background_color="#0EA5E9",
                    border_radius=10,
                    align_items="center",
                ),
            ),
            ButtonsRow(
                pn.Button("Increment", on_press=lambda: on_action("increment")),
                pn.Button("Decrement", on_press=lambda: on_action("decrement")),
            ),
            Hint("A screen reader's increment/decrement actions route to the same handler."),
        ),
        DemoSection(
            "important_for_accessibility",
            pn.View(
                pn.Text("decorative-only", style=pn.style(color="#94A3B8")),
                important_for_accessibility="no_hide_descendants",
                style=pn.style(padding=8),
            ),
            pn.Text("a11y-visible-marker", style=pn.style(font_weight="600")),
            Hint("The grey decorative text is hidden from assistive technology."),
        ),
    )
