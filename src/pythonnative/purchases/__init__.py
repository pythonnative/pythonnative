"""In-app purchases: StoreKit 2 on iOS and Google Play Billing on Android.

Enable it in ``pythonnative.toml``:

```toml
[plugins]
use = ["purchases"]
```

Products are defined in App Store Connect and the Play Console, and their
ids go here. Off device, and in the browser preview, a fake store stands in;
see [`fake_store`][pythonnative.purchases.fake_store].

Example:
    ```python
    from pythonnative.purchases import Purchases

    async def buy_pro() -> None:
        products = await Purchases.products(["pro"])
        result = await Purchases.purchase(products[0].id)
        if result.status == "purchased" and result.transaction.verified:
            unlock_pro()
            await Purchases.finish(result.transaction)
    ```

Always finish a transaction after granting what it paid for. The store keeps
re-delivering an unfinished one, and Play refunds one left unacknowledged for
three days.
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Protocol, Sequence, Union

from ..native_modules.registry import NativeModuleError, emit, native_module, on_event
from ..runtime import invoke
from ..sdk.plugin import plugin_module

__all__ = [
    "FakeStore",
    "Product",
    "ProductKind",
    "PurchaseResult",
    "PurchaseStatus",
    "Purchases",
    "Transaction",
    "fake_store",
]

ProductKind = Literal["consumable", "non_consumable", "subscription", "one_time"]
"""What a product is. Play doesn't record whether an in-app product is consumable, so it reports ``one_time``."""

PurchaseStatus = Literal["purchased", "pending", "cancelled"]
"""How a purchase ended. ``pending`` waits on something outside the app, such as a parent's approval."""


@dataclass(frozen=True)
class Product:
    """Something for sale, as the store describes it.

    Attributes:
        id: The product's identifier.
        title: The localized name.
        description: The localized description.
        price: The price in ``currency``.
        currency: The ISO 4217 code.
        display_price: The price formatted for the user's locale.
        kind: What it is.
    """

    id: str
    title: str
    description: str
    price: Decimal
    currency: str
    display_price: str
    kind: ProductKind


@dataclass(frozen=True)
class Transaction:
    """A completed payment.

    Attributes:
        id: The store's identifier for this transaction.
        product_id: The product it paid for.
        purchase_date: When it happened.
        token: What your server sends to the store to check it: the JWS on
            iOS, and the purchase token on Android.
        verified: On iOS, whether StoreKit's signature check passed. Always
            ``False`` on Android, where the device has no verdict to give:
            check ``token`` with the Google Play Developer API on your server.
        revoked: The store took it back, for a refund for example. Only iOS
            reports this to the device.
    """

    id: str
    product_id: str
    purchase_date: datetime
    token: str
    verified: bool
    revoked: bool = False


@dataclass(frozen=True)
class PurchaseResult:
    """The outcome of [`Purchases.purchase`][pythonnative.purchases.Purchases.purchase].

    Attributes:
        status: How it ended.
        transaction: The transaction, when ``status`` is ``"purchased"``.
    """

    status: PurchaseStatus
    transaction: Optional[Transaction] = None


class _PurchasesService(Protocol):
    async def is_available(self) -> bool: ...

    async def products(self, ids: List[str]) -> List[Dict[str, Any]]: ...

    async def purchase(self, product_id: str) -> Dict[str, Any]: ...

    async def restore(self) -> List[Dict[str, Any]]: ...

    async def finish(self, id: str, token: str, consume: bool = False) -> None: ...

    def listen(self) -> None: ...


