"""Typing conformance: components, children, and keys.

Checked by mypy (see tests/test_typing_conformance.py); never imported
or executed. Each line that must be rejected carries a
``# type: ignore[code]``, so with ``warn_unused_ignores`` an API that
stops rejecting the mistake fails the check.
"""

from __future__ import annotations

from typing import Callable

import pythonnative as pn


@pn.component
def Card(title: str, count: int = 0) -> pn.Node:
    return pn.Text(f"{title}: {count}")


@pn.component
def Panel(*children: pn.Node, title: str = "") -> pn.Node:
    return pn.Column(pn.Text(title), *children)


@pn.component
def Toggle(on_change: Callable[[bool], None], value: bool = False) -> pn.Node:
    return pn.Switch(value=value, on_change=on_change)


def accepted(flag: bool, labels: list[str]) -> pn.Node:
    card: pn.Element = Card(title="Hello")
    positional = Card("Hello", 2)
    keyed: pn.Element = Card(title="x").with_key(3)
    column = pn.Column(
        pn.Text("x") if flag else None,
        flag and pn.Text("y"),
        [pn.Text(label).with_key(label) for label in labels],
        (Card(title=label).with_key(label) for label in labels),
        pn.Text("keyed", key="k"),
    )
    panel = Panel(card, positional, keyed, column, title="Panel")
    toggle = Toggle(on_change=lambda value: None)
    return [panel, toggle, None, False]


def no_arguments() -> None:
    return None


def rejected() -> None:
    Card(title=1)  # type: ignore[arg-type]
    Card(key="k", title="x")  # type: ignore[call-arg]
    Card(titel="x")  # type: ignore[call-arg]
    Card()  # type: ignore[call-arg]
    Panel(pn.Text("x"), title=None)  # type: ignore[arg-type]
    Toggle(on_change=no_arguments)  # type: ignore[arg-type]
    pn.Text("x", selectable="yes")  # type: ignore[arg-type]
    pn.Column(pn.Text("x"), 3)  # type: ignore[arg-type]


def returns_a_number() -> pn.Node:
    return 3  # type: ignore[return-value]
