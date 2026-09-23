"""Work bounds, input causality, and failure isolation for the commit pipeline."""

import asyncio
import random
import threading
from dataclasses import dataclass
from typing import Any

import pytest

import pythonnative as pn
from pythonnative import runtime
from pythonnative.bridge import codec
from pythonnative.bridge.fake import FakeTransport
from pythonnative.bridge.list_store import ListStore
from pythonnative.events import get_event_registry
from pythonnative.native_views import set_backend
from pythonnative.native_views.bridge_backend import BridgeBackend
from pythonnative.profiling import Profiler
from pythonnative.reconciler import Reconciler
from pythonnative.testing import render


@dataclass(frozen=True)
class Item:
    id: str
    title: str


def row(item: Item, index: int) -> pn.Element:
    return pn.Text(f"{index}: {item.title}")


def test_list_data_updates_only_changed_metadata_and_preserves_mounted_state() -> None:
    source = pn.ListData((Item(str(i), str(i)) for i in range(100_000)), key=lambda item: item.id)
    result = render(pn.FlatList(data=source, render_item=row, item_height=44), viewport=None)
    tag = result.get_by_type("VirtualList").tag
    keys = result.backend.list_stores[tag].keys
    with Profiler() as profile:
        source.update("0", Item("0", "changed"))
        result.settle()
    packet = result.get_by_type("VirtualList").props["dataset"]
    assert packet["changes"] == [["u", ["0", 2, 44.0, False]]]
    assert len(codec.dumps(packet)) < 120
    assert profile.counters["list.snapshot_rows"] == 0
    assert profile.counters["list.incremental_changes"] == 1
    assert profile.counters["list.rows_validated"] == 1
    assert result.backend.list_stores[tag].keys is keys
    assert result.get_by_text("0: changed")
    assert len(result.get_all_by_type("Text")) < 60
    result.unmount()
    assert not source._listeners


def test_switching_from_a_mutated_incremental_source_replaces_all_native_keys() -> None:
    source = pn.ListData([Item("a", "A"), Item("b", "B")], key=lambda item: item.id)
    result = render(pn.FlatList(data=source, render_item=row))
    source.clear()
    result.rerender(pn.FlatList(data=[Item("z", "Z")], render_item=row, key_extractor=lambda item, index: item.id))
    store = result.backend.list_stores[result.get_by_type("VirtualList").tag]
    assert store.keys == ["z"]
    assert result.get_by_text("0: Z")
    result.unmount()


def test_switching_incremental_sources_refreshes_rows_with_matching_keys_and_versions() -> None:
    source = pn.ListData([Item("a", "Before")], key=lambda item: item.id)
    replacement = pn.ListData([Item("a", "After")], key=lambda item: item.id)
    result = render(pn.FlatList(data=source, render_item=row))
    result.rerender(pn.FlatList(data=replacement, render_item=row))
    assert result.get_by_text("0: After")
    assert not result.query_by_text("0: Before")
    result.unmount()
    assert not source._listeners and not replacement._listeners


def test_window_events_do_not_read_old_indices_through_a_mutated_source() -> None:
    source = pn.ListData([Item("a", "A"), Item("b", "B")], key=lambda item: item.id)
    seen: list[list[pn.ViewableItem[Item]]] = []
    result = render(pn.FlatList(data=source, render_item=row, on_viewable_items_changed=seen.append))
    native = result.get_by_type("VirtualList")
    revision = native.props["dataset"]["revision"]
    on_window = get_event_registry().get(native.tag, "on_window")
    on_bind = get_event_registry().get(native.tag, "on_bind_row")
    assert on_window is not None and on_bind is not None
    seen.clear()
    source.clear()
    on_window({"revision": revision, "first": 0, "last": 1})
    on_bind({"revision": revision, "index": 1, "key": "b"})
    assert not seen
    result.settle()
    store = result.backend.list_stores[result.get_by_type("VirtualList").tag]
    assert not store.keys
    result.unmount()


