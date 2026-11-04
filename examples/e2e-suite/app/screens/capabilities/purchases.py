"""Demo screen for [`pythonnative.purchases`][pythonnative.purchases].

A simulator has no real store to sell from, so this looks a product up and shows
what the store said. In the browser preview and in tests the fake store answers,
so the whole purchase flow runs there. Setting up the fake store on a device does
nothing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.screens.scaffold import DemoScreen, DemoSection, Hint, ResultText

import pythonnative as pn
from pythonnative.native_modules.registry import NativeModuleError
from pythonnative.purchases import Product, Purchases, fake_store

fake_store.set_products([Product("e2e_pro", "Pro", "Everything", Decimal("4.99"), "USD", "$4.99", "non_consumable")])


@pn.component
def PurchasesDemo() -> pn.Node:
    """Render store availability, a product lookup, and a purchase."""
    available, set_available = pn.use_state("checking")
    products, set_products = pn.use_state("checking")
    finished, set_finished = pn.use_state("no")
    price, set_price = pn.use_state("none")
    outcome, set_outcome = pn.use_state("none")
    updates, set_updates = pn.use_state(0)

    def subscribe() -> Any:
        return Purchases.on_update(lambda _: set_updates(lambda n: n + 1))

    pn.use_effect(subscribe, [])

    async def look_up() -> None:
        set_available("yes" if await Purchases.is_available() else "no")
        try:
            found = await Purchases.products(["e2e_pro"])
            set_products(str(len(found)))
            set_price(found[0].display_price if found else "none")
        except NativeModuleError as error:
            set_products(error.code or "failed")
        set_finished("yes")

    pn.use_effect(look_up, [])

    async def buy() -> None:
        try:
            result = await Purchases.purchase("e2e_pro")
            set_outcome(result.status)
            if result.transaction is not None:
                await Purchases.finish(result.transaction)
        except NativeModuleError as error:
            set_outcome(error.code or "failed")

    return DemoScreen(
        "Purchases",
        "Purchases.is_available, products, purchase, finish, and on_update.",
        DemoSection(
            "Store",
            ResultText("Available", available),
            ResultText("Products", products),
            ResultText("Price", price),
            ResultText("Lookup finished", finished),
            ResultText("Updates", updates),
            Hint("A simulator has no products. Android without Google Play reports unavailable."),
        ),
        DemoSection(
            "Purchase",
            ResultText("Outcome", outcome),
            pn.Button("Buy e2e_pro", on_press=buy),
        ),
    )
