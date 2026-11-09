"""Demo screen for [`pn.with_spring`][pythonnative.with_spring].

One button springs a box's scale with the physical parameters
(``damping`` and ``stiffness``); the other uses ``duration`` with
``damping_ratio``, the critically tuned form that settles on time. Both
are awaited from Python, and the demo shows where the shared value came
to rest.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@pn.component
def WithSpringDemo() -> pn.Node:
    """Spring a box's scale and report where it settles."""
    scale = pn.use_shared_value(0.5)
    status, set_status = pn.use_state("idle")
    rest, set_rest = pn.use_state("0.50")
    grow = pn.use_animated_style(lambda: {"transform": [{"scale": scale.value}]})

    async def spring_to(target: float, *, timed: bool) -> None:
        set_status("running")
        if timed:
            done = await scale.animate(pn.with_spring(target, duration=400, damping_ratio=1.0))
        else:
            done = await scale.animate(pn.with_spring(target, damping=12, stiffness=160))
        set_rest(f"{scale.value:.2f}")
        set_status("done" if done else "interrupted")

    async def run() -> None:
        await spring_to(1.0, timed=False)

    async def run_timed() -> None:
        await spring_to(0.5, timed=True)

    return DemoScreen(
        "with_spring",
        "Spring a shared value with physical or duration-based parameters.",
        DemoSection(
            "Spring demo",
            ResultText("Status", status),
            ResultText("Scale", rest),
            pn.View(
                pn.Text("spring-box label", style=pn.style(color="#FFFFFF", font_weight="700")),
                style=[
                    pn.style(padding=24, background_color="#10B981", border_radius=12, align_self="center"),
                    grow,
                ],
            ),
            ButtonsRow(
                pn.Button("Run spring", on_press=run),
                pn.Button("Run timed spring", on_press=run_timed),
            ),
            Hint("Maestro taps 'Run spring', then 'Run timed spring', and asserts 'Status: done' each time."),
        ),
    )
