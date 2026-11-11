"""Demo screen for ``interpolate`` and ``interpolate_color`` in an animated style.

See [`pn.interpolate`][pythonnative.interpolate] and
[`pn.interpolate_color`][pythonnative.interpolate_color].

One shared value runs from 0 to 1. An animated style maps it, on the UI
thread, to a slide, a color blend, a corner radius, and a clamped
opacity. A [`use_derived_value`][pythonnative.use_derived_value] computes
the same color blend in the core, and after the run Python compares it
with ``pn.interpolate_color`` evaluated in Python: the helpers are shared,
so the two must agree. The extrapolation lines are computed in Python.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_COLORS = ("#EF4444", "#F59E0B", "#22C55E")
_STOPS = (0.0, 0.5, 1.0)
_TRAVEL = 160.0


@pn.component
def InterpolateDemo() -> pn.Node:
    """Map one shared value onto position, color, radius, and opacity."""
    progress = pn.use_shared_value(0.0)
    blended = pn.use_derived_value(lambda: pn.interpolate_color(progress.value, _STOPS, _COLORS))
    status, set_status = pn.use_state("idle")
    end_color, set_end_color = pn.use_state("none")
    styled = pn.use_animated_style(
        lambda: {
            "transform": [{"translate_x": pn.interpolate(progress.value, (0, 1), (0, _TRAVEL))}],
            "background_color": pn.interpolate_color(progress.value, _STOPS, _COLORS),
            "border_radius": pn.interpolate(progress.value, (0, 1), (0, 28)),
            "opacity": pn.clamp(0.4 + progress.value, 0, 1),
        }
    )

    async def run() -> None:
        set_status("running")
        done = await progress.animate(pn.with_timing(1.0, duration=400))
        set_end_color(blended.value)
        set_status("done" if done else "interrupted")

    async def reset() -> None:
        await progress.animate(pn.with_timing(0.0, duration=200))
        set_end_color("none")
        set_status("idle")

    expected = pn.interpolate_color(1.0, _STOPS, _COLORS)
    return DemoScreen(
        "Interpolate",
        "interpolate and interpolate_color in an animated style.",
        DemoSection(
            "Interpolate demo",
            ResultText("Status", status),
            ResultText("End color", end_color),
            ResultText("Colors match", "yes" if end_color == expected else "no"),
            ResultText("Midpoint color", pn.interpolate_color(0.5, _STOPS, _COLORS)),
            ResultText("Clamped past the end", f"{pn.interpolate(2.0, (0, 1), (0, _TRAVEL), 'clamp'):.0f}"),
            ResultText("Extended past the end", f"{pn.interpolate(2.0, (0, 1), (0, _TRAVEL)):.0f}"),
            pn.View(
                pn.Text("interp-box", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=[pn.style(padding=16, background_color=_COLORS[0], align_self="flex_start"), styled],
            ),
            ButtonsRow(
                pn.Button("Run interpolate", on_press=run),
                pn.Button("Reset interpolate", on_press=reset),
            ),
            Hint("Maestro runs the animation and asserts 'Status: done' and 'Colors match: yes'."),
        ),
    )
