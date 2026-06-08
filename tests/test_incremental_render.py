"""Tests for local (dirty-tracked) re-rendering and measurement caching.

These exercise the incremental render path: a state change marks only
the owning component's subtree dirty, and
[`flush_dirty`][pythonnative.reconciler.Reconciler.flush_dirty]
re-renders just that subtree instead of the whole app. They also cover
the measurement cache that lets untouched leaves skip native
``measure_intrinsic`` calls across layout passes.
"""

from typing import Any, Dict, List, Tuple

from pythonnative.components import ErrorBoundary
from pythonnative.element import Element
from pythonnative.hooks import Provider, component, create_context, use_context, use_state
from pythonnative.reconciler import Reconciler


class MockView:
    _next_id = 0

    def __init__(self, type_name: str, props: Dict[str, Any]) -> None:
        MockView._next_id += 1
        self.id = MockView._next_id
        self.type_name = type_name
        self.props = dict(props)
        self.children: List["MockView"] = []
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


class MockBackend:
    """Records operations and counts intrinsic measurements per view."""

    _LEAF_INTRINSIC = {
        "Text": (60.0, 16.0),
        "Button": (80.0, 32.0),
    }

    def __init__(self) -> None:
        self.ops: List[Any] = []
        self.measure_calls: List[int] = []

    def create_view(self, type_name: str, props: Dict[str, Any]) -> MockView:
        view = MockView(type_name, props)
        self.ops.append(("create", type_name, view.id))
        return view

    def update_view(self, view: MockView, type_name: str, changed: Dict[str, Any]) -> None:
        view.props.update(changed)
        self.ops.append(("update", type_name, view.id, tuple(sorted(changed.keys()))))

    def add_child(self, parent: MockView, child: MockView, parent_type: str) -> None:
        parent.children.append(child)
        self.ops.append(("add_child", parent.id, child.id))

    def remove_child(self, parent: MockView, child: MockView, parent_type: str) -> None:
        parent.children = [c for c in parent.children if c.id != child.id]
        self.ops.append(("remove_child", parent.id, child.id))

    def insert_child(self, parent: MockView, child: MockView, parent_type: str, index: int) -> None:
        parent.children.insert(index, child)
        self.ops.append(("insert_child", parent.id, child.id, index))

    def set_frame(self, view: MockView, type_name: str, x: float, y: float, w: float, h: float) -> None:
        view.frame = (x, y, w, h)

    def measure_intrinsic(self, view: MockView, type_name: str, max_w: float, max_h: float) -> Tuple[float, float]:
        self.measure_calls.append(view.id)
        return self._LEAF_INTRINSIC.get(type_name, (0.0, 0.0))


def _make_reconciler() -> Tuple[Reconciler, MockBackend]:
    backend = MockBackend()
    rec = Reconciler(backend)
    # The screen host normally supplies this; tests drive flush_dirty by
    # hand so a no-op trigger is enough.
    rec._screen_re_render = lambda: None
    return rec, backend


# ======================================================================
# Local re-render
# ======================================================================


def test_flush_dirty_rerenders_only_dirty_component() -> None:
    render_counts = {"a": 0, "b": 0, "parent": 0}
    setters: Dict[str, Any] = {}

    @component
    def child(name: str = "") -> Element:
        render_counts[name] += 1
        value, set_value = use_state(0)
        setters[name] = set_value
        return Element("Text", {"text": f"{name}:{value}"}, [])

    @component
    def parent() -> Element:
        render_counts["parent"] += 1
        return Element(
            "Column",
            {},
            [child(name="a", key="a"), child(name="b", key="b")],
        )

    rec, _backend = _make_reconciler()
    rec.mount(parent())
    assert render_counts == {"a": 1, "b": 1, "parent": 1}

    # Change only child "a"'s state.
    setters["a"](1)
    rec.flush_dirty()

    assert render_counts["a"] == 2
    assert render_counts["b"] == 1, "sibling component must not re-render"
    assert render_counts["parent"] == 1, "ancestor must not re-render"


def test_flush_dirty_updates_only_the_changed_native_view() -> None:
    setters: Dict[str, Any] = {}

    @component
    def child(name: str = "") -> Element:
        value, set_value = use_state(0)
        setters[name] = set_value
        return Element("Text", {"text": f"{name}:{value}"}, [])

    @component
    def parent() -> Element:
        return Element("Column", {}, [child(name="a", key="a"), child(name="b", key="b")])

    rec, backend = _make_reconciler()
    column = rec.mount(parent())
    assert column.children[0].props["text"] == "a:0"
    assert column.children[1].props["text"] == "b:0"

    backend.ops.clear()
    setters["a"](7)
    rec.flush_dirty()

    assert column.children[0].props["text"] == "a:7"
    assert column.children[1].props["text"] == "b:0"
    # Only the "a" Text view should have been updated.
    updates = [op for op in backend.ops if op[0] == "update"]
    assert len(updates) == 1


def test_flush_dirty_batches_multiple_dirty_components() -> None:
    render_counts = {"a": 0, "b": 0}
    setters: Dict[str, Any] = {}

    @component
    def child(name: str = "") -> Element:
        render_counts[name] += 1
        value, set_value = use_state(0)
        setters[name] = set_value
        return Element("Text", {"text": f"{name}:{value}"}, [])

    @component
    def parent() -> Element:
        return Element("Column", {}, [child(name="a", key="a"), child(name="b", key="b")])

    rec, _backend = _make_reconciler()
    rec.mount(parent())

    setters["a"](1)
    setters["b"](1)
    rec.flush_dirty()

    assert render_counts == {"a": 2, "b": 2}


