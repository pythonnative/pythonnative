"""Unit tests for the reconciler using a mock native backend."""

from typing import Any, Dict, List, Tuple

import pytest

from pythonnative.element import Element
from pythonnative.hooks import component
from pythonnative.reconciler import Reconciler

# ======================================================================
# Mock backend
# ======================================================================


class MockView:
    """Simulates a native view for testing."""

    _next_id = 0

    def __init__(self, type_name: str, props: Dict[str, Any]) -> None:
        MockView._next_id += 1
        self.id = MockView._next_id
        self.type_name = type_name
        self.props = dict(props)
        self.children: List["MockView"] = []
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def __repr__(self) -> str:
        return f"MockView({self.type_name}#{self.id})"


class MockBackend:
    """Records operations for assertions."""

    # Default intrinsic size for content-bearing leaves (Text, Button, etc.).
    _LEAF_INTRINSIC = {
        "Text": (60.0, 16.0),
        "Button": (80.0, 32.0),
        "Image": (40.0, 40.0),
        "TextInput": (120.0, 32.0),
        "TabBar": (320.0, 49.0),
    }

    def __init__(self) -> None:
        self.ops: List[Any] = []

    def create_view(self, type_name: str, props: Dict[str, Any]) -> MockView:
        view = MockView(type_name, props)
        self.ops.append(("create", type_name, view.id))
        return view

    def update_view(self, native_view: MockView, type_name: str, changed_props: Dict[str, Any]) -> None:
        native_view.props.update(changed_props)
        self.ops.append(("update", type_name, native_view.id, tuple(sorted(changed_props.keys()))))

    def add_child(self, parent: MockView, child: MockView, parent_type: str) -> None:
        parent.children.append(child)
        self.ops.append(("add_child", parent.id, child.id))

    def remove_child(self, parent: MockView, child: MockView, parent_type: str) -> None:
        parent.children = [c for c in parent.children if c.id != child.id]
        self.ops.append(("remove_child", parent.id, child.id))

    def insert_child(self, parent: MockView, child: MockView, parent_type: str, index: int) -> None:
        parent.children.insert(index, child)
        self.ops.append(("insert_child", parent.id, child.id, index))

    def set_frame(
        self,
        native_view: MockView,
        type_name: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        native_view.frame = (x, y, width, height)
        self.ops.append(("set_frame", native_view.id, x, y, width, height))

    def measure_intrinsic(
        self,
        native_view: MockView,
        type_name: str,
        max_width: float,
        max_height: float,
    ) -> Tuple[float, float]:
        return self._LEAF_INTRINSIC.get(type_name, (0.0, 0.0))


# ======================================================================
# Tests: mount
# ======================================================================


def test_mount_single_element() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el = Element("Text", {"text": "hello"}, [])
    root = rec.mount(el)
    assert isinstance(root, MockView)
    assert root.type_name == "Text"
    assert root.props["text"] == "hello"


def test_mount_nested_elements() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el = Element(
        "Column",
        {},
        [
            Element("Text", {"text": "a"}, []),
            Element("Button", {"title": "b"}, []),
        ],
    )
    root = rec.mount(el)
    assert root.type_name == "Column"
    assert len(root.children) == 2
    assert root.children[0].type_name == "Text"
    assert root.children[1].type_name == "Button"


def test_mount_deeply_nested() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el = Element(
        "ScrollView",
        {},
        [
            Element(
                "Column",
                {},
                [
                    Element("Text", {"text": "deep"}, []),
                ],
            ),
        ],
    )
    root = rec.mount(el)
    assert root.children[0].children[0].props["text"] == "deep"


# ======================================================================
# Tests: reconcile (update props)
# ======================================================================


def test_reconcile_updates_props() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el1 = Element("Text", {"text": "hello"}, [])
    rec.mount(el1)

    backend.ops.clear()
    el2 = Element("Text", {"text": "world"}, [])
    rec.reconcile(el2)

    update_ops = [op for op in backend.ops if op[0] == "update"]
    assert len(update_ops) == 1
    assert "text" in update_ops[0][3]


def test_reconcile_no_change_no_update() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el = Element("Text", {"text": "same"}, [])
    rec.mount(el)

    backend.ops.clear()
    rec.reconcile(Element("Text", {"text": "same"}, []))

    update_ops = [op for op in backend.ops if op[0] == "update"]
    assert len(update_ops) == 0


# ======================================================================
# Tests: reconcile children (add / remove)
# ======================================================================


def test_reconcile_add_child() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el1 = Element("Column", {}, [Element("Text", {"text": "a"}, [])])
    root = rec.mount(el1)
    assert len(root.children) == 1

    backend.ops.clear()
    el2 = Element(
        "Column",
        {},
        [Element("Text", {"text": "a"}, []), Element("Text", {"text": "b"}, [])],
    )
    rec.reconcile(el2)

    assert len(root.children) == 2


def test_reconcile_remove_child() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el1 = Element(
        "Column",
        {},
        [Element("Text", {"text": "a"}, []), Element("Text", {"text": "b"}, [])],
    )
    root = rec.mount(el1)
    assert len(root.children) == 2

    backend.ops.clear()
    el2 = Element("Column", {}, [Element("Text", {"text": "a"}, [])])
    rec.reconcile(el2)

    assert len(root.children) == 1


def test_reconcile_replace_child_type() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el1 = Element("Column", {}, [Element("Text", {"text": "a"}, [])])
    root = rec.mount(el1)

    backend.ops.clear()
    el2 = Element("Column", {}, [Element("Button", {"title": "b"}, [])])
    rec.reconcile(el2)

    assert root.children[0].type_name == "Button"


# ======================================================================
# Tests: reconcile root type change
# ======================================================================


def test_reconcile_root_type_change() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el1 = Element("Text", {"text": "a"}, [])
    root1 = rec.mount(el1)

    el2 = Element("Button", {"title": "b"}, [])
    root2 = rec.reconcile(el2)
    assert root2.type_name == "Button"
    assert root2 is not root1


# ======================================================================
# Tests: callback props always counted as changed
# ======================================================================


def test_reconcile_callback_always_updated() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    cb1 = lambda: None  # noqa: E731
    cb2 = lambda: None  # noqa: E731
    el1 = Element("Button", {"title": "x", "on_click": cb1}, [])
    rec.mount(el1)

    backend.ops.clear()
    el2 = Element("Button", {"title": "x", "on_click": cb2}, [])
    rec.reconcile(el2)

    update_ops = [op for op in backend.ops if op[0] == "update"]
    assert len(update_ops) == 1
    assert "on_click" in update_ops[0][3]


# ======================================================================
# Tests: removed props signalled as None
# ======================================================================


def test_reconcile_removed_prop_becomes_none() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el1 = Element("Text", {"text": "hi", "color": "#FF0000"}, [])
    root = rec.mount(el1)

    backend.ops.clear()
    el2 = Element("Text", {"text": "hi"}, [])
    rec.reconcile(el2)

    update_ops = [op for op in backend.ops if op[0] == "update"]
    assert len(update_ops) == 1
    assert "color" in update_ops[0][3]
    assert root.props.get("color") is None


# ======================================================================
# Tests: complex multi-step reconciliation
# ======================================================================


def test_multiple_reconcile_cycles() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    rec.mount(Element("Column", {}, [Element("Text", {"text": "0"}, [])]))

    for i in range(1, 5):
        rec.reconcile(Element("Column", {}, [Element("Text", {"text": str(i)}, [])]))

    assert rec._tree is not None
    assert rec._tree.children[0].element.props["text"] == "4"


# ======================================================================
# Tests: key-based reconciliation
# ======================================================================


def test_keyed_children_preserve_identity() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    el1 = Element(
        "Column",
        {},
        [
            Element("Text", {"text": "A"}, [], key="a"),
            Element("Text", {"text": "B"}, [], key="b"),
            Element("Text", {"text": "C"}, [], key="c"),
        ],
    )
    root = rec.mount(el1)
    view_a = rec._tree.children[0].native_view
    view_b = rec._tree.children[1].native_view
    view_c = rec._tree.children[2].native_view

    backend.ops.clear()
    el2 = Element(
        "Column",
        {},
        [
            Element("Text", {"text": "C"}, [], key="c"),
            Element("Text", {"text": "A"}, [], key="a"),
            Element("Text", {"text": "B"}, [], key="b"),
        ],
    )
    rec.reconcile(el2)

    assert rec._tree.children[0].native_view is view_c
    assert rec._tree.children[1].native_view is view_a
    assert rec._tree.children[2].native_view is view_b

    # Native children must also reflect the new order
    assert root.children[0] is view_c
    assert root.children[1] is view_a
    assert root.children[2] is view_b


def test_keyed_children_remove_by_key() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    el1 = Element(
        "Column",
        {},
        [
            Element("Text", {"text": "A"}, [], key="a"),
            Element("Text", {"text": "B"}, [], key="b"),
            Element("Text", {"text": "C"}, [], key="c"),
        ],
    )
    rec.mount(el1)

    el2 = Element(
        "Column",
        {},
        [
            Element("Text", {"text": "A"}, [], key="a"),
            Element("Text", {"text": "C"}, [], key="c"),
        ],
    )
    rec.reconcile(el2)

    assert len(rec._tree.children) == 2
    assert rec._tree.children[0].element.key == "a"
    assert rec._tree.children[1].element.key == "c"


def test_keyed_children_insert_new() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    el1 = Element(
        "Column",
        {},
        [
            Element("Text", {"text": "A"}, [], key="a"),
            Element("Text", {"text": "C"}, [], key="c"),
        ],
    )
    rec.mount(el1)

    el2 = Element(
        "Column",
        {},
        [
            Element("Text", {"text": "A"}, [], key="a"),
            Element("Text", {"text": "B"}, [], key="b"),
            Element("Text", {"text": "C"}, [], key="c"),
        ],
    )
    rec.reconcile(el2)

    assert len(rec._tree.children) == 3
    assert rec._tree.children[1].element.key == "b"


# ======================================================================
# Tests: error boundaries
# ======================================================================


def test_error_boundary_catches_mount_error() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    def bad_component(**props: Any) -> Element:
        raise ValueError("boom")

    fallback = Element("Text", {"text": "error caught"}, [])
    child = Element(bad_component, {}, [])
    eb = Element("__ErrorBoundary__", {"__fallback__": fallback}, [child])

    root = rec.mount(eb)
    assert root.type_name == "Text"
    assert root.props["text"] == "error caught"


def test_error_boundary_callable_fallback() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    def bad_component(**props: Any) -> Element:
        raise RuntimeError("oops")

    def fallback_fn(exc: Exception) -> Element:
        return Element("Text", {"text": f"caught: {exc}"}, [])

    child = Element(bad_component, {}, [])
    eb = Element("__ErrorBoundary__", {"__fallback__": fallback_fn}, [child])

    root = rec.mount(eb)
    assert root.type_name == "Text"
    assert "caught: oops" in root.props["text"]


def test_error_boundary_no_error_renders_child() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    child = Element("Text", {"text": "ok"}, [])
    fallback = Element("Text", {"text": "error"}, [])
    eb = Element("__ErrorBoundary__", {"__fallback__": fallback}, [child])

    root = rec.mount(eb)
    assert root.type_name == "Text"
    assert root.props["text"] == "ok"


def test_error_boundary_catches_reconcile_error() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    call_count = [0]

    @component
    def flaky() -> Element:
        call_count[0] += 1
        if call_count[0] > 1:
            raise RuntimeError("reconcile boom")
        return Element("Text", {"text": "ok"}, [])

    def fallback_fn(exc: Exception) -> Element:
        return Element("Text", {"text": f"recovered: {exc}"}, [])

    eb1 = Element("__ErrorBoundary__", {"__fallback__": fallback_fn}, [flaky()])
    root = rec.mount(eb1)
    assert root.props["text"] == "ok"

    eb2 = Element("__ErrorBoundary__", {"__fallback__": fallback_fn}, [flaky()])
    root = rec.reconcile(eb2)
    assert "recovered" in root.props["text"]


def test_error_boundary_without_fallback_propagates() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)

    def bad(**props: Any) -> Element:
        raise ValueError("no fallback")

    child = Element(bad, {}, [])
    eb = Element("__ErrorBoundary__", {}, [child])

    with pytest.raises(ValueError, match="no fallback"):
        rec.mount(eb)


