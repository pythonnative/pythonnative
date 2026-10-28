"""Demo screen for [`pn.Easing`][pythonnative.Easing].

Runs ``Animated.timing`` with each named curve and a custom
``Easing.bezier(...)`` ([`EasingSpec`][pythonnative.EasingSpec]); the
resulting [`AnimationResult`][pythonnative.AnimationResult] is mirrored
into the status line. A misspelled easing string raises ``ValueError``
instead of silently falling back, which the demo also checks.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_CURVES: list[tuple[str, pn.EasingSpec]] = [
    ("linear", pn.Easing.linear),
    ("ease", pn.Easing.ease),
    ("ease_in", pn.Easing.ease_in),
    ("ease_out", pn.Easing.ease_out),
    ("ease_in_out", pn.Easing.ease_in_out),
    ("quad", pn.Easing.quad),
    ("cubic", pn.Easing.cubic),
    ("bounce", pn.Easing.bounce),
    ("bezier", pn.Easing.bezier(0.42, 0.0, 0.58, 1.0)),
]


def _rejects_unknown_easing() -> bool:
    try:
        pn.Animated.timing(pn.AnimatedValue(0.0), to=1.0, duration=10, easing="ease_in_ot")
    except ValueError:
        return True
    return False


@pn.component
def EasingDemo() -> pn.Node:
    """Slide a box with every Easing curve in turn."""
    tx = pn.use_animated_value(0.0)
    status, set_status = pn.use_state("idle")
    curves_run, set_curves_run = pn.use_state(0)
    last_curve, set_last_curve = pn.use_state("none")

    async def run_all() -> None:
        set_status("running")
        finished = 0
        for name, spec in _CURVES:
            set_last_curve(name)
            result = await pn.Animated.timing(tx, to=120.0, duration=120, easing=spec)
            finished += int(result.finished)
            result = await pn.Animated.timing(tx, to=0.0, duration=60, easing=name if name != "bezier" else spec)
            finished += int(result.finished)
        set_curves_run(len(_CURVES))
        set_status("done" if finished == 2 * len(_CURVES) else "interrupted")

    return DemoScreen(
        "Easing",
        "Animated.timing with every Easing curve, including a bezier.",
        DemoSection(
            "Easing curves",
            ResultText("Status", status),
            ResultText("Curves run", curves_run),
            ResultText("Last curve", last_curve),
            ResultText("Rejects unknown easing", "yes" if _rejects_unknown_easing() else "no"),
            ResultText("Animatable props", len(pn.ANIMATABLE_PROPS)),
            pn.Animated.View(
                pn.Text("easing-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                style={
                    "translate_x": tx,
                    "padding": 16,
                    "background_color": "#8B5CF6",
                    "border_radius": 10,
                    "align_self": "flex_start",
                },
            ),
            ButtonsRow(pn.Button("Run all curves", on_press=run_all)),
            Hint("Maestro taps 'Run all curves' and waits for 'Curves run: 9'."),
        ),
    )
