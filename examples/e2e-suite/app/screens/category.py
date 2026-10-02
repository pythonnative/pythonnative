"""Per-category screen: lists every demo in a category as tappable buttons.

The screen's ``name`` parameter is its route param, so the home screen
opens it with ``nav.navigate(CategoryListScreen(name="Hooks"))``. It
renders a scrollable column of ``"Open: <Title>"`` buttons that push
each demo's component. Maestro flows tap them by exact title; new demos
appear here automatically once they're added to
:data:`app.registry.DEMOS`.
"""

from __future__ import annotations

from functools import partial

import pythonnative as pn
from app.registry import DemoEntry, demos_for_category
from app.theme import AppStyles, Layout


@pn.component
def CategoryListScreen(name: str = "Components") -> pn.Node:
    """Render every demo in the ``name`` category as a button."""
    nav = pn.use_navigation()
    styles = pn.use_styles(AppStyles)
    demos = demos_for_category(name)

    def open_demo(demo: DemoEntry) -> None:
        nav.push(demo.component())

    return pn.ScrollView(
        pn.Column(
            pn.Text(f"Demos in {name}", style=styles.title),
            pn.Text(
                f"{len(demos)} demos in this category. Tap one to exercise the feature.",
                style=styles.hint,
            ),
            *[
                pn.Button(
                    f"Open: {demo.title}",
                    on_press=partial(open_demo, demo),
                    key=demo.id,
                )
                for demo in demos
            ],
            pn.Button("Back to home", on_press=nav.go_back),
            style=Layout.screen,
        )
    )
