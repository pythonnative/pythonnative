"""Demo screen for [`pn.use_effect`][pythonnative.use_effect].

Two effects:

- An "on mount" effect that bumps a counter once, then registers a
  cleanup. The cleanup runs when the screen unmounts (i.e. on
  Back), so Maestro can't directly assert it; the mount counter is
  the testable surface.
- A "dependency change" effect that re-runs each time the user
  changes the dependency, so flows can drive it deterministically by
  tapping "Bump dep".
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section


@pn.component
def UseEffectDemo() -> pn.Element:
    """Render effect run counters driven by dependency-array changes."""
    dep, set_dep = pn.use_state(0)
    mount_runs, set_mount_runs = pn.use_state(0)
    dep_runs, set_dep_runs = pn.use_state(0)

    def _on_mount() -> None:
        # ``[]`` dep list -> only runs on mount.
        set_mount_runs(mount_runs + 1)

    pn.use_effect(_on_mount, [])

    def _on_dep_change() -> None:
        set_dep_runs(dep_runs + 1)

    pn.use_effect(_on_dep_change, [dep])

    return demo_screen(
        "use_effect",
        "Two effects: one runs once on mount, one runs on each dep change.",
        section(
            "Effect run counters",
            result_text("Mount runs", mount_runs),
            result_text("Dep runs", dep_runs),
            result_text("Dep value", dep),
            buttons_row(
                pn.Button("Bump dep", on_press=lambda: set_dep(dep + 1)),
            ),
            hint("Tapping 'Bump dep' twice should set 'Dep runs: 3' (1 on mount + 2 bumps)."),
        ),
    )