class FakeStore:
    """The store off device and in the browser preview. It sells only what it's told to.

    It isn't a simulator of either real store: it answers immediately and
    charges nothing. On a device calls never reach it, so setting it up there
    has no effect. The module's one instance is
    [`fake_store`][pythonnative.purchases.fake_store].

    Example:
        ```python
        from decimal import Decimal
        from pythonnative.purchases import Product, Purchases, fake_store

        fake_store.set_products([
            Product("pro", "Pro", "Everything", Decimal("4.99"), "USD", "$4.99", "non_consumable"),
        ])
        fake_store.set_outcome("cancelled")
        result = await Purchases.purchase("pro")
        assert result.status == "cancelled"
        ```
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Forget all products, outcomes, and transactions."""
        self._available = True
        self._products: Dict[str, Product] = {}
        self._outcome: Union[PurchaseStatus, NativeModuleError] = "purchased"
        self._ids = itertools.count(1)
        self._owned: Dict[str, Dict[str, Any]] = {}
        self.finished: List[str] = []

    def set_available(self, available: bool) -> None:
        """Set what ``is_available`` answers."""
        self._available = available

    def set_products(self, products: Sequence[Product]) -> None:
        """Set what's for sale."""
        self._products = {product.id: product for product in products}

    def set_outcome(self, outcome: Union[PurchaseStatus, NativeModuleError]) -> None:
        """Set how every later purchase ends. An error is raised from ``purchase``."""
        self._outcome = outcome

    def push_update(self, product_id: str) -> Transaction:
        """Complete a purchase outside the app, as an approved pending one would, telling ``on_update``.

        Args:
            product_id: The product it paid for.

        Returns:
            The transaction ``on_update`` receives.
        """
        wire = self._transact(product_id)
        emit("Purchases", "update", wire)
        return _transaction(wire)

    def _transact(self, product_id: str) -> Dict[str, Any]:
        number = next(self._ids)
        id = f"fake-{number}"
        wire = {
            "id": id,
            "product_id": product_id,
            "purchase_date": time.time(),
            "token": f"fake-token-{number}",
            "verified": True,
        }
        self._owned[id] = wire
        return wire

    # The contract.

    def is_available(self) -> bool:
        """Answer what ``set_available`` set."""
        return self._available

    def products(self, ids: List[str]) -> List[Dict[str, Any]]:
        """Return the ones ``set_products`` set."""
        known = [self._products[id] for id in ids if id in self._products]
        return [{**vars(product), "price": str(product.price)} for product in known]

    def purchase(self, product_id: str) -> Dict[str, Any]:
        """End as ``set_outcome`` set."""
        if product_id not in self._products:
            raise NativeModuleError("Purchases", "purchase", f"no product {product_id!r}", "unknown_product")
        if isinstance(self._outcome, NativeModuleError):
            raise self._outcome
        if self._outcome != "purchased":
            return {"status": self._outcome}
        return {"status": "purchased", "transaction": self._transact(product_id)}

    def restore(self) -> List[Dict[str, Any]]:
        """Return every transaction not yet consumed."""
        return list(self._owned.values())

    def finish(self, id: str, token: str, consume: bool = False) -> None:
        """Record the id in ``finished``, and consume it if it should be."""
        del token
        self.finished.append(id)
        product = self._products.get(self._owned[id]["product_id"]) if id in self._owned else None
        if consume or (product is not None and product.kind == "consumable"):
            self._owned.pop(id, None)

    def listen(self) -> None:
        """Do nothing: updates go straight to listeners."""


fake_store = FakeStore()
"""The fake store in use off device."""

plugin_module(
    "Purchases",
    _PurchasesService,
    plugin="purchases",
    events={"update": Dict[str, Any]},
    fallback=fake_store,
)


def _transaction(wire: Mapping[str, Any]) -> Transaction:
    return Transaction(
        id=str(wire["id"]),
        product_id=str(wire["product_id"]),
        purchase_date=datetime.fromtimestamp(float(wire["purchase_date"]), tz=timezone.utc),
        token=str(wire["token"]),
        verified=bool(wire["verified"]),
        revoked=bool(wire.get("revoked", False)),
    )


def _product(wire: Mapping[str, Any]) -> Product:
    return Product(
        id=str(wire["id"]),
        title=str(wire["title"]),
        description=str(wire["description"]),
        price=Decimal(str(wire["price"])),
        currency=str(wire["currency"]),
        display_price=str(wire["display_price"]),
        kind=wire["kind"],
    )


