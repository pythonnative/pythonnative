"""The one-time Pro unlock, which lifts the limit on attachments.

The store can't always be asked. It's unavailable in a simulator, a sideloaded
build, or a plane, so what a person has bought is remembered in the settings table
and the store is only asked to confirm it. Every path through here ends in a
[`ProState`][app.models.ProState] that the screen can explain.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

import pythonnative as pn
from pythonnative.native_modules import NativeModuleError
from pythonnative.purchases import Purchases, Transaction

from .journal import Journal, journal

PRODUCT_ID = "dev.pythonnative.fieldnotes.pro"
"""The non-consumable product in App Store Connect and the Play Console."""


class ProUnlock:
    """Talks to the store and keeps the store's answer in the journal.

    Args:
        journal: Where the state and the unlock itself are kept.
    """

    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    def _publish(self, **changes: object) -> None:
        self.journal.publish(pro=replace(self.journal.snapshot.pro, **changes))  # type: ignore[arg-type]

    async def refresh(self) -> None:
        """Ask whether the unlock is on sale here, and for how much."""
        self._publish(phase="checking", message="", busy=False)
        try:
            if not await Purchases.is_available():
                self._publish(
                    phase="unavailable",
                    message="The store isn't available on this device, so Pro can't be bought here right now.",
                )
                return
            products = await Purchases.products([PRODUCT_ID])
        except NativeModuleError as error:
            self._publish(phase="unavailable", message=_store_trouble(error))
            return
        if not products:
            self._publish(phase="no_product", message="Pro isn't on sale in this store yet.")
            return
        self._publish(phase="ready", display_price=products[0].display_price)

    async def buy(self) -> None:
        """Run the store's purchase flow and deliver the unlock if it completes."""
        self._publish(busy=True, message="")
        try:
            result = await Purchases.purchase(PRODUCT_ID)
        except NativeModuleError as error:
            self._publish(busy=False, message=_store_trouble(error))
            return
        if result.status == "purchased" and result.transaction is not None:
            await self._deliver(result.transaction)
            self._publish(busy=False, message="Thank you. Attachments are now unlimited.")
        elif result.status == "pending":
            self._publish(busy=False, message="The purchase is waiting for approval. Pro unlocks once it's approved.")
        else:
            self._publish(busy=False, message="The purchase was canceled. You haven't been charged.")

    async def restore(self) -> None:
        """Ask the store what this account owns, for a new device or a reinstall."""
        self._publish(busy=True, message="")
        try:
            owned = await Purchases.restore()
        except NativeModuleError as error:
            self._publish(busy=False, message=_store_trouble(error))
            return
        matching = [transaction for transaction in owned if transaction.product_id == PRODUCT_ID]
        for transaction in matching:
            await self._deliver(transaction)
        self._publish(busy=False, message="Pro restored." if matching else "No earlier purchase of Pro was found.")

    def listen(self) -> Callable[[], None]:
        """Hear about purchases that finish outside a ``buy`` call, such as a parent's approval.

        Returns:
            A function that stops listening. If the capability's missing from the
            build, this listens to nothing and the screen reports that from
            ``refresh``.
        """
        try:
            return Purchases.on_update(self._on_update)
        except NativeModuleError as error:
            self._publish(phase="unavailable", message=_store_trouble(error))
            return lambda: None

    def _on_update(self, transaction: Transaction) -> None:
        if transaction.product_id == PRODUCT_ID:
            pn.run_async(self._deliver(transaction))

    async def _deliver(self, transaction: Transaction) -> None:
        """Record what a transaction means, then tell the store it was delivered."""
        await self.journal.update_settings(pro_owned=not transaction.revoked)
        if not transaction.revoked:
            await Purchases.finish(transaction)


def _store_trouble(error: NativeModuleError) -> str:
    messages = {
        "unsupported": "In-app purchases need iOS 15 or later.",
        "unavailable": "Couldn't reach the store. Check your connection and try again.",
        "unknown_product": "Pro isn't on sale in this store yet.",
        "plugin_not_enabled": "This build doesn't include in-app purchases.",
    }
    return messages.get(error.code or "", f"The store reported a problem: {error}")


pro = ProUnlock(journal)
"""The one unlock the settings screen and ``App`` share."""
