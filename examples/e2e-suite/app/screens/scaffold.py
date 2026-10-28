"""Shared layout components used by every demo screen.

``DemoScreen`` renders a consistent structure so flows have a small,
predictable set of strings to wait on:

- ``"Demo: <title>"``: anchor text marking that the demo loaded. Maestro
  flows start with ``extendedWaitUntil: visible: "Demo: <title>"`` so they
  wait for the screen to render before interacting.
- ``"Back to list"``: the bottom button that pops back to the category
  list. Every demo has it in the same place, so cleanup is identical
  across flows.

Demo screens supply only the body content; everything around it is
boilerplate kept in one file so the surface area each Maestro flow
needs to learn stays small. Every piece is a component that reads the
theme through [`use_styles`][pythonnative.use_styles], so the whole
suite follows the dark-mode switch.
"""

from __future__ import annotations

from typing import Optional

import pythonnative as pn
from app.theme import AppStyles, Layout


@pn.component
def DemoScreen(
    title: str,
    summary: str,
    *body: pn.Node,
    refresh_control: Optional[pn.Element] = None,
) -> pn.Node:
    """Render a demo screen with a stable header, body, and back button.

    Args:
        title: Demo title shown as ``"Demo: <title>"`` text. This is
            the canonical "screen loaded" marker for Maestro flows.
        summary: One-line description of what the demo demonstrates.
            Shown beneath the title in the secondary text style.
        *body: Children that contain the actual demo content.
        refresh_control: Optional [`pn.RefreshControl`][pythonnative.RefreshControl]
            attached to the page scroll view. A page-level pull gives the gesture the
            full screen of travel it needs to cross the platform's
            activation threshold.
    """
    nav = pn.use_navigation()
    styles = pn.use_styles(AppStyles)
    return pn.ScrollView(
        pn.Column(
            pn.Text(f"Demo: {title}", style=styles.title),
            pn.Text(summary, style=styles.subtitle),
            *body,
            pn.Button("Back to list", on_press=nav.go_back),
            style=Layout.screen,
        ),
        refresh_control=refresh_control,
    )


@pn.component
def Card(*children: pn.Node) -> pn.Node:
    """Wrap demo children in a soft card so the body has visual structure."""
    styles = pn.use_styles(AppStyles)
    return pn.View(*children, style=styles.card)


@pn.component
def ResultText(prefix: str, value: object) -> pn.Node:
    """Render a ``"<prefix>: <value>"`` line in the bright result style.

    Used by demos to expose dynamic state Maestro can assert against.
    The exact whitespace is preserved so flows can match exactly:

        ``assertVisible: "Counter: 5"``
    """
    styles = pn.use_styles(AppStyles)
    return pn.Text(f"{prefix}: {value}", style=styles.result)


@pn.component
def Label(text: str) -> pn.Node:
    """Render a small label above a control."""
    styles = pn.use_styles(AppStyles)
    return pn.Text(text, style=styles.section_title)


@pn.component
def Hint(text: str) -> pn.Node:
    """Render a quieter explanatory line."""
    styles = pn.use_styles(AppStyles)
    return pn.Text(text, style=styles.hint)


@pn.component
def DemoSection(title: str, *children: pn.Node) -> pn.Node:
    """A titled card with multiple children, separated by a gap."""
    return Card(Label(title), *children)


@pn.component
def ButtonsRow(*buttons: pn.Node) -> pn.Node:
    """Lay out a horizontal row of buttons with a consistent gap."""
    return pn.Row(*buttons, style=Layout.row)
