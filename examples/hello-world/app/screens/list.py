"""List tab: virtualized FlatList demo.

500 rows windowed in Python: only the rows near the viewport are
mounted as native views, leading/trailing spacers stand in for the
rest, and the window shifts as the user scrolls.
"""

from dataclasses import dataclass

import pythonnative as pn
from app.theme import AppStyles


@dataclass(frozen=True)
class Item:
    id: int
    title: str
    subtitle: str


ITEMS = [Item(i, f"Row {i + 1}", f"Lorem ipsum #{i}") for i in range(500)]


class ListStyles:
    def __init__(self, theme: pn.Theme) -> None:
        colors = theme.colors
        self.row = pn.style(padding=12, gap=4, background_color=colors.surface, border_radius=theme.radii.md)
        self.title = pn.style(font_size=16, font_weight="600", color=colors.text)
        self.subtitle = pn.style(font_size=13, color=colors.text_secondary)
        self.header = pn.style(padding=16, background_color=colors.surface)
        self.list = pn.style(flex=1, padding_horizontal=theme.spacing.sm, background_color=colors.background)


@pn.component
def ItemRow(item: Item) -> pn.Node:
    styles = pn.use_styles(ListStyles)
    return pn.Pressable(
        pn.View(
            pn.Text(item.title, style=styles.title),
            pn.Text(item.subtitle, style=styles.subtitle),
            style=styles.row,
        ),
        on_press=lambda: print(f"[ListScreen] tapped row {item.id}"),
    )


# Module-level, so FlatList sees the same functions on every render and
# keeps the rows it already built.
def item_key(item: Item, index: int) -> str:
    return str(item.id)


def render_item(item: Item, index: int) -> pn.Element:
    return ItemRow(item)


@pn.component
def ListScreen() -> pn.Node:
    app_styles = pn.use_styles(AppStyles)
    styles = pn.use_styles(ListStyles)
    return pn.Column(
        pn.View(
            pn.Text("Virtualized FlatList: 500 rows, windowed in Python", style=app_styles.hint),
            style=styles.header,
        ),
        pn.FlatList(
            data=ITEMS,
            item_height=64,
            separator_height=8,
            render_item=render_item,
            key_extractor=item_key,
            style=styles.list,
        ),
        style={"flex": 1},
    )
