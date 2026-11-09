"""Demo screen for [`pn.Easing`][pythonnative.Easing] with ``with_timing``.

Runs an awaited ``with_timing`` with each named curve, a
``Easing.bezier(...)``, and a sampled ``Easing.custom(fn)``, counting the
animations that report they finished. A misspelled curve name raises
``ValueError`` instead of silently falling back, which the demo also
checks.
"""

from __future__ import annotations

from typing import List, Tuple

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText
from pythonnative.motion import EasingSpec

_CURVES: List[Tuple[str, EasingSpec]] = [
    ("linear", pn.Easing.linear),
    ("ease", pn.Easing.ease),
    ("ease_in", pn.Easing.ease_in),
    ("ease_out", pn.Easing.ease_out),
    ("ease_in_out", pn.Easing.ease_in_out),
    ("quad", pn.Easing.quad),
    ("cubic", pn.Easing.cubic),
    ("bounce", pn.Easing.bounce),
    ("bezier", pn.Easing.bezier(0.42, 0.0, 0.58, 1.0)),
    ("custom", pn.Easing.custom(lambda t: t * t * (3 - 2 * t))),
]


def _rejects_unknown_easing() -> bool:
    try:
        EasingSpec("ease_in_ot")
    except ValueError:
        return True
    return False


@pn.component
def EasingDemo() -> pn.Node:
    """Slide a box with every Easing curve in turn."""
    tx = pn.use_shared_value(0.0)
    status, set_status = pn.use_state("idle")
    curves_run, set_curves_run = pn.use_state(0)
    last_curve, set_last_curve = pn.use_state("none")
    slide = pn.use_animated_style(lambda: {"transform": [{"translate_x": tx.value}]})

    async def run_all() -> None:
        set_status("running")
        finished = 0
        for name, spec in _CURVES:
            set_last_curve(name)
            finished += int(await tx.animate(pn.with_timing(120.0, duration=120, easing=spec)))
            # Named curves also go by their string name.
            back = spec if name in ("bezier", "custom") else name
            finished += int(await tx.animate(pn.with_timing(0.0, duration=60, easing=back)))
        set_curves_run(len(_CURVES))
        set_status("done" if finished == 2 * len(_CURVES) else "interrupted")

    return DemoScreen(
        "Easing",
        "with_timing along every Easing curve, a bezier, and a sampled custom curve.",
        DemoSection(
            "Easing curves",
            ResultText("Status", status),
            ResultText("Curves run", curves_run),
            ResultText("Last curve", last_curve),
            ResultText("Rejects unknown easing", "yes" if _rejects_unknown_easing() else "no"),
            pn.View(
                pn.Text("easing-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=[
                    pn.style(padding=16, background_color="#8B5CF6", border_radius=10, align_self="flex_start"),
                    slide,
                ],
            ),
            ButtonsRow(pn.Button("Run all curves", on_press=run_all)),
            Hint(f"Maestro taps 'Run all curves' and waits for 'Curves run: {len(_CURVES)}'."),
        ),
    )
