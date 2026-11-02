"""Demo screen for [`Location`][pythonnative.location.Location].

The simulator and emulator answer with their configured position, or nothing when
none is set, so the flow asserts the outcome was reported rather than where it is.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, ResultText
from pythonnative.location import Location, Position


@pn.component
def LocationDemo() -> pn.Node:
    """Request one fix and show the permission status it reports."""
    status, set_status = pn.use_state("not asked")
    fix, set_fix = pn.use_state("none yet")

    async def check() -> None:
        set_status(await pn.Permissions.check("location_when_in_use"))

    pn.use_effect(check, [])

    async def locate() -> None:
        position: Position | None = await Location.get_current(timeout=5)
        set_fix("no fix" if position is None else f"{position.latitude:.1f}, {position.longitude:.1f}")

    return DemoScreen(
        "Location",
        "Permission status and one position fix.",
        DemoSection(
            "One fix",
            ResultText("Permission known", "yes" if status != "not asked" else "no"),
            ResultText("Facade imported", "yes"),
            ButtonsRow(pn.Button("Locate", on_press=lambda: pn.run_async(locate()))),
            ResultText("Last fix", fix),
        ),
    )
