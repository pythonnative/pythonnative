"""Behavioral contracts for the application loop, shared requests, and commits."""

import asyncio
import threading
from dataclasses import dataclass
from typing import Annotated

import pytest

import pythonnative as pn
from pythonnative import runtime
from pythonnative.animation_graph import serialize
from pythonnative.bridge import codec
from pythonnative.bridge.commits import CommitError
from pythonnative.bridge.fake import FakeTransport
from pythonnative.mutations import CreateOp, DestroyOp, InsertOp, UpdateOp
from pythonnative.native_views.bridge_backend import BridgeBackend
from pythonnative.query import QueryClient
from pythonnative.sdk.schema import ComponentSchema, NativeField


def test_text_echo_acknowledges_only_the_native_edits_python_has_seen() -> None:
    transport = FakeTransport()
    backend = BridgeBackend(transport)
    backend.apply_mutations([CreateOp(1, "TextInput", {"value": ""})])
    event = backend._commit.acknowledgement() | {"sequence": 1, "args": ["20"], "edit_revision": 2}
    assert backend.accept_event(1, "on_change", event)
    backend.apply_mutations([UpdateOp(1, {"value": "20"})])
    assert transport.views[1].props["_pn_edit_revision"] == 2
    # A later native edit must not be acknowledged before its callback arrives.
    backend.apply_mutations([UpdateOp(1, {"value": "normalized"})])
    assert transport.views[1].props["_pn_edit_revision"] == 2


def test_standard_loop_supports_sockets_timeout_and_task_groups() -> None:
    runtime.start()

    async def exercise() -> None:
        assert threading.current_thread().name == "PythonNative"
        connected = asyncio.Event()

        async def echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                writer.write(await reader.readexactly(4))
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                connected.set()

        async with asyncio.timeout(2):
            async with await asyncio.start_server(echo, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                try:
                    async with asyncio.TaskGroup() as group:
                        received = group.create_task(reader.readexactly(4))
                        writer.write(b"ping")
                        group.create_task(writer.drain())
                    assert received.result() == b"ping"
                    await connected.wait()
                finally:
                    writer.close()
                    await writer.wait_closed()
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.001):
                await asyncio.Event().wait()

    runtime.run_blocking(exercise(), timeout=4)


def test_component_scope_cancels_tasks_without_cancelling_application_work() -> None:
    runtime.start()

    async def exercise() -> None:
        scope = runtime.TaskScope("component")
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def work() -> None:
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        owned = scope.create_task(work())
        app = runtime.run_application_task(asyncio.sleep(0.01, result="saved"))
        await started.wait()
        scope.close()
        await cancelled.wait()
        assert owned.cancelled()
        assert await app == "saved"
        await asyncio.sleep(0)
        assert scope.pending == 0
        with pytest.raises(RuntimeError, match="closed"):
            scope.create_task(asyncio.sleep(0))

    runtime.run_blocking(exercise(), timeout=2)


def test_query_deduplicates_and_final_unsubscribe_cancels() -> None:
    async def exercise() -> None:
        cache = QueryClient()
        started, cancelled = asyncio.Event(), asyncio.Event()
        calls = 0

        async def fetch() -> str:
            nonlocal calls
            calls += 1
            try:
                started.set()
                await asyncio.Event().wait()
                return "unreachable"
            finally:
                cancelled.set()

        remove_one = cache.subscribe("shared", fetch, lambda: None)
        remove_two = cache.subscribe("shared", fetch, lambda: None)
        await started.wait()
        assert calls == 1
        remove_one()
        await asyncio.sleep(0)
        assert not cancelled.is_set()
        remove_two()
        await cancelled.wait()
        assert not cache.snapshot("shared").loading
        cache.close()

    runtime.run_blocking(exercise(), timeout=2)


def test_optimistic_query_result_supersedes_pending_fetch() -> None:
    async def exercise() -> None:
        cache = QueryClient(capacity=2)
        started = asyncio.Event()

        async def fetch() -> str:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return "stale"  # Misbehaving clients still can't overwrite new data.
            return "stale"

        remove = cache.subscribe("item", fetch, lambda: None)
        await started.wait()
        cache.set_data("item", "optimistic")
        await asyncio.sleep(0)
        assert cache.snapshot("item").data == "optimistic"
        remove()
        for i in range(50):
            cache.set_data(i, i)
        assert len(cache._entries) == 2
        cache.close()

    runtime.run_blocking(exercise(), timeout=2)


