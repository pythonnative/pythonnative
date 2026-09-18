"""Tests for the runtime fixes in RFC 0002: effect errors, hidden Suspense siblings,
eager async bodies, the single render-storm policy, dev warnings, typing helpers,
and the journal hot path."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

import pythonnative as pn
from pythonnative import diagnostics, journal, runtime
from pythonnative.component import component
from pythonnative.components import Column, ErrorBoundary, Suspense, Text, TextInput
from pythonnative.element import Element
from pythonnative.hooks import Ref, use_effect, use_layout_effect, use_memo, use_ref, use_state
from pythonnative.mutations import CreateOp
from pythonnative.reconciler import MAX_RENDER_PASSES, Reconciler, VNode
from pythonnative.suspense import start_resource
from pythonnative.testing import FakeBackend, render, render_hook


@pytest.fixture()
def dev_mode() -> Any:
    diagnostics.set_dev_mode(True)
    diagnostics.clear_warnings()
    yield None
    diagnostics.clear_warnings()
    diagnostics.set_dev_mode(False)


class RecordingBackend(FakeBackend):
    """A fake backend that remembers the props of every view ever created."""

    def __init__(self) -> None:
        super().__init__()
        self.created: List[Dict[str, Any]] = []

    def _apply_one(self, op: Any) -> Any:
        if isinstance(op, CreateOp):
            self.created.append(dict(op.props))
        return super()._apply_one(op)


# ======================================================================
# Effect errors route to the nearest ErrorBoundary
# ======================================================================


def test_effect_error_shows_boundary_fallback_without_raising() -> None:
    @component
    def Boom() -> Element:
        use_effect(lambda: (_ for _ in ()).throw(ValueError("effect failed")), [])
        return Text("content")

    caught: List[BaseException] = []
    result = render(
        ErrorBoundary(Boom(), fallback=lambda exc: Text(f"fallback: {exc}"), on_error=caught.append),
    )
    assert result.get_by_text("fallback: effect failed")
    assert result.query_by_text("content") is None
    assert [str(e) for e in caught] == ["effect failed"]
    result.unmount()


def test_layout_effect_error_routes_to_boundary_and_siblings_survive() -> None:
    @component
    def Boom() -> Element:
        def fail() -> None:
            raise RuntimeError("layout effect failed")

        use_layout_effect(fail, [])
        return Text("content")

    result = render(Column(Text("sibling"), ErrorBoundary(Boom(), fallback=Text("fallback"))))
    assert result.text() == ["sibling", "fallback"]
    result.unmount()


def test_effect_error_without_boundary_propagates_but_keeps_the_surface() -> None:
    @component
    def Boom() -> Element:
        def fail() -> None:
            raise ValueError("no boundary")

        use_effect(fail, [])
        return Text("content")

    backend = FakeBackend()
    rec = Reconciler(backend)
    with pytest.raises(ValueError, match="no boundary"):
        rec.mount(Column(Boom()))
    assert rec.root is not None, "a Python error after commit never retires the native surface"
    assert backend.live_view_count() == 2
    assert not getattr(backend, "_failed", False)
    rec.unmount()


def test_effect_error_from_state_update_routes_to_boundary() -> None:
    setters: Dict[str, Any] = {}

    @component
    def Widget() -> Element:
        count, set_count = use_state(0)
        setters["set"] = set_count

        def effect() -> None:
            if count == 1:
                raise ValueError("boom on update")

        use_effect(effect, [count])
        return Text(f"count={count}")

    result = render(Column(Text("header"), ErrorBoundary(Widget(), fallback=Text("fallback"))))
    assert result.text() == ["header", "count=0"]
    setters["set"](1)
    result.settle()
    assert result.text() == ["header", "fallback"]
    result.unmount()


# ======================================================================
# Suspense on update keeps siblings mounted
# ======================================================================


def test_update_suspension_hides_content_and_keeps_sibling_views() -> None:
    gate = runtime.get_loop().create_future()
    field: Ref[Any] = Ref()
    setters: Dict[str, Any] = {}

    @component
    async def Slow() -> Element:
        await gate
        return Text("slow")

    @component
    def Form() -> Element:
        show, set_show = use_state(False)
        setters["show"] = set_show
        children = [TextInput(value="typed", ref=field, test_id="field")]
        if show:
            children.append(Slow())
        return Column(*children, test_id="form")

    backend = FakeBackend()
    result = render(Suspense(Form(), fallback=Text("loading")), backend=backend)
    assert result.get_by_test_id("field").props["value"] == "typed"
    handle = field.current
    tag = handle.tag

    setters["show"](True)
    result.settle()
    assert result.get_by_text("loading"), "the fallback shows beside the hidden content"
    assert result.query_by_test_id("field") is None, "hidden content is not visible"
    assert result.get_by_test_id("field", hidden=True).tag == tag, "but it is still mounted"
    assert result.get_by_test_id("form", hidden=True).hidden
    assert field.current is handle and handle.tag == tag, "the TextInput kept its native view"
    assert tag in backend.views

    gate.set_result(None)
    result.settle()
    assert result.query_by_text("loading") is None
    assert result.get_by_test_id("field").tag == tag
    assert result.text() == ["slow"]
    assert not result.get_by_test_id("form").hidden, "the display override is lifted"
    assert field.current.tag == tag
    result.unmount()


def test_update_suspension_hidden_content_stays_hidden_in_layout() -> None:
    gate = runtime.get_loop().create_future()
    setters: Dict[str, Any] = {}

    @component
    async def Slow() -> Element:
        await gate
        return Text("slow")

    @component
    def Body() -> Element:
        show, set_show = use_state(False)
        setters["show"] = set_show
        children = [Text("static", style={"height": 40})]
        if show:
            children.append(Slow())
        return Column(*children, test_id="body")

    result = render(Column(Suspense(Body(), fallback=Text("loading", test_id="fallback"))))
    setters["show"](True)
    result.settle()
    assert result.get_by_test_id("fallback").frame[1] == 0.0, "the fallback sits where the hidden content was"
    gate.set_result(None)
    result.settle()
    assert result.get_by_test_id("body").frame[3] > 0
    result.unmount()


# ======================================================================
# Async components step eagerly
# ======================================================================


def test_async_component_with_resolved_awaits_renders_inline() -> None:
    ready = start_resource(lambda: "data")

    @component
    async def Ready() -> Element:
        value = await ready
        return Text(value)

    backend = RecordingBackend()
    result = render(Suspense(Ready(), fallback=Text("loading")), backend=backend, settle_first=False)
    assert result.text() == ["data"]
    assert all(props.get("text") != "loading" for props in backend.created), "no fallback commit"
    result.unmount()


def test_async_component_with_pending_await_shows_fallback_then_content() -> None:
    @component
    async def Slow() -> Element:
        await asyncio.sleep(0.01)
        return Text("slow")

    result = render(Suspense(Slow(), fallback=Text("loading")), settle_first=False)
    assert result.text() == ["loading"]
    result.settle()
    assert result.text() == ["slow"]
    result.unmount()


def test_async_component_first_step_runs_with_the_application_loop_bound() -> None:
    """The eager first step runs outside a running loop in headless tests; loop-bound awaits still work."""

    @component
    async def Waits() -> Element:
        event = asyncio.Event()
        asyncio.get_running_loop().call_later(0.005, event.set)
        await event.wait()
        return Text("done")

    result = render(Suspense(Waits(), fallback=Text("loading")), settle_first=False)
    assert result.text() == ["loading"]
    result.settle()
    assert result.text() == ["done"]
    result.unmount()


# ======================================================================
# Render storms
# ======================================================================


def test_render_storm_raises_from_the_offending_component() -> None:
    @component
    def Storm() -> Element:
        count, set_count = use_state(0)
        use_effect(lambda: set_count(count + 1))
        return Text(str(count))

    rec = Reconciler(FakeBackend())
    with pytest.raises(RuntimeError, match="Too many re-renders: Storm"):
        rec.mount(Column(Storm()))


def test_render_storm_routes_through_error_boundary() -> None:
    @component
    def Storm() -> Element:
        count, set_count = use_state(0)
        use_effect(lambda: set_count(count + 1))
        return Text(str(count))

    result = render(Column(Text("ok"), ErrorBoundary(Storm(), fallback=lambda exc: Text(str(exc)))))
    assert result.text()[0] == "ok"
    assert result.text()[1].startswith("Too many re-renders: Storm")
    result.unmount()


def test_render_storm_limit_allows_long_but_finite_chains() -> None:
    @component
    def Settles() -> Element:
        count, set_count = use_state(0)
        use_effect(lambda: count < MAX_RENDER_PASSES - 5 and set_count(count + 1))
        return Text(str(count))

    result = render(Settles())
    assert result.text() == [str(MAX_RENDER_PASSES - 5)]
    result.unmount()


def test_only_one_render_storm_guard_exists() -> None:
    import pythonnative.hosts.base as hosts_base
    import pythonnative.reconciler.core as core

    assert not hasattr(hosts_base, "MAX_RENDER_PASSES")
    assert core.MAX_RENDER_PASSES == MAX_RENDER_PASSES == 50


# ======================================================================
# Dev warnings
# ======================================================================


def _warning_containing(text: str) -> str:
    matches = [w for w in diagnostics.get_warnings() if text in w]
    assert matches, f"no warning mentions {text!r}: {diagnostics.get_warnings()}"
    return matches[0]


def test_warns_on_unkeyed_dynamic_sibling_list(dev_mode: Any) -> None:
    @component
    def Rows() -> Any:
        return [Text(str(i)) for i in range(3)]

    result = render(Column(Rows()))
    assert "Rows rendered a list of 3 sibling elements without keys" in _warning_containing("without keys")
    result.unmount()


def test_no_unkeyed_warning_for_positional_children_or_keyed_lists(dev_mode: Any) -> None:
    @component
    def Rows() -> Any:
        return [Text(str(i), key=str(i)) for i in range(3)]

    result = render(Column(Text("a"), Text("b"), Rows()))
    assert not [w for w in diagnostics.get_warnings() if "without keys" in w]
    result.unmount()


def test_warns_on_nested_unkeyed_list_among_children(dev_mode: Any) -> None:
    result = render(Column([Text("a"), Text("b")]))  # type: ignore[arg-type]
    assert "Column" in _warning_containing("without keys")
    result.unmount()


def test_warns_on_setter_after_unmount(dev_mode: Any) -> None:
    setters: Dict[str, Any] = {}

    @component
    def Gone() -> Element:
        value, set_value = use_state(0)
        setters["set"] = set_value
        return Text(str(value))

    result = render(Gone())
    result.unmount()
    setters["set"](1)
    runtime.drain(0.2)
    assert "Gone" in _warning_containing("after the component unmounted")


def test_warns_on_setter_during_own_render(dev_mode: Any) -> None:
    @component
    def Eager() -> Element:
        value, set_value = use_state(0)
        if value == 0:
            set_value(1)
        return Text(str(value))

    result = render(Eager())
    assert "Eager" in _warning_containing("during its own render")
    result.unmount()


def test_warns_on_setter_with_same_mutable_object(dev_mode: Any) -> None:
    setters: Dict[str, Any] = {}

    @component
    def Items() -> Element:
        items, set_items = use_state(lambda: ["a"])
        setters["set"] = set_items
        setters["items"] = items
        return Text(",".join(items))

    result = render(Items())
    setters["items"].append("b")
    setters["set"](setters["items"])
    result.settle()
    assert result.text() == ["a"], "in-place mutation never re-renders"
    assert "same list object" in _warning_containing("In-place mutation never re-renders")
    result.unmount()


def test_warns_when_deps_length_changes(dev_mode: Any) -> None:
    setters: Dict[str, Any] = {}

    @component
    def Deps() -> Element:
        count, set_count = use_state(0)
        setters["set"] = set_count
        use_effect(lambda: None, [count] if count == 0 else [count, "extra"])
        return Text(str(count))

    result = render(Deps())
    setters["set"](1)
    result.settle()
    assert "Deps passed 2 dependencies to use_effect but 1 on the previous render" in _warning_containing(
        "dependencies to use_effect"
    )
    result.unmount()


def test_dev_warnings_are_silent_in_production() -> None:
    diagnostics.set_dev_mode(False)
    diagnostics.clear_warnings()

    @component
    def Rows() -> Any:
        return [Text(str(i)) for i in range(3)]

    result = render(Column(Rows()))
    assert diagnostics.get_warnings() == []
    result.unmount()


# ======================================================================
# Typing helpers
# ======================================================================


def test_component_keyed_attaches_key_and_keeps_signature() -> None:
    @component
    def Row(label: str, bold: bool = False) -> Element:
        return Text(label)

    el = Row.keyed(7)("a", bold=True)
    assert el.type is Row
    assert el.key == "7"
    assert el.props == {"label": "a", "bold": True}
    assert Row.keyed(None)("x").key is None
    assert Row("plain", key="k").key == "k", "key= is still accepted at runtime"


def test_use_reducer_and_deps_accept_tuples() -> None:
    def reducer(state: int, action: str) -> int:
        return state + 1 if action == "inc" else state

    def hook() -> Any:
        state, dispatch = pn.use_reducer(reducer, lambda: 5)
        memo = use_memo(lambda: state * 2, (state,))
        use_effect(lambda: None, ())
        return state, dispatch, memo

    result = render_hook(hook)
    state, dispatch, memo = result.current
    assert (state, memo) == (5, 10)
    result.act(lambda: dispatch("inc"))
    assert result.current[0] == 6 and result.current[2] == 12
    result.unmount()


def test_use_ref_initial_value_and_use_color_scheme_literal() -> None:
    result = render_hook(lambda: (use_ref(3), pn.use_color_scheme()))
    ref, scheme = result.current
    assert ref.current == 3
    assert scheme in ("light", "dark")
    result.unmount()


def test_provider_value_is_keyword_only() -> None:
    ctx = pn.create_context("default")
    with pytest.raises(TypeError):
        ctx.Provider("value", Text("x"))  # type: ignore[call-arg]
    el = ctx.Provider(Text("x"), value="value")
    assert el.props == {"value": "value"}


# ======================================================================
# Journal hot path
# ======================================================================


def test_vnode_writes_skip_the_journal_when_no_pass_is_recording(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[Any] = []
    monkeypatch.setattr(journal, "record_attribute", lambda obj, name: calls.append(name))
    assert journal.journal_active is False
    node = VNode(Element("Text", {"text": "x"}, []))
    for _ in range(1000):
        node.children = []
        node.tag = 1
        node.last_frame = (0.0, 0.0, 1.0, 1.0)
    ref: Ref[Any] = Ref(0)
    ref.current = 1
    assert calls == []


def test_journal_records_only_structural_fields_while_active(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []
    monkeypatch.setattr(journal, "record_attribute", lambda obj, name: calls.append(name))
    token = journal.install(journal.Journal())
    try:
        assert journal.journal_active is True
        node = VNode(Element("Text", {"text": "x"}, []))
        calls.clear()
        node.children = []
        node.last_frame = (0.0, 0.0, 1.0, 1.0)
        node.layout_dirty = True
        node.measure_cache = None
        node.element = Element("Text", {"text": "y"}, [])
    finally:
        journal.uninstall(token)
    assert calls == ["children", "element"]
    assert journal.journal_active is False


def test_failed_render_rolls_back_in_place_updates_and_ref_writes() -> None:
    state: Dict[str, Any] = {}

    @component
    def Owner(fail: bool) -> Element:
        reference = use_ref("before")
        state["reference"] = reference
        if fail:
            reference.current = "rejected"
            raise ValueError("failed")
        return Text(reference.current)

    result = render(Column(Text("old"), Owner(False)))
    with pytest.raises(ValueError, match="failed"):
        result.rerender(Column(Text("new"), Owner(True)))
    assert state["reference"].current == "before"
    assert result.reconciler.root.children[0].element.props["text"] == "old"
    assert result.text() == ["old", "before"]
    result.unmount()