_listeners: List[Callable[[Transaction], Any]] = []
_listeners_lock = threading.Lock()
_listening = False


def _on_update(payload: Mapping[str, Any]) -> None:
    transaction = _transaction(payload)
    with _listeners_lock:
        listeners = list(_listeners)
    for listener in listeners:
        invoke(listener, transaction)


on_event("Purchases", "update", _on_update)


class Purchases:
    """The platform's store.

    Raises:
        NativeModuleError: If the store fails, or with the code
            ``plugin_not_enabled`` when ``purchases`` isn't in the build, or
            ``unsupported`` below iOS 15, which StoreKit 2 needs.
    """

    @staticmethod
    async def is_available() -> bool:
        """Whether this device can buy anything right now.

        Returns:
            ``False`` when purchases are restricted, the store isn't there
            (an emulator without Google Play), or iOS is older than 15.
        """
        return bool(await native_module("Purchases").call_async("is_available"))

    @staticmethod
    async def products(ids: Sequence[str]) -> List[Product]:
        """Look up products by id.

        Args:
            ids: The products' identifiers.

        Returns:
            The ones the store knows. An id it doesn't know is left out.
        """
        rows = await native_module("Purchases").call_async("products", ids=list(ids))
        return [_product(row) for row in rows]

    @staticmethod
    async def purchase(product_id: str) -> PurchaseResult:
        """Show the store's purchase sheet and wait for the user.

        A user who already owns the product gets a ``purchased`` result with
        the existing transaction. Subscriptions buy the product's first offer
        on Android.

        Args:
            product_id: The product to buy.

        Returns:
            The outcome. ``cancelled`` and ``pending`` are outcomes, not
            errors. A pending purchase later arrives through
            [`on_update`][pythonnative.purchases.Purchases.on_update].

        Raises:
            NativeModuleError: With the code ``unknown_product``, or
                ``purchase_failed`` when the store refuses.
        """
        result = await native_module("Purchases").call_async("purchase", product_id=product_id)
        wire = result.get("transaction")
        return PurchaseResult(result["status"], _transaction(wire) if wire else None)

    @staticmethod
    async def restore() -> List[Transaction]:
        """Sync with the store and return what the user currently owns.

        On iOS this can prompt the user to sign in, so call it from a
        "Restore purchases" button. Finished consumables aren't included.
        """
        rows = await native_module("Purchases").call_async("restore")
        return [_transaction(row) for row in rows]

    @staticmethod
    async def finish(transaction: Transaction, *, consume: bool = False) -> None:
        """Tell the store the app has delivered what a transaction paid for.

        Args:
            transaction: The transaction.
            consume: On Android, consume the purchase so it can be bought
                again. Play can't tell which products are consumable, so this
                is how you say so. iOS knows from App Store Connect and
                ignores it.
        """
        await native_module("Purchases").call_async(
            "finish", id=transaction.id, token=transaction.token, consume=consume
        )

    @staticmethod
    def on_update(callback: Callable[[Transaction], Any]) -> Callable[[], None]:
        """Call ``callback`` for each transaction that didn't come from a ``purchase`` call.

        This covers pending purchases completing, purchases made outside the
        app, refunds on iOS (``revoked``), and whatever a previous launch left
        unfinished. Subscribe early. The platform holds these for the first
        subscriber, so nothing is lost before then.

        Args:
            callback: Receives a
                [`Transaction`][pythonnative.purchases.Transaction]. It may be async.

        Returns:
            A function that unsubscribes.
        """
        global _listening
        with _listeners_lock:
            _listeners.append(callback)
            first = not _listening
            _listening = True
        if first:
            native_module("Purchases").call("listen")

        def unsubscribe() -> None:
            with _listeners_lock:
                if callback in _listeners:
                    _listeners.remove(callback)

        return unsubscribe
