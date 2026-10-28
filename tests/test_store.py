"""Tests for pn.Store, pn.use_store, bound-method equality, and use_persisted_state."""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

import pytest

import pythonnative as pn
from pythonnative import equality
from pythonnative.hooks import StateSetter
from pythonnative.native_modules.registry import native_module
from pythonnative.runtime import drain, run_blocking
from pythonnative.storage import AsyncStorage
from pythonnative.testing import render


@dataclass(frozen=True)
class Counter:
    count: int = 0
    label: str = "a"


class CountingStore(pn.Store[Counter]):
    """A store that records how often it's subscribed to and how many listeners are live."""

    def __init__(self, initial: Counter) -> None:
        super().__init__(initial)
        self.subscribe_calls = 0
        self.live = 0

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self.subscribe_calls += 1
        self.live += 1
        remove = super().subscribe(listener)

        def unsubscribe() -> None:
            self.live -= 1
            remove()

        return unsubscribe


# ======================================================================
# Store
# ======================================================================


def test_set_and_update_replace_the_value_and_notify() -> None:
    store = pn.Store(Counter())
    calls: List[int] = []
    store.subscribe(lambda: calls.append(store.get().count))

    store.set(Counter(count=1))
    store.update(lambda state: replace(state, count=state.count + 1))

    assert store.get() == Counter(count=2)
    assert calls == [1, 2]


def test_setting_an_equal_value_does_not_notify() -> None:
    store = pn.Store(Counter())
    calls: List[None] = []
    store.subscribe(lambda: calls.append(None))

    store.set(Counter())
    store.update(lambda state: state)
    store.update(lambda state: replace(state))

    assert calls == []


def test_batch_coalesces_writes_into_one_notification() -> None:
    store = pn.Store(0)
    seen: List[int] = []
    store.subscribe(lambda: seen.append(store.get()))

    with store.batch():
        store.set(1)
        store.update(lambda n: n + 1)
        store.set(3)
        assert store.get() == 3  # writes apply immediately
        assert seen == []

    assert seen == [3]


def test_nested_batches_notify_once_when_the_outermost_exits() -> None:
    store = pn.Store(0)
    seen: List[int] = []
    store.subscribe(lambda: seen.append(store.get()))

    with store.batch():
        store.set(1)
        with store.batch():
            store.set(2)
        assert seen == []
        store.set(3)

    assert seen == [3]


def test_batch_without_a_change_does_not_notify() -> None:
    store = pn.Store(5)
    seen: List[int] = []
    store.subscribe(lambda: seen.append(store.get()))

    with store.batch():
        store.set(5)

    assert seen == []


def test_batch_notifies_even_when_the_block_raises() -> None:
    store = pn.Store(0)
    seen: List[int] = []
    store.subscribe(lambda: seen.append(store.get()))

    with pytest.raises(RuntimeError):
        with store.batch():
            store.set(1)
            raise RuntimeError("boom")

    assert seen == [1]


def test_subscribe_returns_an_idempotent_unsubscribe() -> None:
    store = pn.Store(0)
    calls: List[str] = []
    unsubscribe_a = store.subscribe(lambda: calls.append("a"))
    store.subscribe(lambda: calls.append("b"))

    store.set(1)
    unsubscribe_a()
    unsubscribe_a()
    store.set(2)

    assert calls == ["a", "b", "b"]


def test_store_repr_includes_name() -> None:
    assert repr(pn.Store(1, name="count")) == "<Store count 1>"
    assert repr(pn.Store(1)) == "<Store 1>"


# ======================================================================
# use_store
# ======================================================================


def test_use_store_without_selector_returns_the_value() -> None:
    store = pn.Store(Counter(count=3))

    @pn.component
    def Show() -> pn.Node:
        return pn.Text(str(pn.use_store(store).count))

    result = render(Show())
    assert result.text() == ["3"]
    result.act(lambda: store.set(Counter(count=4)))
    assert result.text() == ["4"]


def test_use_store_selector_rerenders_only_when_the_selection_changes() -> None:
    store = pn.Store(Counter())
    renders: List[int] = []

    @pn.component
    def Count() -> pn.Node:
        count = pn.use_store(store, lambda state: state.count)
        renders.append(count)
        return pn.Text(f"count={count}")

    result = render(Count())
    assert renders == [0]

    result.act(lambda: store.update(lambda s: replace(s, label="b")))
    assert renders == [0]

    result.act(lambda: store.update(lambda s: replace(s, count=1)))
    assert renders == [0, 1]
    assert result.text() == ["count=1"]


def test_use_store_fresh_selector_each_render_subscribes_once() -> None:
    store = CountingStore(Counter())
    renders: List[int] = []

    @pn.component
    def Count() -> pn.Node:
        count = pn.use_store(store, lambda state: state.count)
        renders.append(count)
        return pn.Text(str(count))

    result = render(Count())
    for n in range(1, 4):
        result.act(lambda n=n: store.set(Counter(count=n)))  # type: ignore[misc]

    assert renders == [0, 1, 2, 3]
    assert store.subscribe_calls == 1
    assert store.live == 1


