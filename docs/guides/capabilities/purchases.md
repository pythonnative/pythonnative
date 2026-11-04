# Purchases

`pythonnative.purchases` sells in-app products through StoreKit 2 on iOS and Google Play
Billing on Android. Off device, and in the browser preview, a fake store stands in, so the same
code runs in tests.

## Setup

```toml
[plugins]
use = ["purchases"]
```

There's no permission to declare. You define products in App Store Connect and the Play Console,
and refer to them here by ID. StoreKit 2 needs iOS 15: below that, `is_available` returns `False`
and everything else raises `NativeModuleError` with the code `unsupported`. The app's deployment
target can stay at 13.

## Selling something

```python
from pythonnative.purchases import Purchases

products = await Purchases.products(["pro"])
result = await Purchases.purchase(products[0].id)
if result.status == "purchased":
    unlock_pro()
    await Purchases.finish(result.transaction)
```

| Call | Returns |
| --- | --- |
| `await Purchases.is_available()` | Whether the device can buy anything now |
| `await Purchases.products(ids)` | A list of [`Product`][pythonnative.purchases.Product]. An ID the store doesn't know is left out |
| `await Purchases.purchase(product_id)` | A [`PurchaseResult`][pythonnative.purchases.PurchaseResult] |
| `await Purchases.restore()` | A list of [`Transaction`][pythonnative.purchases.Transaction]: what the user owns now |
| `await Purchases.finish(transaction, consume=False)` | Nothing. Tells the store the goods were delivered |
| `Purchases.on_update(callback)` | A function that unsubscribes |

A purchase's `status` is `purchased`, `pending`, or `cancelled`. All three are outcomes and return
normally. `pending` waits on something outside the app, such as a parent's approval, and the
transaction arrives later through `on_update`. A real failure raises `NativeModuleError`:

| Code | When |
| --- | --- |
| `unknown_product` | The store doesn't know that ID |
| `purchase_failed` | The store refused, or another purchase is in progress on Android |
| `restore_failed` | iOS only: `AppStore.sync` failed |
| `unavailable` | Android only: no connection to Google Play after retrying |
| `store_error` | Android only: a query failed |
| `unsupported` | iOS below 15 |

**Always finish a transaction after delivering what it paid for.** Until you do, the store delivers
it again on every launch. Play goes further and refunds a purchase left unacknowledged for three
days.

## Hearing about purchases later

```python
def on_update(transaction: Transaction) -> None:
    if transaction.revoked:
        lock_pro()
    else:
        unlock_pro()
        pn.run_async(Purchases.finish(transaction))


Purchases.on_update(on_update)
```

`on_update` covers what didn't come from a `purchase` call: a pending purchase completing, a purchase
made outside the app, and a transaction a previous launch left unfinished. Native holds these for
the first subscriber, so subscribe early but don't worry about missing one.

## Platform differences

| | iOS | Android |
| --- | --- | --- |
| `Product.kind` | `consumable`, `non_consumable`, or `subscription` | `one_time` or `subscription`. Play doesn't record whether a product is consumable |
| `Transaction.token` | The signed JWS | The purchase token |
| `Transaction.verified` | Whether StoreKit's signature check passed | Always `False`. The device has no verdict to give, so check `token` on your server with the Google Play Developer API |
| `Transaction.revoked` | `True` after a refund | Always `False`. Play reports refunds to your server, not the device |
| `finish` | Finishes the transaction. Ignores `consume` | Acknowledges, or consumes with `consume=True` so the product can be bought again |
| Consumables in `restore` | Finished ones are gone | Consumed ones are gone |
| Subscriptions | The product's plan | The product's first offer, priced at its last phase |
| `restore` | Can prompt the user to sign in, so call it from a button | Silent |

For anything worth protecting, check `token` on your server on both platforms.

## Testing with the fake store

Off device, [`fake_store`][pythonnative.purchases.fake_store] answers every call. It isn't a simulator
of either real store: it answers immediately, charges nothing, and sells only what you tell it to.
On a device, calls never reach it, so setting it up there does nothing. Like Google Play, it consumes a
purchase only when `finish` passes `consume=True`, so a consumable your tests can buy twice can be bought
twice on both stores.

```python
from decimal import Decimal
from pythonnative.purchases import Product, Purchases, fake_store

fake_store.reset()
fake_store.set_products([
    Product("pro", "Pro", "Everything", Decimal("4.99"), "USD", "$4.99", "non_consumable"),
])

fake_store.set_outcome("cancelled")
assert (await Purchases.purchase("pro")).status == "cancelled"

fake_store.set_outcome("purchased")
transaction = (await Purchases.purchase("pro")).transaction
await Purchases.finish(transaction)
assert fake_store.finished == [transaction.id]

fake_store.push_update("pro")   # What on_update hears when a pending purchase completes.
```

`set_outcome` also takes a `NativeModuleError` to raise, and `set_available` sets what `is_available`
answers.

## Testing with StoreKit's local configuration

Xcode can serve products from a `.storekit` file instead of the App Store. There are two ways to turn
that on, and `pn run` uses neither:

- In Xcode, set **Product > Scheme > Edit Scheme > Run > Options > StoreKit Configuration**, and run
  from Xcode. The setting applies only to Xcode's own launch. An app started by `pn run` or
  `simctl launch` doesn't get it.
- In an XCTest, create an `SKTestSession` from the file, with `disableDialogs` set to skip the sheets.

Without either, a simulator finds no products, and `restore` shows a sign-in sheet that waits until
someone answers it.

## What has been verified

- **iOS simulator, against an `SKTestSession` from a `.storekit` file**, created at launch by a throwaway
  plugin that loaded Xcode's StoreKitTest into the app, with dialogs off: `is_available`,
  `products` for a non-consumable, a consumable, and a subscription, with typed prices. `purchase` of each,
  returning a signed transaction with `verified=True`. `finish`. `restore`, which left out the finished consumable.
  A `pending` result with Ask to Buy on. `on_update` for a purchase the session made itself, including one made
  before the first subscriber, which waited for it.
- **Android emulator:** the plugin compiles against Play Billing and reaches Google Play's service, with
  its connection retry. That emulator answers "Billing service unavailable", so `is_available` is `False`
  and the rest raises `unavailable`.
- **Not verified:** the iOS purchase sheet and a user's cancel, since test sessions skip dialogs. StoreKit replaying
  an unfinished transaction at the next launch, which a relaunched test session didn't do. A real App Store sandbox
  purchase. **Any Play purchase:** the flow can't complete on an emulator or without a
  Play-signed build uploaded to a test track, so `products`, `purchase`, `finish`, and `restore` have never
  returned a real answer on Android. Try them on an internal test track before you ship.