# ======================================================================
# Tests: post-render effect flushing
# ======================================================================


def test_effects_flushed_after_mount() -> None:
    calls: list = []

    @component
    def my_comp() -> Element:
        from pythonnative.hooks import use_effect

        use_effect(lambda: calls.append("mounted"), [])
        return Element("Text", {"text": "hi"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(my_comp())
    assert calls == ["mounted"]


def test_effects_flushed_after_reconcile() -> None:
    calls: list = []

    @component
    def my_comp(dep: int = 0) -> Element:
        from pythonnative.hooks import use_effect

        use_effect(lambda: calls.append(f"e{dep}"), [dep])
        return Element("Text", {"text": str(dep)}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(my_comp(dep=1))
    assert calls == ["e1"]

    rec.reconcile(my_comp(dep=2))
    assert calls == ["e1", "e2"]


def test_effect_cleanup_runs_on_rerun() -> None:
    log: list = []

    @component
    def my_comp(dep: int = 0) -> Element:
        from pythonnative.hooks import use_effect

        def effect() -> Any:
            log.append(f"run-{dep}")
            return lambda: log.append(f"cleanup-{dep}")

        use_effect(effect, [dep])
        return Element("Text", {"text": str(dep)}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(my_comp(dep=1))
    assert log == ["run-1"]

    rec.reconcile(my_comp(dep=2))
    assert log == ["run-1", "cleanup-1", "run-2"]


def test_provider_child_native_view_swap() -> None:
    """When a Provider wraps different component types across renders,
    the parent native container must swap the old native subview for the new one."""
    from pythonnative.hooks import Provider, create_context

    ctx = create_context(None)

    @component
    def CompA() -> Element:
        return Element("Text", {"text": "A"}, [])

    @component
    def CompB() -> Element:
        return Element("Text", {"text": "B"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)

    tree1 = Element("View", {}, [Provider(ctx, "v1", CompA())])
    root = rec.mount(tree1)
    assert len(root.children) == 1
    assert root.children[0].props["text"] == "A"
    old_child_id = root.children[0].id

    tree2 = Element("View", {}, [Provider(ctx, "v2", CompB())])
    rec.reconcile(tree2)
    assert len(root.children) == 1
    assert root.children[0].props["text"] == "B"
    assert root.children[0].id != old_child_id


# ======================================================================
# Tests: layout pass
# ======================================================================


def test_layout_pass_runs_after_mount_when_viewport_set() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(320, 480)

    el = Element(
        "Column",
        {"width": 320, "height": 480, "spacing": 4},
        [
            Element("View", {"height": 50}, []),
            Element("View", {"height": 80}, []),
        ],
    )
    rec.mount(el)

    set_frame_ops = [op for op in backend.ops if op[0] == "set_frame"]
    assert set_frame_ops, "Layout pass should emit set_frame ops"


def test_layout_pass_skipped_when_no_viewport() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el = Element("Column", {}, [Element("Text", {"text": "x"}, [])])
    rec.mount(el)
    set_frame_ops = [op for op in backend.ops if op[0] == "set_frame"]
    assert set_frame_ops == []


def test_layout_pass_positions_flex_children_in_row() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(300, 100)

    el = Element(
        "Row",
        {"flex_direction": "row", "width": 300, "height": 100},
        [
            Element("View", {"width": 80, "height": 40}, []),
            Element("View", {"flex": 1, "height": 40}, []),
            Element("View", {"width": 60, "height": 40}, []),
        ],
    )
    root = rec.mount(el)
    # The root view's frame is owned by the screen host (e.g., on iOS the root
    # is positioned below the top safe-area inset by ``_sync_root_frame``);
    # the layout engine intentionally leaves it untouched. Children are
    # positioned relative to the root's local origin.
    assert root.frame == (0.0, 0.0, 0.0, 0.0)
    assert root.children[0].frame == (0.0, 0.0, 80.0, 40.0)
    assert root.children[1].frame == (80.0, 0.0, 160.0, 40.0)
    assert root.children[2].frame == (240.0, 0.0, 60.0, 40.0)


def test_layout_pass_handles_absolute_positioning() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(400, 300)

    el = Element(
        "View",
        {"width": 400, "height": 300},
        [
            Element("View", {"height": 60}, []),
            Element(
                "View",
                {"position": "absolute", "top": 10, "right": 20, "width": 50, "height": 50},
                [],
            ),
        ],
    )
    root = rec.mount(el)
    flow_child, abs_child = root.children
    assert flow_child.frame[1] == 0
    assert abs_child.frame == (330.0, 10.0, 50.0, 50.0)


def test_layout_pass_handles_padding_and_align_items() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(200, 100)

    el = Element(
        "Column",
        {"width": 200, "height": 100, "padding": 8, "align_items": "center"},
        [Element("View", {"width": 40, "height": 30}, [])],
    )
    root = rec.mount(el)
    child = root.children[0]
    # Available cross axis after padding = 200 - 16 = 184; centered child
    # at x = 8 (pad_left) + (184 - 40) / 2 = 80
    assert child.frame == (80.0, 8.0, 40.0, 30.0)


def test_layout_pass_uses_intrinsic_text_size() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(300, 200)

    el = Element(
        "Column",
        {"width": 300, "height": 200, "align_items": "flex_start"},
        [Element("Text", {"text": "hi"}, [])],
    )
    root = rec.mount(el)
    text_view = root.children[0]
    # MockBackend.measure_intrinsic returns (60, 16) for Text.
    assert text_view.frame == (0.0, 0.0, 60.0, 16.0)


def test_layout_re_runs_on_reconcile() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(200, 100)

    el1 = Element("Row", {"width": 200, "height": 100}, [Element("View", {"width": 50, "height": 50}, [])])
    root = rec.mount(el1)
    assert root.children[0].frame == (0.0, 0.0, 50.0, 50.0)

    el2 = Element("Row", {"width": 200, "height": 100}, [Element("View", {"width": 100, "height": 60}, [])])
    rec.reconcile(el2)
    assert root.children[0].frame == (0.0, 0.0, 100.0, 60.0)


def test_set_viewport_size_triggers_layout_when_tree_exists() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    el = Element("Column", {"width": 100, "height": 50}, [Element("View", {"width": 30, "height": 20}, [])])
    rec.mount(el)
    assert all(op[0] != "set_frame" for op in backend.ops)

    rec.set_viewport_size(320, 480)
    assert any(op[0] == "set_frame" for op in backend.ops)


def test_set_viewport_size_idempotent() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(320, 480)
    rec.mount(Element("Column", {"width": 100, "height": 50}, [Element("View", {"width": 30, "height": 20}, [])]))
    n_frames_after_mount = sum(1 for op in backend.ops if op[0] == "set_frame")

    rec.set_viewport_size(320, 480)
    n_frames_after_dup = sum(1 for op in backend.ops if op[0] == "set_frame")
    assert n_frames_after_mount == n_frames_after_dup


def test_set_viewport_size_rejects_non_positive() -> None:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(0, 0)
    rec.set_viewport_size(-100, 100)
    rec.mount(Element("Column", {"width": 100, "height": 50}, []))
    assert all(op[0] != "set_frame" for op in backend.ops)


def test_layout_pass_gives_tabbar_intrinsic_height() -> None:
    """Regression: TabBar inside a flex:1 column must get its intrinsic height.

    The hello-world tab navigator renders ``View(flex_direction=column,
    flex=1)`` containing a ``View(flex=1)`` content area and a ``TabBar``
    leaf. Without an intrinsic-size measure on TabBar the bar collapses
    to height 0 and disappears from the screen.
    """
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(320, 600)

    el = Element(
        "View",
        {"flex_direction": "column", "flex": 1},
        [
            Element("View", {"flex": 1}, []),
            Element("TabBar", {"items": [{"name": "a", "title": "A"}]}, []),
        ],
    )
    root = rec.mount(el)
    content_view, tab_bar = root.children
    # MockBackend reports TabBar intrinsic = (320, 49); the bar must
    # take that height and the content view must fill the rest.
    assert tab_bar.frame[3] == 49.0, "TabBar must keep its intrinsic 49pt height"
    assert tab_bar.frame[1] == 600.0 - 49.0, "TabBar must sit at the bottom of the viewport"
    assert content_view.frame[3] == 600.0 - 49.0, "Content area must fill the rest"


def test_layout_pass_uses_intrinsic_button_size() -> None:
    """Regression: a Button with no explicit width/height must measure non-zero.

    Mirrors the iOS ``UIButton`` issue where the buttons in the
    hello-world card became invisible because their intrinsic size
    came back as ``(0, 0)``.
    """
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(320, 600)

    el = Element(
        "Column",
        {"width": 320, "height": 200, "padding": 16, "align_items": "center"},
        [
            Element(
                "Row",
                {"flex_direction": "row", "spacing": 8},
                [
                    Element("Button", {"title": "Tap me"}, []),
                    Element("Button", {"title": "Reset"}, []),
                ],
            )
        ],
    )
    root = rec.mount(el)
    row = root.children[0]
    btn_a, btn_b = row.children
    # MockBackend reports Button intrinsic = (80, 32).
    assert btn_a.frame[2] > 0 and btn_a.frame[3] > 0, "Buttons must have non-zero size"
    assert btn_a.frame[2:] == (80.0, 32.0)
    assert btn_b.frame[2:] == (80.0, 32.0)


def test_spacer_with_size_prop_takes_that_dimension() -> None:
    """Regression: ``pn.Spacer(size=16)`` must reserve real space, not zero.

    The component-level ``Spacer`` accepts a ``size`` kwarg that is
    forwarded as a prop; the layout engine only knows ``width`` /
    ``height``, so the factory must translate the prop. Without the
    translation a fixed-size spacer collapses to 0 and any siblings
    relying on it for visual separation get bunched together.
    """
    import pythonnative as pn

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.set_viewport_size(320, 600)

    el = Element(
        "Row",
        {"flex_direction": "row", "width": 320, "height": 50},
        [
            Element("View", {"width": 40, "height": 40}, []),
            pn.Spacer(size=24),
            Element("View", {"width": 40, "height": 40}, []),
        ],
    )
    root = rec.mount(el)
    a, spacer, b = root.children
    assert spacer.frame[2] == 24.0, "Spacer(size=24) must take 24pt on the row's main axis"
    assert b.frame[0] == a.frame[2] + spacer.frame[2], "Sibling sits after spacer"


# ======================================================================
# Fragment (transparent grouping element)
# ======================================================================


def test_fragment_flattens_into_parent() -> None:
    """A Fragment inside a parent contributes its children at the parent level."""
    import pythonnative as pn

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(
        Element(
            "Column",
            {},
            [
                Element("Text", {"text": "before"}, []),
                pn.Fragment(
                    Element("Text", {"text": "frag-a"}, []),
                    Element("Text", {"text": "frag-b"}, []),
                ),
                Element("Text", {"text": "after"}, []),
            ],
        )
    )
    # Find the Column view and assert it received 4 direct children.
    create_ops = [op for op in backend.ops if op[0] == "create"]
    column_id = next(op[2] for op in create_ops if op[1] == "Column")
    add_to_column = [op for op in backend.ops if op[0] == "add_child" and op[1] == column_id]
    assert len(add_to_column) == 4, "Fragment should be transparent and contribute 2 children directly"


def test_fragment_reconciles_keyed_siblings() -> None:
    """Reordering keyed children inside a Fragment moves rather than recreates."""
    import pythonnative as pn

    @component
    def row(reversed_order: bool = False) -> Element:
        items: list[Element] = [
            Element("Text", {"text": "A"}, [], key="a"),
            Element("Text", {"text": "B"}, [], key="b"),
        ]
        if reversed_order:
            items.reverse()
        return Element("Column", {}, [pn.Fragment(*items)])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(row(reversed_order=False))

    create_ops_before = [op for op in backend.ops if op[0] == "create"]
    backend.ops.clear()

    rec.reconcile(row(reversed_order=True))

    create_ops_after = [op for op in backend.ops if op[0] == "create"]
    assert create_ops_after == [], "Reordering keyed children inside Fragment must not recreate views"
    assert any(op[0] in ("insert_child", "add_child", "remove_child") for op in backend.ops)
    # Two Text views existed before; no new ones should have been added.
    assert sum(1 for op in create_ops_before if op[1] == "Text") == 2
