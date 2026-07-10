"""Home screen: lists every category as a tappable row.

Each row pushes the ``Category`` route with ``{"name": "<category>"}``
as a route param. The category screen then lists every demo in that
category.

Stable labels used by Maestro:

- ``"E2E Suite home"``: present whenever the home screen is on top
  of the stack. Maestro flows start with
  ``extendedWaitUntil: visible: "E2E Suite home"`` so they wait for
  the app to boot before tapping.
- ``"Open <name>"``: buttons that open each category. Flows tap
  them by name (e.g. ``tapOn: "Open Hooks"``).
"""

from __future__ import annotations

import pythonnative as pn
from app.registry import CATEGORIES, demos_for_category
from app.theme import styles


@pn.component
def HomeScreen() -> pn.Element:
    """Master list of categories.

    Renders one button per category from :data:`app.registry.CATEGORIES`,
    each labelled ``"Open <name>"`` so flows can target it by an exact
    string match without colliding with the category list screen's
    title text. The demo count appears as a separate text line so the
    button label itself is short and stable.
    """
    nav = pn.use_navigation()

    def open_category(name: str) -> None:
        nav.navigate("Category", {"name": name})

    return pn.ScrollView(
        pn.Column(
            pn.Text("E2E Suite home", style=styles["title"]),
            pn.Text(
                "Every category below maps to a folder of demo screens. "
                "Tap a category, then tap a demo to exercise that feature.",
                style=styles["hint"],
            ),
            *[
                pn.Column(
                    pn.Button(
                        f"Open {name}",
                        on_press=lambda _name=name: open_category(_name),
                    ),
                    pn.Text(
                        f"{len(demos_for_category(name))} demos",
                        style=styles["hint"],
                    ),
                    style=pn.style(spacing=4),
                )
                for name in CATEGORIES
            ],
            style=styles["screen"],
        )
    )
