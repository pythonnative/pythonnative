"""``pythonnative.purchases``: the fake store, the facade, and the plugin manifest."""

from __future__ import annotations

import json
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, List

import pytest

import pythonnative.purchases as purchases
from pythonnative.native_modules.registry import NativeModuleError, emit, register_python_module
from pythonnative.project.plugins import load_plugin
from pythonnative.purchases import Product, Purchases, Transaction, fake_store
from pythonnative.runtime import drain, run_blocking
from pythonnative.sdk import schema

NATIVE = Path(purchases.__file__).parent / "native"
PRO = Product("pro", "Pro", "Everything", Decimal("4.99"), "USD", "$4.99", "non_consumable")
COINS = Product("coins", "Coins", "100 coins", Decimal("0.99"), "USD", "$0.99", "consumable")


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    register_python_module("Purchases", fake_store)
    fake_store.reset()
    fake_store.set_products([PRO, COINS])
    yield
    fake_store.reset()
    purchases._listeners.clear()


def test_available_follows_the_fake_store() -> None:
    assert run_blocking(Purchases.is_available()) is True
    fake_store.set_available(False)
    assert run_blocking(Purchases.is_available()) is False


def test_products_come_back_typed_and_unknown_ids_drop_out() -> None:
    found = run_blocking(Purchases.products(["pro", "ghost"]))
    assert found == [PRO]
    assert isinstance(found[0].price, Decimal)


def test_a_new_fake_store_sells_nothing() -> None:
    fake_store.reset()
    assert run_blocking(Purchases.products(["pro"])) == []


def test_a_purchase_returns_a_verified_transaction() -> None:
    result = run_blocking(Purchases.purchase("pro"))
    assert result.status == "purchased"
    transaction = result.transaction
    assert transaction is not None
    assert transaction.product_id == "pro"
    assert transaction.verified is True
    assert transaction.revoked is False
    assert transaction.purchase_date.tzinfo is timezone.utc


@pytest.mark.parametrize("status", ["pending", "cancelled"])
def test_pending_and_cancelled_are_outcomes(status: Any) -> None:
    fake_store.set_outcome(status)
    result = run_blocking(Purchases.purchase("pro"))
    assert result.status == status
    assert result.transaction is None


def test_a_set_error_raises_from_purchase() -> None:
    fake_store.set_outcome(NativeModuleError("Purchases", "purchase", "declined", "purchase_failed"))
    with pytest.raises(NativeModuleError) as caught:
        run_blocking(Purchases.purchase("pro"))
    assert caught.value.code == "purchase_failed"


def test_an_unknown_product_raises() -> None:
    with pytest.raises(NativeModuleError) as caught:
        run_blocking(Purchases.purchase("ghost"))
    assert caught.value.code == "unknown_product"


def test_restore_returns_what_is_owned_until_consumed() -> None:
    pro = run_blocking(Purchases.purchase("pro")).transaction
    coins = run_blocking(Purchases.purchase("coins")).transaction
    assert pro is not None and coins is not None
    assert {item.id for item in run_blocking(Purchases.restore())} == {pro.id, coins.id}
    run_blocking(Purchases.finish(pro))
    run_blocking(Purchases.finish(coins))
    assert fake_store.finished == [pro.id, coins.id]
    assert [item.id for item in run_blocking(Purchases.restore())] == [pro.id]
    run_blocking(Purchases.finish(pro, consume=True))
    assert run_blocking(Purchases.restore()) == []


def test_on_update_delivers_until_unsubscribed() -> None:
    seen: List[Transaction] = []
    unsubscribe = Purchases.on_update(seen.append)
    transaction = fake_store.push_update("pro")
    assert seen == [transaction]
    unsubscribe()
    fake_store.push_update("pro")
    assert seen == [transaction]
    unsubscribe()


def test_on_update_accepts_an_async_callback() -> None:
    seen: List[str] = []

    async def record(transaction: Transaction) -> None:
        seen.append(transaction.id)

    Purchases.on_update(record)
    fake_store.push_update("pro")
    assert drain(2.0, until=lambda: bool(seen))


def test_an_update_reports_a_revoked_transaction() -> None:
    seen: List[Transaction] = []
    Purchases.on_update(seen.append)
    emit(
        "Purchases",
        "update",
        {
            "id": "1",
            "product_id": "pro",
            "purchase_date": 1700000000.0,
            "token": "jws",
            "verified": True,
            "revoked": True,
        },
    )
    assert seen[0].revoked is True
    assert seen[0].purchase_date.timestamp() == 1700000000.0


def test_the_first_subscriber_tells_native_to_release_held_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[bool] = []
    monkeypatch.setattr(fake_store, "listen", lambda: calls.append(True))
    monkeypatch.setattr(purchases, "_listening", False)
    Purchases.on_update(lambda _: None)
    Purchases.on_update(lambda _: None)
    assert calls == [True]


def test_the_contract_lists_the_events_and_methods() -> None:
    contract = schema.MODULES["Purchases"]
    assert set(contract.events) == {"update"}
    assert {"is_available", "products", "purchase", "restore", "finish", "listen"} == set(contract.methods)
    for method in ("is_available", "products", "purchase", "restore", "finish"):
        assert contract.methods[method]["async"] is True
    on_disk = json.loads((NATIVE / "schema.json").read_text())["modules"]["Purchases"]
    assert set(on_disk["methods"]) == set(contract.methods)


def test_the_manifest_loads() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "purchases"
    assert plugin.ios_entry == "PurchasesPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.purchases.PurchasesPlugin"
    assert any(path.suffix == ".swift" for path in plugin.ios_sources)
    assert any(path.suffix == ".kt" for path in plugin.android_sources)
    assert any(item.startswith("com.android.billingclient:billing-ktx:") for item in plugin.maven_dependencies)
