"""Demo screen for the ``presentation`` and ``animation`` screen options.

The root Stack (see ``main.py``) registers one extra route per variant in
:data:`PRESENTATION_VARIANTS`, each with a different ``presentation`` or
``animation`` option, so the *native* stack presents them: on iOS a page
sheet, a full-screen cover, a form sheet, and an over-context transparent
modal; Android presents every modal style as a full-screen screen with a
slide-from-bottom transition, and both platforms honor the ``fade`` and
``slide_from_bottom`` animations. Each presented screen shows a stable
marker and a "Dismiss presented" button that pops it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


@dataclass(frozen=True)
class PresentationVariant:
    """One extra root route presented from the demo."""

    route: str
    label: str
    options: pn.ScreenOptions
    component: Callable[[], pn.Element]


def _make_presented(label: str) -> Callable[[], pn.Element]:
    @pn.component
    def Presented() -> pn.Element:
        nav = pn.use_navigation()
        return pn.View(
            pn.Column(
                pn.Text(f"Presented: {label}", style=pn.style(font_size=20, font_weight="700", color="#0F172A")),
                pn.Text(
                    "This screen was pushed on the root stack with a presentation option.",
                    style=pn.style(color="#475569"),
                ),
                pn.Button("Dismiss presented", on_press=nav.go_back),
                style=pn.style(padding=20, spacing=12, background_color="#FFFFFF", border_radius=12),
            ),
            style=pn.style(flex=1, justify_content="center", padding=24),
        )

    return Presented


PRESENTATION_VARIANTS: List[PresentationVariant] = [
    PresentationVariant(
        "presentation_modal", "modal", {"title": "Modal", "presentation": "modal"}, _make_presented("modal")
    ),
    PresentationVariant(
        "presentation_full_screen_modal",
        "full_screen_modal",
        {"title": "Full screen", "presentation": "full_screen_modal"},
        _make_presented("full_screen_modal"),
    ),
    PresentationVariant(
        "presentation_form_sheet",
        "form_sheet",
        {"title": "Form sheet", "presentation": "form_sheet"},
        _make_presented("form_sheet"),
    ),
    PresentationVariant(
        "presentation_transparent_modal",
        "transparent_modal",
        {"title": "Transparent", "presentation": "transparent_modal", "header_shown": False},
        _make_presented("transparent_modal"),
    ),
    PresentationVariant("presentation_fade", "fade", {"title": "Fade", "animation": "fade"}, _make_presented("fade")),
    PresentationVariant(
        "presentation_slide_from_bottom",
        "slide_from_bottom",
        {"title": "Slide up", "animation": "slide_from_bottom", "header_back_title": "Back"},
        _make_presented("slide_from_bottom"),
    ),
]


@pn.component
def PresentationDemo() -> pn.Element:
    """Render one button per presentation / animation variant."""
    nav = pn.use_navigation()
    opened, set_opened = pn.use_state(0)
    last, set_last = pn.use_state("none")

    def open_variant(variant: PresentationVariant) -> Callable[[], None]:
        def _open() -> None:
            set_opened(opened + 1)
            set_last(variant.label)
            nav.push(variant.route)

        return _open

    buttons = [pn.Button(f"Open {variant.label}", on_press=open_variant(variant)) for variant in PRESENTATION_VARIANTS]

    return demo_screen(
        "Presentation",
        "Push root screens with every presentation and animation option.",
        section(
            "Variants",
            result_text("Opened", opened),
            result_text("Last variant", last),
            # One button per line: the long variant names overflow a shared row
            # on phone widths and Maestro can't tap a clipped button.
            pn.Column(*buttons, style=pn.style(spacing=8, align_items="flex_start")),
            hint("Each presented screen shows 'Presented: <variant>' and a dismiss button."),
        ),
    )
