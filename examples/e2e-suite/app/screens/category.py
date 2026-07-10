"""Per-category screen: lists every demo in a category as tappable buttons.

The screen reads its ``name`` route param and renders a scrollable
column of ``"Open: <Title>"`` buttons. Maestro flows tap them by
exact title; new demos appear here automatically once they're added
to :data:`app.registry.DEMOS`.
"""

from __future__ import annotations

import pythonnative as pn
from app.registry import demos_for_category
from app.theme import styles


@pn.component
def CategoryListScreen() -> pn.Element:
    """Render every demo in the route's ``name`` category as a button."""
    nav = pn.use_navigation()
    params = nav.get_params()
    category: str = params.get("name", "Components")
    demos = demos_for_category(category)

    def open_demo(demo_id: str) -> None:
        nav.navigate(demo_id)

    return pn.ScrollView(
        pn.Column(
            pn.Text(f"Demos in {category}", style=styles["title"]),
            pn.Text(
                f"{len(demos)} demos in this category. Tap one to exercise the feature.",
                style=styles["hint"],
            ),
            *[
                pn.Button(
                    f"Open: {demo.title}",
                    on_press=lambda _id=demo.id: open_demo(_id),
                )
                for demo in demos
            ],
            pn.Button("Back to home", on_press=nav.go_back),
            style=styles["screen"],
        )
    )
