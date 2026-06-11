"""Shared layout shell used by every demo screen.

``demo_screen`` renders a consistent structure so flows have a small,
predictable set of strings to wait on:

- ``"Demo: <title>"`` — anchor text marking that the demo loaded. Maestro
  flows start with ``extendedWaitUntil: visible: "Demo: <title>"`` so they
  wait for the screen to render before interacting.
- ``"Back to list"`` — the bottom button that pops back to the category
  list. Every demo has it in the same place, so cleanup is identical
  across flows.

Demo screens supply only the body content; everything around it is
boilerplate kept in one file so the surface area each Maestro flow
needs to learn stays small.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import pythonnative as pn
from app.theme import styles


def demo_screen(
    title: str,
    summary: str,
    *body: pn.Element,
    refresh_control: Optional[Dict[str, Any]] = None,
) -> pn.Element:
    """Render a demo screen with a stable header, body, and back button.

    Args:
        title: Demo title shown as ``"Demo: <title>"`` text. This is
            the canonical "screen loaded" marker for Maestro flows.
        summary: One-line description of what the demo demonstrates.
            Shown beneath the title in the secondary text style.
        *body: Children that contain the actual demo content.
        refresh_control: Optional pull-to-refresh spec attached to the
            page scroll view. A page-level pull gives the gesture the
            full screen of travel it needs to cross the platform's
            activation threshold.

    Returns:
        A scrollable [`pn.ScrollView`][pythonnative.ScrollView]
        wrapping the title, summary, body, and a back button.
    """
    nav = pn.use_navigation()
    return pn.ScrollView(
        pn.Column(
            pn.Text(f"Demo: {title}", style=styles["title"]),
            pn.Text(summary, style=styles["subtitle"]),
            *body,
            pn.Button("Back to list", on_click=nav.go_back),
            style=styles["screen"],
        ),
        refresh_control=refresh_control,
    )


def card(*children: pn.Element) -> pn.Element:
    """Wrap demo children in a soft card so the body has visual structure."""
    return pn.View(*children, style=styles["card"])


def result_text(prefix: str, value: object) -> pn.Element:
    """Render a ``"<prefix>: <value>"`` line in the bright result style.

    Used by demos to expose dynamic state Maestro can assert against.
    The exact whitespace is preserved so flows can match exactly:

        ``assertVisible: "Counter: 5"``
    """
    return pn.Text(f"{prefix}: {value}", style=styles["result"])


def label(text: str) -> pn.Element:
    """Render a small label above a control."""
    return pn.Text(text, style=styles["section_title"])


def hint(text: str) -> pn.Element:
    """Render a quieter explanatory line."""
    return pn.Text(text, style=styles["hint"])


def section(title: str, *children: pn.Element) -> pn.Element:
    """A titled card with multiple children, separated by spacing."""
    return card(label(title), *children)


def buttons_row(*buttons: pn.Element) -> pn.Element:
    """Lay out a horizontal row of buttons with consistent spacing."""
    return pn.Row(*buttons, style=styles["row"])


def list_lines(lines: Iterable[str]) -> pn.Element:
    """Render a vertical column of plain text lines (label style)."""
    return pn.Column(
        *[pn.Text(line, style=styles["label"]) for line in lines],
        style=pn.style(spacing=4),
    )
