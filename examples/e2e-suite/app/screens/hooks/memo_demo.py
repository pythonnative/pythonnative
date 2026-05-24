"""Demo screen for [`pn.memo`][pythonnative.memo].

Two children are wrapped in ``@pn.memo``. They count their own renders
in module-level refs. The parent has a state that flips on tap. The
memoized children should NOT re-render when the parent state changes,
unless their own props change.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, hint, result_text, section

_render_counts = {"a": 0, "b": 0}


@pn.memo
@pn.component
def _MemoA() -> pn.Element:
    _render_counts["a"] += 1
    return pn.Text(f"MemoA render count: {_render_counts['a']}", style=pn.style(font_weight="600"))


@pn.memo
@pn.component
def _MemoB(label: str = "x") -> pn.Element:
    _render_counts["b"] += 1
    return pn.Text(
        f"MemoB label={label} render count: {_render_counts['b']}",
        style=pn.style(font_weight="600"),
    )


@pn.component
def MemoDemo() -> pn.Element:
    """Render two memoized children and a parent counter that should not re-render them."""
    parent_count, set_parent_count = pn.use_state(0)
    b_label, set_b_label = pn.use_state("x")

    return demo_screen(
        "memo",
        "Memoized children stay still when parent state changes.",
        section(
            "Memo identity",
            result_text("Parent renders", parent_count),
            _MemoA(),
            _MemoB(label=b_label),
            buttons_row(
                pn.Button("Bump parent", on_click=lambda: set_parent_count(parent_count + 1)),
                pn.Button(
                    "Toggle B label",
                    on_click=lambda: set_b_label("y" if b_label == "x" else "x"),
                ),
            ),
            hint("Bumping parent should NOT bump MemoA's count. " "Toggling B label DOES bump MemoB's count."),
        ),
    )