def test_list_data_batch_move_remove_and_insert_keep_indices_and_keys() -> None:
    source = pn.ListData([Item("a", "A"), Item("b", "B"), Item("c", "C")], key=lambda item: item.id)
    result = render(pn.FlatList(data=source, render_item=row, item_height=44))
    seen = []
    unsubscribe = source.subscribe(lambda: seen.append(source.revision))
    with source.batch():
        source.update("b", Item("b", "B2"))
        source.move("c", 0)
        source.remove("a")
        source.insert(1, Item("d", "D"))
    result.settle()
    store = result.backend.list_stores[result.get_by_type("VirtualList").tag]
    assert store.keys == ["c", "d", "b"]
    assert result.get_by_text("0: C")
    assert result.get_by_text("1: D")
    assert result.get_by_text("2: B2")
    assert seen == [4]
    unsubscribe()
    result.unmount()


def test_lagging_subscribers_reset_after_bounded_history_expires() -> None:
    source = pn.ListData([Item("a", "A")], key=lambda item: item.id, history_limit=2)
    result = render(pn.FlatList(data=source, render_item=row))
    with source.batch():
        for i in range(5):
            source.update("a", Item("a", str(i)))
    result.settle()
    assert result.get_by_type("VirtualList").props["dataset"]["changes"][0][0] == "reset"
    assert len(source._history) == 2
    assert result.get_by_text("0: 4")
    result.unmount()


def test_list_data_validates_before_mutation_and_notifies_successful_batch_prefix() -> None:
    data = pn.ListData([Item("a", "A")], key=lambda item: item.id)
    notifications = []
    data.subscribe(lambda: notifications.append(data.revision))
    with pytest.raises(ValueError):
        with data.batch():
            data.update("a", Item("a", "new"))
            data.insert(0, Item("a", "duplicate"))
    assert data.get("a").title == "new"
    assert notifications == [1]
    with pytest.raises(ValueError):
        data.update("a", Item("b", "wrong key"))
    assert data.revision == 1


@pytest.mark.parametrize("seed", range(5))
def test_randomized_list_patches_match_a_reference_sequence(seed: int) -> None:
    rng = random.Random(seed)
    store = ListStore()
    expected: list[str] = []
    for step in range(250):
        revision = store.revision
        choice = rng.choice(["i", "u", "d", "m"]) if expected else "i"
        if choice == "i":
            index, key = rng.randrange(len(expected) + 1), str(step)
            expected.insert(index, key)
            change: list[Any] = ["i", index, [key, 1, 44, False]]
        elif choice == "d":
            key = expected.pop(rng.randrange(len(expected)))
            change = ["d", key]
        elif choice == "m":
            index, old = rng.randrange(len(expected)), rng.randrange(len(expected))
            key = expected.pop(old)
            expected.insert(index, key)
            change = ["m", key, index]
        else:
            key = rng.choice(expected)
            change = ["u", [key, store.rows[key].revision + 1, rng.randrange(1, 200), False]]
        store.apply({"base": revision, "revision": revision + 1, "changes": [change]})
        assert store.keys == expected
        assert set(store.rows) == set(expected)
        before = dict(store.rows)
        with pytest.raises(ValueError):
            store.apply(
                {
                    "base": revision + 1,
                    "revision": revision + 2,
                    "changes": [["i", 0, ["new", 1, 44, False]], ["d", "missing"]],
                }
            )
        assert store.rows == before and store.keys == expected and store.revision == revision + 1


class DelayedTransport(FakeTransport):
    asynchronous_commits = True

    def __init__(self) -> None:
        super().__init__()
        self.gate = threading.Event()
        self.entered = threading.Event()
        self.reject = False
        self.worker_threads: list[str] = []

    def apply(self, transaction_json: str) -> str:
        self.worker_threads.append(threading.current_thread().name)
        self.entered.set()
        if not self.gate.wait(3):
            raise TimeoutError("Test didn't release native commit")
        if self.reject:
            return codec.dumps({"ok": False, "failed": False, "error": "test rejection"})
        return super().apply(transaction_json)


async def entered(transport: DelayedTransport) -> None:
    async with asyncio.timeout(2):
        while not transport.entered.is_set():
            await asyncio.sleep(0.001)