def test_use_store_parent_rerender_does_not_resubscribe() -> None:
    store = CountingStore(Counter())
    setters: List[StateSetter[int]] = []

    @pn.component
    def Child() -> pn.Node:
        return pn.Text(pn.use_store(store, lambda s: s.label))

    @pn.component
    def Parent() -> pn.Node:
        tick, set_tick = pn.use_state(0)
        setters.append(set_tick)
        return pn.Column(pn.Text(f"tick={tick}"), Child())

    result = render(Parent())
    for n in range(1, 4):
        result.act(lambda n=n: setters[-1](n))  # type: ignore[misc]

    assert result.text() == ["tick=3", "a"]
    assert store.subscribe_calls == 1


def test_use_store_unsubscribes_on_unmount() -> None:
    store = CountingStore(Counter())
    renders: List[int] = []

    @pn.component
    def Count() -> pn.Node:
        count = pn.use_store(store, lambda state: state.count)
        renders.append(count)
        return pn.Text(str(count))

    result = render(Count())
    assert store.live == 1

    result.unmount()
    assert store.live == 0

    store.set(Counter(count=9))
    drain()
    assert renders == [0]


def test_use_store_picks_up_a_write_between_render_and_subscribe() -> None:
    store = pn.Store(0)

    @pn.component
    def Show() -> pn.Node:
        value = pn.use_store(store)
        if value == 0:
            # Simulates another writer landing after render, before the effect subscribes.
            store.set(1)
        return pn.Text(str(value))

    result = render(Show())
    assert result.text() == ["1"]


def test_use_store_write_from_another_thread_reaches_the_component() -> None:
    store = pn.Store(Counter())

    @pn.component
    def Count() -> pn.Node:
        return pn.Text(f"count={pn.use_store(store, lambda s: s.count)}")

    result = render(Count())

    worker = threading.Thread(target=lambda: store.update(lambda s: replace(s, count=42)))
    worker.start()
    worker.join()
    result.settle()

    assert result.text() == ["count=42"]


# ======================================================================
# Bound-method equality and use_subscription
# ======================================================================


class Source:
    def __init__(self) -> None:
        self.value = 0
        self.subscribe_calls = 0
        self._listeners: List[Callable[[], None]] = []

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self.subscribe_calls += 1
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def get(self) -> int:
        return self.value

    def other(self) -> int:
        return self.value

    def bump(self) -> None:
        self.value += 1
        for listener in list(self._listeners):
            listener()


def test_bound_methods_of_the_same_object_and_function_are_equal() -> None:
    source = Source()
    assert source.subscribe is not source.subscribe
    assert equality.equal(source.subscribe, source.subscribe)


def test_bound_methods_of_different_instances_are_not_equal() -> None:
    assert not equality.equal(Source().subscribe, Source().subscribe)


def test_bound_methods_of_different_functions_are_not_equal() -> None:
    source = Source()
    assert not equality.equal(source.get, source.other)


def test_plain_callables_still_compare_by_identity() -> None:
    def fn() -> None:
        return None

    assert equality.equal(fn, fn)
    assert not equality.equal(fn, lambda: None)
    assert not equality.equal(fn, 1)


def test_memo_skips_when_a_bound_method_prop_is_reaccessed() -> None:
    source = Source()
    renders: List[str] = []
    setters: List[StateSetter[int]] = []

    @pn.memo
    @pn.component
    def Child(on_change: Callable[[], None]) -> pn.Node:
        renders.append("child")
        return pn.Text("child")

    @pn.component
    def Parent() -> pn.Node:
        tick, set_tick = pn.use_state(0)
        setters.append(set_tick)
        return pn.Column(pn.Text(str(tick)), Child(on_change=source.bump))

    result = render(Parent())
    result.act(lambda: setters[-1](1))

    assert result.text() == ["1", "child"]
    assert renders == ["child"]


def test_use_subscription_with_bound_methods_subscribes_once() -> None:
    source = Source()
    renders: List[int] = []

    @pn.component
    def Show() -> pn.Node:
        value = pn.use_subscription(source.subscribe, source.get)
        renders.append(value)
        return pn.Text(str(value))

    result = render(Show())
    for _ in range(3):
        result.act(source.bump)

    assert renders == [0, 1, 2, 3]
    assert result.text() == ["3"]
    assert source.subscribe_calls == 1


# ======================================================================
# use_persisted_state
# ======================================================================


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[None]:
    """Isolate the fallback Storage module in a temp dir, as tests/test_storage.py does."""
    os.environ["PN_STORAGE_DIR"] = str(tmp_path)
    native_module("Storage").impl._reset()  # type: ignore[attr-defined]
    yield
    native_module("Storage").impl._reset()  # type: ignore[attr-defined]
    os.environ.pop("PN_STORAGE_DIR", None)


def _stored(key: str) -> Any:
    return run_blocking(AsyncStorage.get_json(key))


def _seed(key: str, value: Any) -> None:
    run_blocking(AsyncStorage.set_json(key, value))