def test_rejected_acknowledgement_poisoning_and_explicit_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport()
    backend = BridgeBackend(transport)
    backend.apply_mutations([CreateOp(1, "View", {})])
    original = transport.apply
    monkeypatch.setattr(transport, "apply", lambda payload: codec.dumps({"ok": True, "revision": 999}))
    with pytest.raises(CommitError, match="rejected"):
        backend.apply_mutations([CreateOp(2, "Text", {"text": "uncommitted"})])
    assert backend.resolve_view(2) is None
    with pytest.raises(CommitError, match="failed"):
        backend.apply_mutations([CreateOp(3, "Text", {})])
    monkeypatch.setattr(transport, "apply", original)
    backend.reset()
    backend.apply_mutations([CreateOp(4, "View", {})])
    assert backend.live_view_count() == 1


def test_invalid_tree_commit_has_no_partial_effect() -> None:
    transport = FakeTransport()
    backend = BridgeBackend(transport)
    with pytest.raises(CommitError):
        backend.apply_mutations([CreateOp(1, "View", {}), InsertOp(1, 1, 0)])
    assert transport.views == {}
    backend.apply_mutations([CreateOp(1, "View", {})])
    envelope = backend._commit.acknowledgement() | {"sequence": 1, "args": []}
    envelope.pop("ok")
    assert backend.accept_event(1, "on_press", envelope)
    assert not backend.accept_event(1, "on_press", envelope)
    backend.apply_mutations([DestroyOp(1)])
    assert not backend.accept_event(1, "on_press", envelope | {"sequence": 2})


def test_schema_rejects_wrong_types_and_records_layout_metadata() -> None:
    @dataclass(frozen=True)
    class Gauge:
        value: Annotated[float, NativeField(invalidates_layout=True)]
        label: str = ""

    schema = ComponentSchema.from_dataclass("Gauge", Gauge)
    schema.validate({"value": 2.5})
    assert schema.props["value"]["native"]["invalidates_layout"]
    with pytest.raises(TypeError, match="number"):
        schema.validate({"value": True})
    with pytest.raises(TypeError, match="requires"):
        schema.validate({})
    with pytest.raises(TypeError, match="Unknown"):
        schema.validate({"value": 0, "typo": 1})


def test_animation_graph_orders_dependencies_and_retains_keyed_bindings() -> None:
    value = pn.Animated.Value(0)
    derived = (value * 2 + 5).interpolate([0, 100], [0, 1], extrapolate="clamp")
    detach = derived.attach(99, "opacity")
    graph = serialize(value)
    seen: set[int] = set()
    for node in graph["nodes"]:
        assert all(parent["node"] in seen for parent in node.get("inputs", []) if "node" in parent)
        seen.add(node["id"])
    assert graph["bindings"] == [[99, "opacity", id(derived)]]
    assert [node["kind"] for node in graph["nodes"]] == ["value", "multiply", "add", "interpolate"]
    detach()
    assert serialize(value)["bindings"] == []


def test_replacing_derived_bindings_keeps_a_running_graph_owned() -> None:
    from typing import Any

    from pythonnative.native_views import set_registry
    from pythonnative.testing import FakeBackend, render

    class GraphBackend(FakeBackend):
        def __init__(self) -> None:
            super().__init__()
            self.bindings: list[list[Any]] = []

        def install_animation_graph(self, tag: int, graph: dict[str, Any]) -> None:
            self.bindings.append(graph["bindings"])

    backend = GraphBackend()
    set_registry(backend)
    value = pn.Animated.Value(0)

    @pn.component
    def Box(factor: float) -> pn.Element:
        return pn.Animated.View(style=pn.style(opacity=value * factor))

    result = render(Box(0.5), backend=backend)
    try:
        backend.bindings.clear()
        result.rerender(Box(0.75))
        assert backend.bindings
        assert all(backend.bindings), "Replacing bindings must never release the entire graph"
    finally:
        result.unmount()
        set_registry(None)
    assert backend.bindings[-1] == []


def test_implicit_queries_do_not_share_unrelated_closures_or_remounts() -> None:
    from pythonnative.testing import render

    @pn.component
    def Name(value: str) -> pn.Element:
        async def fetch() -> str:
            return value

        query = pn.use_query(fetch, [])
        return pn.Text(query.data or "loading")

    result = render(pn.Column(Name("first"), Name("second")))
    assert result.get_by_text("first")
    assert result.get_by_text("second")
    result.unmount()
    result = render(Name("new application"))
    assert result.get_by_text("new application")
    result.unmount()


def test_nested_async_callback_inherits_component_cancellation_scope() -> None:
    async def exercise() -> None:
        scope = runtime.TaskScope("gesture component")
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def handler() -> None:
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        runtime.invoke(lambda: runtime.invoke(handler), scope=scope)
        await started.wait()
        scope.close()
        await cancelled.wait()
        await asyncio.sleep(0)
        assert scope.pending == 0

    runtime.run_blocking(exercise(), timeout=2)