def test_pending_commit_keeps_loop_responsive_and_coalesces_state_before_effects() -> None:
    async def exercise() -> None:
        transport = DelayedTransport()
        backend = BridgeBackend(transport)
        set_backend(backend)
        effects, renders, setter = [], [], {}
        reference: pn.Ref[Any] = pn.Ref()

        @pn.component
        def App() -> pn.Element:
            value, update = pn.use_state(0)
            setter["update"] = update
            renders.append(value)
            pn.use_layout_effect(lambda: effects.append((value, reference.current is not None)), [value])
            return pn.Text(str(value), ref=reference)

        reconciler = Reconciler(backend)
        reconciler.mount(App())
        await entered(transport)
        assert reconciler.commit_pending and reference.current is None and not effects
        # These callbacks execute while native is deliberately blocked.
        for _ in range(25):
            setter["update"](lambda value: value + 1)
        await asyncio.sleep(0)
        assert renders == [0]
        transport.gate.set()
        await asyncio.wait_for(reconciler.wait_for_commit(), 2)
        assert renders == [0, 25]
        assert effects == [(0, True), (25, True)]
        assert all(name != "PythonNative" for name in transport.worker_threads)
        reconciler.unmount()
        await reconciler.wait_for_commit()
        assert reference.current is None and backend.live_view_count() == 0
        set_backend(None)

    runtime.run_blocking(exercise(), timeout=5)


def test_rejected_commit_rolls_back_before_replaying_queued_input() -> None:
    async def exercise() -> None:
        transport = DelayedTransport()
        transport.gate.set()
        backend = BridgeBackend(transport)
        reconciler = Reconciler(backend)
        errors: list[BaseException] = []
        setter: dict[str, Any] = {}
        reconciler.on_commit_error = errors.append

        @pn.component
        def App() -> pn.Element:
            value, update = pn.use_state(0)
            setter["update"] = update
            return pn.Text(str(value))

        reconciler.mount(App())
        await reconciler.wait_for_commit()
        transport.gate.clear()
        transport.entered.clear()
        transport.reject = True
        setter["update"](1)
        await entered(transport)
        setter["update"](lambda value: value + 1)
        transport.gate.set()
        async with asyncio.timeout(2):
            while not errors:
                await asyncio.sleep(0)
        transport.reject = False
        await reconciler.wait_for_commit()
        assert not backend._failed
        assert next(iter(transport.views.values())).props["text"] == "2"
        reconciler.unmount()
        await reconciler.wait_for_commit()

    runtime.run_blocking(exercise(), timeout=5)


def test_two_reconcilers_serialize_commits_and_mount_replacement_waits() -> None:
    async def exercise() -> None:
        transport = DelayedTransport()
        backend = BridgeBackend(transport)
        first, second = Reconciler(backend), Reconciler(backend)
        first.mount(pn.Text("first"))
        await entered(transport)
        second.mount(pn.Text("second"))
        first.mount(pn.Text("replacement"))
        transport.gate.set()
        await asyncio.wait_for(asyncio.gather(first.wait_for_commit(), second.wait_for_commit()), 2)
        assert sorted(view.props["text"] for view in transport.views.values()) == ["replacement", "second"]
        assert backend._commit.revision == 4
        first.unmount()
        second.unmount()
        await asyncio.gather(first.wait_for_commit(), second.wait_for_commit())
        assert not transport.views

    runtime.run_blocking(exercise(), timeout=5)


def test_cancelled_waiter_does_not_cancel_native_publication() -> None:
    async def exercise() -> None:
        transport = DelayedTransport()
        backend = BridgeBackend(transport)
        reconciler = Reconciler(backend)
        reconciler.mount(pn.Text("survives"))
        await entered(transport)
        waiter = asyncio.create_task(reconciler.wait_for_commit())
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        transport.gate.set()
        await asyncio.wait_for(reconciler.wait_for_commit(), 2)
        assert reconciler.root_view() is not None and not backend._failed
        reconciler.unmount()
        await reconciler.wait_for_commit()

    runtime.run_blocking(exercise(), timeout=5)


def test_append_and_remove_update_the_previous_last_rows_separator() -> None:
    source = pn.ListData([Item("a", "A")], key=lambda item: item.id)
    result = render(pn.FlatList(data=source, render_item=row, item_separator=lambda: pn.Text("separator")))
    assert not result.get_all_by_text("separator")
    source.append(Item("b", "B"))
    result.settle()
    assert len(result.get_all_by_text("separator")) == 1
    source.remove("b")
    result.settle()
    assert not result.get_all_by_text("separator")
    result.unmount()