@pytest.fixture
def writes(monkeypatch: pytest.MonkeyPatch) -> List[Any]:
    """Record every ``AsyncStorage.set_json`` call (still writing through)."""
    recorded: List[Any] = []
    real = AsyncStorage.set_json

    async def recording(key: str, value: Any) -> None:
        recorded.append(value)
        await real(key, value)

    monkeypatch.setattr(AsyncStorage, "set_json", staticmethod(recording))
    return recorded


def _persisted_counter(renders: List[int], setters: List[StateSetter[int]]) -> pn.Component[[]]:
    @pn.component
    def Counter() -> pn.Node:
        value, set_value = pn.use_persisted_state("counter", 0)
        renders.append(value)
        setters.append(set_value)
        return pn.Text(f"value={value}")

    return Counter


@pytest.mark.usefixtures("storage")
def test_persisted_state_loads_the_stored_value() -> None:
    _seed("counter", 7)
    renders: List[int] = []
    setters: List[StateSetter[int]] = []

    result = render(_persisted_counter(renders, setters)())

    assert renders[0] == 0
    assert result.text() == ["value=7"]


@pytest.mark.usefixtures("storage")
def test_persisted_state_keeps_initial_when_nothing_is_stored(writes: List[Any]) -> None:
    renders: List[int] = []
    setters: List[StateSetter[int]] = []

    result = render(_persisted_counter(renders, setters)())

    assert result.text() == ["value=0"]
    assert writes == []
    assert _stored("counter") is None


@pytest.mark.usefixtures("storage")
def test_persisted_state_setter_accepts_an_updater(writes: List[Any]) -> None:
    _seed("counter", 1)
    renders: List[int] = []
    setters: List[StateSetter[int]] = []
    result = render(_persisted_counter(renders, setters)())
    writes.clear()

    result.act(lambda: setters[-1](lambda v: v + 1))
    result.act(lambda: setters[-1](lambda v: v + 1))

    assert result.text() == ["value=3"]
    assert _stored("counter") == 3
    assert writes == [2, 3]


@pytest.mark.usefixtures("storage")
def test_persisted_state_writes_after_commit_not_inside_the_updater(writes: List[Any]) -> None:
    renders: List[int] = []
    setters: List[StateSetter[int]] = []
    result = render(_persisted_counter(renders, setters)())
    observed_in_updater: List[Any] = []

    def updater(value: int) -> int:
        observed_in_updater.append(list(writes))
        return value + 5

    setters[-1](updater)
    # The updater ran and the state changed, but nothing was written yet.
    assert observed_in_updater == [[]]
    assert writes == []

    result.settle()
    assert writes == [5]
    assert _stored("counter") == 5


@pytest.mark.usefixtures("storage")
def test_persisted_state_transition_replay_writes_once(writes: List[Any]) -> None:
    setters: List[StateSetter[int]] = []
    transitions: List[Callable[[Callable[[], None]], None]] = []

    @pn.component
    def Counter() -> pn.Node:
        value, set_value = pn.use_persisted_state("counter", 0)
        _pending, start = pn.use_transition()
        setters.append(set_value)
        transitions.append(start)
        return pn.Text(f"value={value}")

    result = render(Counter())
    result.act(lambda: transitions[-1](lambda: setters[-1](lambda v: v + 1)))

    assert result.text() == ["value=1"]
    assert writes == [1]


@pytest.mark.usefixtures("storage")
def test_persisted_state_value_set_before_load_finishes_wins(
    monkeypatch: pytest.MonkeyPatch, writes: List[Any]
) -> None:
    _seed("counter", 100)
    writes.clear()
    gates: List["asyncio.Future[None]"] = []
    real_get_json = AsyncStorage.get_json

    async def slow_get_json(key: str) -> Any:
        gate: "asyncio.Future[None]" = asyncio.get_running_loop().create_future()
        gates.append(gate)
        await gate
        return await real_get_json(key)

    monkeypatch.setattr(AsyncStorage, "get_json", staticmethod(slow_get_json))
    renders: List[int] = []
    setters: List[StateSetter[int]] = []
    result = render(_persisted_counter(renders, setters)(), settle_first=False)

    assert drain(timeout=1.0, until=lambda: bool(gates))
    setters[-1](lambda v: v + 1)
    result.reconciler.flush_dirty()
    assert writes == []  # nothing is written before the load finishes

    gates[0].set_result(None)
    result.settle()

    assert result.text() == ["value=1"]
    assert run_blocking(real_get_json("counter")) == 1
    assert writes == [1]
    assert 100 not in renders


@pytest.mark.usefixtures("storage")
def test_persisted_state_separate_keys_are_independent() -> None:
    _seed("a", "stored-a")
    captured: Dict[str, Optional[str]] = {}

    @pn.component
    def Both() -> pn.Node:
        a, _set_a = pn.use_persisted_state("a", "initial-a")
        b, _set_b = pn.use_persisted_state("b", "initial-b")
        captured.update(a=a, b=b)
        return None

    render(Both())
    assert captured == {"a": "stored-a", "b": "initial-b"}
