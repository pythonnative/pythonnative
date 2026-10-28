"""Demo screen for [`pn.Store`][pythonnative.Store] and [`pn.use_store`][pythonnative.use_store].

A module-level ``Store[Cart]`` holds a frozen dataclass. Two readouts
subscribe with selectors: one shows the item count and counts its own
renders, the other shows the note. Writing the note doesn't re-render
the count readout, because its selected value didn't change; adding
two items inside ``store.batch()`` re-renders it once. The store is
reset when the demo unmounts so every visit starts empty.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText


@dataclass(frozen=True)
class Cart:
    """The store's value: an immutable snapshot replaced on every write."""

    items: tuple[str, ...] = ()
    note: str = ""


cart = pn.Store(Cart(), name="e2e.cart")
"""App-wide state shared by every component that reads it."""


def add_item() -> None:
    """Append one item."""
    cart.update(lambda state: replace(state, items=(*state.items, f"item {len(state.items) + 1}")))


def add_two() -> None:
    """Append two items with a single notification."""
    with cart.batch():
        add_item()
        add_item()


def set_note(note: str) -> None:
    """Replace the note without touching the items."""
    cart.update(lambda state: replace(state, note=note))


def reset_cart() -> None:
    """Restore the empty cart."""
    cart.set(Cart())


@pn.component
def CartCount() -> pn.Node:
    """Show the item count; re-renders only when the count changes."""
    count = pn.use_store(cart, lambda state: len(state.items))
    renders = pn.use_ref(0)
    renders.current += 1
    return pn.Column(
        ResultText("Items", count),
        ResultText("Count renders", renders.current),
    )


@pn.component
def CartNote() -> pn.Node:
    """Show the note; re-renders only when the note changes."""
    note = pn.use_store(cart, lambda state: state.note)
    return ResultText("Note", note or "(empty)")


@pn.component
def UseStoreDemo() -> pn.Node:
    """Render two selector-scoped readouts of one store and buttons that write it."""
    pn.use_effect(lambda: reset_cart, [])
    return DemoScreen(
        "use_store",
        "Components subscribe to a Store through selectors and re-render only when their slice changes.",
        DemoSection(
            "Cart store",
            CartCount(),
            CartNote(),
            ButtonsRow(
                pn.Button("Add item", on_press=add_item),
                pn.Button("Add two", on_press=add_two),
            ),
            ButtonsRow(
                pn.Button("Set note", on_press=lambda: set_note("hello")),
                pn.Button("Reset store", on_press=reset_cart),
            ),
            Hint("Setting the note leaves 'Count renders' alone; 'Add two' batches into one render."),
        ),
    )