def test_shared_list_trace() -> None:
    import json
    from pathlib import Path

    store = ListStore()
    for case in json.loads((Path(__file__).parent / "contracts/list-trace.json").read_text()):
        if case["valid"]:
            store.apply(case["packet"])
        else:
            with pytest.raises(ValueError):
                store.apply(case["packet"])
        assert store.keys == case["keys"], case["name"]
        assert store.revision == case["revision"], case["name"]


def test_events_wait_for_refs_and_layout_effects() -> None:
    from pythonnative.bridge import _on_event

    async def exercise() -> None:
        transport = DelayedTransport()
        backend = BridgeBackend(transport)
        set_backend(backend)
        reference: pn.Ref[Any] = pn.Ref()
        effects: list[bool] = []
        clicks: list[tuple[bool, bool]] = []

        @pn.component
        def App() -> pn.Element:
            pn.use_layout_effect(lambda: effects.append(True), [])
            return pn.Button(
                "Ready", ref=reference, on_press=lambda: clicks.append((reference.current is not None, bool(effects)))
            )

        reconciler = Reconciler(backend)
        reconciler.mount(App())
        await entered(transport)
        tag = reconciler.root_tag
        assert tag is not None
        _on_event(
            tag,
            "on_press",
            codec.dumps(
                {"application": backend._commit.application, "surface": 1, "revision": 1, "sequence": 1, "args": []}
            ),
        )
        assert clicks == []
        transport.gate.set()
        await reconciler.wait_for_commit()
        await asyncio.sleep(0)
        assert clicks == [(True, True)]
        reconciler.unmount()
        await reconciler.wait_for_commit()
        set_backend(None)

    runtime.run_blocking(exercise(), timeout=5)


def test_host_refresh_waits_for_pending_mount_and_recovers_unknown_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    from pythonnative.hosts.base import ScreenHost

    class LostAcknowledgement(DelayedTransport):
        lose_ack = False

        def apply(self, payload: str) -> str:
            reply = super().apply(payload)
            return "null" if self.lose_ack else reply

    async def exercise() -> None:
        transport = LostAcknowledgement()
        backend = BridgeBackend(transport)
        set_backend(backend)
        module = types.ModuleType("pending_refresh_app")
        label = ["first"]
        errors: list[BaseException] = []

        @pn.component
        def App() -> pn.Element:
            return pn.Text(label[0])

        module.App = App  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, module.__name__, module)
        host = ScreenHost(None, module.__name__, App)
        host.on_create()
        await entered(transport)
        original = host.reconciler
        label[0] = "refreshed"
        host.refresh([module.__name__], force_remount=True)
        transport.gate.set()
        async with asyncio.timeout(2):
            while host.reconciler is original or host.reconciler.commit_pending:
                await asyncio.sleep(0.001)
        assert [view.props["text"] for view in transport.views.values()] == ["refreshed"]
        host.reconciler.on_commit_error = errors.append
        transport.lose_ack = True
        host.reconciler.reconcile(pn.Text("unknown outcome"))
        async with asyncio.timeout(2):
            while not errors:
                await asyncio.sleep(0.001)
        assert backend._failed and host.reconciler.root is None
        transport.lose_ack = False
        host.refresh([module.__name__], force_remount=True)
        await host.reconciler.wait_for_commit()
        assert not backend._failed
        assert [view.props["text"] for view in transport.views.values()] == ["refreshed"]
        reconciler = host.reconciler
        host.on_destroy()
        await reconciler.wait_for_commit()
        assert not transport.views
        set_backend(None)

    runtime.run_blocking(exercise(), timeout=6)


@pytest.mark.parametrize("incremental", [False, True])
def test_lists_mount_through_validated_bridge_without_scroll_subscribers(incremental: bool) -> None:
    transport = FakeTransport()
    backend = BridgeBackend(transport)
    reconciler = Reconciler(backend)
    data = pn.ListData([Item("a", "A")], key=lambda item: item.id) if incremental else [Item("a", "A")]
    reconciler.mount(pn.FlatList(data=data, render_item=row))
    native = transport.find("VirtualList")[0]
    assert "on_scroll" not in native.props
    assert "on_scroll" not in native.props.get("_pn_events", [])
    reconciler.unmount()
    reconciler.mount(
        pn.SectionList(sections=[pn.Section(key="a", title="A", data=["item"])], sticky_section_headers=True)
    )
    assert transport.find("VirtualList")
    reconciler.unmount()
