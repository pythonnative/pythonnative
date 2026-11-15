"""Demo screen for child identity (RFC 0010).

A conditional banner appears above a stateful counter, and a list grows
above a stateful footer. ``None`` keeps its slot and a list is one
group, so neither the counter nor the footer remounts: their counts
survive both changes.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText


@pn.component
def Counter(label: str) -> pn.Node:
    """A counter whose state would reset if it remounted."""
    count, set_count = pn.use_state(0)
    return pn.Column(
        ResultText(label, count),
        pn.Button(f"Bump {label.lower()}", on_press=lambda: set_count(count + 1)),
    )


@pn.component
def ChildIdentityDemo() -> pn.Node:
    """Toggle a sibling and grow a list without remounting the stateful children beside them."""
    banner, set_banner = pn.use_state(False)
    rows, set_rows = pn.use_state(0)
    return DemoScreen(
        "Child identity",
        "A conditional child keeps its slot and a list is one group, so siblings keep their state.",
        DemoSection(
            "Conditional sibling",
            banner and pn.Text("Banner shown"),
            Counter("Counter"),
            pn.Button("Toggle banner", on_press=lambda: set_banner(not banner)),
        ),
        DemoSection(
            "List beside a footer",
            [pn.Text(f"Row {i}", key=str(i)) for i in range(rows)],
            Counter("Footer"),
            pn.Button("Add row", on_press=lambda: set_rows(rows + 1)),
        ),
        Hint("Maestro bumps both counters, toggles the banner, adds rows, and checks the counts survived."),
    )