def test_flush_dirty_skips_descendant_already_covered_by_ancestor() -> None:
    render_counts = {"outer": 0, "inner": 0}
    setters: Dict[str, Any] = {}

    @component
    def inner() -> Element:
        render_counts["inner"] += 1
        value, set_inner = use_state(0)
        setters["inner"] = set_inner
        return Element("Text", {"text": f"inner:{value}"}, [])

    @component
    def outer() -> Element:
        render_counts["outer"] += 1
        value, set_outer = use_state(0)
        setters["outer"] = set_outer
        return Element("Column", {"text": str(value)}, [inner()])

    rec, _backend = _make_reconciler()
    rec.mount(outer())
    assert render_counts == {"outer": 1, "inner": 1}

    # Both dirty in the same pass; the ancestor re-render already
    # re-renders the descendant, so inner runs exactly once more.
    setters["outer"](1)
    setters["inner"](1)
    rec.flush_dirty()

    assert render_counts["outer"] == 2
    assert render_counts["inner"] == 2


def test_flush_dirty_preserves_provider_context() -> None:
    theme = create_context("light")
    seen: List[str] = []
    setters: Dict[str, Any] = {}

    @component
    def consumer() -> Element:
        t = use_context(theme)
        seen.append(t)
        _value, set_value = use_state(0)
        setters["x"] = set_value
        return Element("Text", {"text": t}, [])

    @component
    def app() -> Element:
        return Provider(theme, "dark", consumer())

    rec, _backend = _make_reconciler()
    rec.mount(app())
    assert seen[-1] == "dark"

    # A purely local re-render of the consumer must still resolve the
    # ancestor Provider's value (regression guard: without restoring the
    # ancestor context stack this would read the "light" default).
    setters["x"](1)
    rec.flush_dirty()
    assert seen[-1] == "dark"


def test_unmounted_component_setter_does_not_resurrect_subtree() -> None:
    setters: Dict[str, Any] = {}
    render_counts = {"child": 0}

    @component
    def child() -> Element:
        render_counts["child"] += 1
        value, set_value = use_state(0)
        setters["child"] = set_value
        return Element("Text", {"text": str(value)}, [])

    @component
    def parent(show: bool = True) -> Element:
        return Element("Column", {}, [child()] if show else [])

    rec, _backend = _make_reconciler()
    rec.mount(parent(show=True))
    assert render_counts["child"] == 1
    stale_setter = setters["child"]

    # Unmount the child via a full reconcile.
    rec.reconcile(parent(show=False))

    # A setter call from the now-unmounted child must be a safe no-op.
    stale_setter(5)
    rec.flush_dirty()
    assert render_counts["child"] == 1


# ======================================================================
# Error boundaries during local re-render
# ======================================================================


def test_local_rerender_error_is_caught_by_ancestor_boundary() -> None:
    setters: Dict[str, Any] = {}

    @component
    def risky() -> Element:
        value, set_value = use_state(0)
        setters["risky"] = set_value
        if value > 0:
            raise ValueError("boom")
        return Element("Text", {"text": "ok"}, [])

    @component
    def app() -> Element:
        return ErrorBoundary(risky(), fallback=lambda err: Element("Text", {"text": f"caught:{err}"}, []))

    rec, _backend = _make_reconciler()
    root = rec.mount(app())
    assert root.props["text"] == "ok"

    # The setter triggers a local re-render that throws; the enclosing
    # ErrorBoundary must catch it and mount the fallback.
    setters["risky"](1)
    rec.flush_dirty()
    assert rec._tree.native_view.props["text"].startswith("caught:")


def test_local_rerender_error_without_boundary_propagates() -> None:
    setters: Dict[str, Any] = {}

    @component
    def risky() -> Element:
        value, set_value = use_state(0)
        setters["risky"] = set_value
        if value > 0:
            raise ValueError("boom")
        return Element("Text", {"text": "ok"}, [])

    @component
    def app() -> Element:
        return Element("Column", {}, [risky()])

    rec, _backend = _make_reconciler()
    rec.mount(app())

    setters["risky"](1)
    try:
        rec.flush_dirty()
        raised = False
    except ValueError:
        raised = True
    assert raised, "error with no boundary must propagate out of flush_dirty"


# ======================================================================
# Measurement caching
# ======================================================================


def test_measurement_cache_skips_unchanged_leaves_across_layout_passes() -> None:
    rec, backend = _make_reconciler()
    rec.mount(
        Element(
            "Column",
            {},
            [Element("Text", {"text": "a"}, []), Element("Text", {"text": "b"}, [])],
        )
    )
    rec.set_viewport_size(300.0, 600.0)
    assert len(backend.measure_calls) == 2, "each leaf measured once on first layout"

    # A second layout pass over an unchanged tree must hit the cache.
    rec._run_layout()
    assert len(backend.measure_calls) == 2, "unchanged leaves must not re-measure"


def test_measurement_cache_invalidated_only_for_rerendered_leaf() -> None:
    setters: Dict[str, Any] = {}

    @component
    def child(name: str = "") -> Element:
        value, set_value = use_state(0)
        setters[name] = set_value
        return Element("Text", {"text": f"{name}:{value}"}, [])

    @component
    def parent() -> Element:
        return Element("Column", {}, [child(name="a", key="a"), child(name="b", key="b")])

    rec, backend = _make_reconciler()
    rec.mount(parent())
    rec.set_viewport_size(300.0, 600.0)

    a_view = rec._tree.native_view.children[0]
    b_view = rec._tree.native_view.children[1]
    assert sorted(backend.measure_calls) == sorted([a_view.id, b_view.id])

    backend.measure_calls.clear()
    setters["a"](1)
    rec.flush_dirty()

    # Only the re-rendered leaf produced a new Element identity, so only
    # it is re-measured; the untouched sibling stays cached.
    assert a_view.id in backend.measure_calls
    assert b_view.id not in backend.measure_calls
