"""List tab: virtualized FlatList demo.

500 rows windowed in Python: only the rows near the viewport are
mounted as native views, leading/trailing spacers stand in for the
rest, and the window shifts as the user scrolls.
"""

import pythonnative as pn


@pn.component
def ListScreen() -> pn.Element:
    items = [{"id": i, "title": f"Row {i + 1}", "subtitle": f"Lorem ipsum #{i}"} for i in range(500)]

    def render_row(item: dict, index: int) -> pn.Element:
        return pn.Pressable(
            pn.View(
                pn.Text(item["title"], style={"font_size": 16, "font_weight": "600"}),
                pn.Text(item["subtitle"], style={"font_size": 13, "color": "#6B7280"}),
                style={
                    "padding": 12,
                    "spacing": 4,
                    "background_color": "#FFFFFF",
                    "border_radius": 8,
                },
            ),
            on_press=lambda: print(f"[ListScreen] tapped row {index}"),
        )

    return pn.Column(
        pn.View(
            pn.Text(
                "Virtualized FlatList: 500 rows, windowed in Python",
                style={"font_size": 13, "color": "#6B7280"},
            ),
            style={"padding": 16, "background_color": "#F9FAFB"},
        ),
        pn.FlatList(
            data=items,
            item_height=64,
            separator_height=8,
            render_item=render_row,
            key_extractor=lambda item, _: str(item["id"]),
            style={"flex": 1, "background_color": "#F3F4F6"},
        ),
        style={"flex": 1},
    )
