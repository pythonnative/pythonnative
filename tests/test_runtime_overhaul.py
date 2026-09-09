"""Regression tests for component ownership and scheduling contracts."""

import asyncio
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

import pythonnative as pn
from pythonnative.bridge.commits import CommitState, ViewState
from pythonnative.events import get_event_registry
from pythonnative.profiling import Profiler
from pythonnative.reconciler import Reconciler
from pythonnative.runtime import run_blocking
from pythonnative.testing import FakeBackend, render


def test_element_owns_immutable_snapshot() -> None:
    props = {"text": "before"}
    children: list[Any] = []
    element = pn.Element("Text", props, children)
    props["text"] = "after"
    children.append(pn.Text("child"))
    assert element.props["text"] == "before"
    assert element.children == ()
    with pytest.raises(TypeError):
        element.props["text"] = "changed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        element.type = "View"  # type: ignore[misc]


def test_python_argument_binding_preserves_positional_only_and_variadics() -> None:
    @pn.component
    def Card(title: str, /, subtitle: str = "sub", *children: pn.Element, enabled: bool = True, **extra: Any) -> Any:
        return title, subtitle, children, enabled, extra

    child = pn.Text("body")
    element = Card("title", "subtitle", child, enabled=False, custom=3)
    assert Card.render(element) == ("title", "subtitle", (child,), False, {"custom": 3})
    with pytest.raises(TypeError):
        Card(title="wrong")  # type: ignore[call-arg]


def test_async_provider_environment_survives_await() -> None:
    context = pn.create_context("default")

    @pn.component
    async def Child() -> pn.Element:
        await asyncio.sleep(0)
        return pn.Text(pn.use_context(context))

    result = render(context.Provider("provided", pn.Suspense(Child(), fallback=pn.Text("loading"))))
    assert result.get_by_text("provided")
    result.unmount()


def test_urgent_state_rebases_after_deferred_updates_and_setters_are_stable() -> None:
    async def exercise() -> None:
        handles: dict[str, Any] = {}
        snapshots: list[Any] = []
        setters: list[Any] = []

        @pn.component
        def Counter() -> pn.Element:
            value, setter = pn.use_state(0)
            pending, start = pn.use_transition()
            handles.update(set=setter, start=start)
            setters.append(setter)
            snapshots.append((value, pending))
            return pn.Text(str(value))

        rec = Reconciler(FakeBackend())
        rec.mount(Counter())
        handles["start"](lambda: handles["set"](lambda value: value + 10))
        handles["set"](lambda value: value + 1)
        assert snapshots[-1] == (1, True)
        rec.transitions.flush()
        assert snapshots[-1] == (11, False)
        assert all(setter is setters[0] for setter in setters)
        rec.unmount()

    run_blocking(exercise(), timeout=2)


def test_failed_render_keeps_committed_tree_refs_events_and_effects() -> None:
    old_ref: pn.Ref[Any] = pn.Ref()
    new_ref: pn.Ref[Any] = pn.Ref()
    effects: list[str] = []
    old_callback, new_callback = lambda: None, lambda: None

    @pn.component
    def Failing() -> pn.Element:
        pn.use_effect(lambda: effects.append("rejected"), [])
        raise ValueError("render rejected")

    backend = FakeBackend()
    rec = Reconciler(backend)
    rec.mount(pn.Column(pn.Button("old", ref=old_ref, on_press=old_callback)))
    tag = old_ref._pn_tag
    before = old_ref.current
    with pytest.raises(ValueError, match="render rejected"):
        rec.reconcile(pn.Column(pn.Button("new", ref=new_ref, on_press=new_callback), Failing()))
    assert old_ref.current is before
    assert new_ref.current is None
    assert get_event_registry().get(tag, "on_press") is old_callback
    assert effects == []
    assert rec.root is not None and rec.root.children[0].element.props["title"] == "old"
    rec.reconcile(pn.Column(pn.Button("recovered", ref=old_ref, on_press=old_callback)))
    rec.unmount()


def test_commit_overlay_work_depends_on_changed_records() -> None:
    state = CommitState("app", 1, views={i: ViewState("Text", {"text": "before"}) for i in range(1, 10001)})
    untouched = state.views[2]
    with Profiler() as profiler:
        candidate = state.prepare(
            {"version": 2, "application": "app", "surface": 1, "revision": 1, "ops": [["u", 1, {"text": "after"}]]}
        )
    assert state.views[1].props["text"] == "before"
    assert candidate.views[2] is untouched
    assert profiler.counters["commit.records_copied"] == 1
    state = candidate.publish()
    assert state.views[1].props["text"] == "after"


