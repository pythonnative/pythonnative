"""Typing conformance: typed screens and navigation (checked by mypy, never executed)."""

from __future__ import annotations

import pythonnative as pn


@pn.component
def HomeScreen() -> pn.Node:
    nav = pn.use_navigation()
    nav.push(ItemScreen(id=42))
    nav.navigate(ItemScreen(id=1, tab="reviews"))
    nav.push(ItemScreen(id="x"))  # type: ignore[arg-type]
    nav.push(ItemScreen(identifier=1))  # type: ignore[call-arg]
    nav.push("ItemScreen")  # type: ignore[arg-type]
    return pn.Text("home")


@pn.component
def ItemScreen(id: int, tab: str = "details") -> pn.Node:
    nav = pn.use_navigation()
    pn.use_screen_options(title=f"Item {id}")
    pn.use_screen_options(titel="x")  # type: ignore[call-arg]
    nav.pop_to(HomeScreen)
    nav.replace(ItemScreen(id=id + 1))
    nav.reset(HomeScreen(), ItemScreen(id=1))
    can: bool = nav.can_go_back()
    return pn.Text(f"{id} {tab} {can}")


Root = pn.StackNavigator(
    pn.Screen(HomeScreen, title="Home"),
    pn.Screen(ItemScreen, path="items/{id}", header_large_title=True),
    initial=HomeScreen,
)

pn.Screen(HomeScreen, titel="Home")  # type: ignore[call-arg]
pn.StackNavigator(HomeScreen, initial="HomeScreen")  # type: ignore[arg-type]

ref = pn.NavigationRef()
app: pn.Element = pn.NavigationContainer(Root, link_prefixes=["myapp://"], ref=ref)
