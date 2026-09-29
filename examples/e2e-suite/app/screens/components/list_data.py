"""Live keyed edits, retained row state, and native scrolling over 10,000 items."""

from dataclasses import dataclass, replace

import pythonnative as pn
from app.screens.scaffold import buttons_row, demo_screen, result_text, section


@dataclass(frozen=True)
class Item:
    key: str
    title: str


@pn.component
def CounterRow(item: Item) -> pn.Element:
    taps, set_taps = pn.use_state(0)
    return pn.Button(f"{item.title}: {taps}", on_press=lambda: set_taps(taps + 1))


def render_row(item: Item, index: int) -> pn.Element:
    return CounterRow(item)


@pn.component
def ListDataDemo() -> pn.Element:
    data = pn.use_memo(
        lambda: pn.ListData((Item(str(i), f"Live row {i}") for i in range(10_000)), key=lambda item: item.key), []
    )
    controller = pn.use_ref(None)
    viewed, set_viewed = pn.use_state("")

    def viewable(items: list[pn.ViewableItem[Item]]) -> None:
        if items:
            set_viewed(items[0].key)

    def edit() -> None:
        with data.batch():
            data.update("0", replace(data.get("0"), title="Edited row 0"))
            if data[0].key != "new":
                data.insert(0, Item("new", "Inserted row"))
            data.move("0", 1)

    return demo_screen(
        "ListData",
        "Incremental edits preserve visible keyed row state.",
        section(
            "Live data",
            result_text("First visible key", viewed),
            pn.FlatList(
                data=data,
                render_item=render_row,
                item_height=44,
                ref=controller,
                on_viewable_items_changed=viewable,
                style=pn.style(height=280),
            ),
            buttons_row(
                pn.Button("Apply live edits", on_press=edit),
                pn.Button(
                    "Jump near end", on_press=lambda: controller.current.scroll_to_index(len(data) - 8, animated=False)
                ),
            ),
        ),
    )