def test_positional_only_name_can_also_be_in_keyword_arguments() -> None:
    @pn.component
    def Example(value: str, /, **extras: Any) -> Any:
        return value, extras

    assert Example.render(Example("positional", value="keyword")) == ("positional", {"value": "keyword"})


def test_native_mount_failure_retires_committed_effects_and_refs() -> None:
    class FailingBackend(FakeBackend):
        fail = False
        _failed = False

        def apply_mutations(self, ops: Any) -> None:
            if self.fail:
                self._failed = True
                raise RuntimeError("native mount failed")
            super().apply_mutations(ops)

    cleaned: list[str] = []
    reference: pn.Ref[Any] = pn.Ref()

    @pn.component
    def Owner(value: str) -> pn.Element:
        pn.use_effect(lambda: lambda: cleaned.append("owner"), [])
        return pn.Text(value, ref=reference)

    backend = FailingBackend()
    rec = Reconciler(backend)
    rec.mount(Owner("before"))
    backend.fail = True
    with pytest.raises(RuntimeError, match="native mount failed"):
        rec.reconcile(Owner("after"))
    assert rec.root is None
    assert reference.current is None
    assert cleaned == ["owner"]


def test_render_ref_mutations_roll_back_with_failed_work() -> None:
    state: dict[str, Any] = {}

    @pn.component
    def Owner(fail: bool) -> pn.Element:
        reference = pn.use_ref("before")
        state["reference"] = reference
        if fail:
            reference.current = "rejected"
            raise ValueError("failed")
        return pn.Text(reference.current)

    result = render(Owner(False))
    with pytest.raises(ValueError, match="failed"):
        result.rerender(Owner(True))
    assert state["reference"].current == "before"
    result.unmount()


def test_obsolete_async_component_work_is_canceled_before_it_can_publish() -> None:
    async def exercise() -> None:
        gates = {name: asyncio.Event() for name in ("old", "new")}
        canceled: list[str] = []

        @pn.component
        async def Child(value: str) -> pn.Element:
            try:
                await gates[value].wait()
                return pn.Text(value)
            except asyncio.CancelledError:
                canceled.append(value)
                raise

        def tree(value: str) -> pn.Element:
            return pn.Suspense(Child(value), fallback=pn.Text("loading"))

        backend = FakeBackend()
        rec = Reconciler(backend)
        rec.mount(tree("old"))
        await asyncio.sleep(0)
        rec.reconcile(tree("new"))
        gates["old"].set()
        await asyncio.sleep(0)
        assert "old" in canceled
        assert all(view.text != "old" for view in backend.views.values())
        gates["new"].set()
        for _ in range(5):
            await asyncio.sleep(0)
        assert any(view.text == "new" for view in backend.views.values())
        rec.unmount()

    run_blocking(exercise(), timeout=2)


def test_canceling_a_typed_builtin_notifies_native_once() -> None:
    from pythonnative.bridge import codec
    from pythonnative.native_modules.registry import BridgeModule

    class PendingTransport:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        def call(self, module: str, method: str, args: str) -> str:
            self.calls.append((module, method, codec.loads(args)))
            return codec.dumps({"ok": True, "value": None} if method == "_pn_cancel" else {"pending": True})

    async def exercise() -> None:
        transport = PendingTransport()
        module = BridgeModule("Camera", transport)
        task = asyncio.create_task(module.call_async("take_photo"))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert [call[1] for call in transport.calls] == ["take_photo", "_pn_cancel"]
        assert transport.calls[1][2]["args"]["call_id"] == transport.calls[0][2]["call_id"]

    run_blocking(exercise(), timeout=2)


def test_failed_render_preserves_accepted_async_work() -> None:
    async def exercise() -> None:
        gate = asyncio.Event()
        started: list[str] = []
        canceled: list[str] = []

        @pn.component
        async def Child(value: str) -> pn.Element:
            started.append(value)
            try:
                await gate.wait()
                return pn.Text(value)
            except asyncio.CancelledError:
                canceled.append(value)
                raise

        @pn.component
        def Sibling(fail: bool) -> pn.Element:
            if fail:
                raise ValueError("rejected sibling")
            return pn.Text("sibling")

        def tree(value: str, fail: bool = False) -> pn.Element:
            return pn.Column(pn.Suspense(Child(value), fallback=pn.Text("loading")), Sibling(fail))

        backend = FakeBackend()
        rec = Reconciler(backend)
        rec.mount(tree("accepted"))
        await asyncio.sleep(0)
        with pytest.raises(ValueError, match="rejected sibling"):
            rec.reconcile(tree("rejected", True))
        gate.set()
        for _ in range(8):
            await asyncio.sleep(0)
        assert started == ["accepted"]
        assert canceled == []
        assert any(view.text == "accepted" for view in backend.views.values())
        rec.unmount()

    run_blocking(exercise(), timeout=2)
