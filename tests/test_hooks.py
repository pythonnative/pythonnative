"""Unit tests for function components and hooks."""

from typing import Any, Dict, List

from pythonnative.element import Element
from pythonnative.hooks import (
    HookState,
    NavigationHandle,
    Provider,
    _NavigationContext,
    _set_hook_state,
    batch_updates,
    component,
    create_context,
    use_callback,
    use_context,
    use_effect,
    use_memo,
    use_navigation,
    use_reducer,
    use_ref,
    use_state,
)
from pythonnative.reconciler import Reconciler

# ======================================================================
# Mock backend (shared with test_reconciler)
# ======================================================================


class MockView:
    _next_id = 0

    def __init__(self, type_name: str, props: Dict[str, Any]) -> None:
        MockView._next_id += 1
        self.id = MockView._next_id
        self.type_name = type_name
        self.props = dict(props)
        self.children: List["MockView"] = []


class MockBackend:
    def __init__(self) -> None:
        self.ops: List[Any] = []

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


# ======================================================================
# use_state
# ======================================================================


def test_use_state_returns_initial_value() -> None:
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        val, setter = use_state(42)
        assert val == 42
    finally:
        _set_hook_state(None)


def test_use_state_lazy_initialiser() -> None:
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        val, _ = use_state(lambda: 99)
        assert val == 99
    finally:
        _set_hook_state(None)


def test_use_state_setter_triggers_render() -> None:
    renders = []
    ctx = HookState()
    ctx._trigger_render = lambda: renders.append(1)
    _set_hook_state(ctx)
    try:
        val, setter = use_state(0)
        setter(1)
        assert len(renders) == 1
        assert ctx.states[0] == 1
    finally:
        _set_hook_state(None)


def test_use_state_setter_functional_update() -> None:
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        _, setter = use_state(10)
        _set_hook_state(None)
        setter(lambda prev: prev + 5)
        assert ctx.states[0] == 15
    finally:
        _set_hook_state(None)


# ======================================================================
# use_reducer
# ======================================================================


def test_use_reducer_returns_initial_state() -> None:
    def reducer(state: int, action: str) -> int:
        return state

    ctx = HookState()
    _set_hook_state(ctx)
    try:
        state, dispatch = use_reducer(reducer, 42)
        assert state == 42
    finally:
        _set_hook_state(None)


def test_use_reducer_lazy_initial_state() -> None:
    def reducer(state: int, action: str) -> int:
        return state

    ctx = HookState()
    _set_hook_state(ctx)
    try:
        state, _ = use_reducer(reducer, lambda: 99)
        assert state == 99
    finally:
        _set_hook_state(None)


def test_use_reducer_dispatch_triggers_render() -> None:
    renders: list = []

    def reducer(state: int, action: str) -> int:
        if action == "increment":
            return state + 1
        if action == "reset":
            return 0
        return state

    ctx = HookState()
    ctx._trigger_render = lambda: renders.append(1)
    _set_hook_state(ctx)
    try:
        state, dispatch = use_reducer(reducer, 0)
        dispatch("increment")
        assert ctx.states[0] == 1
        assert len(renders) == 1
        dispatch("increment")
        assert ctx.states[0] == 2
        assert len(renders) == 2
        dispatch("reset")
        assert ctx.states[0] == 0
        assert len(renders) == 3
    finally:
        _set_hook_state(None)


def test_use_reducer_no_render_on_same_state() -> None:
    renders: list = []

    def reducer(state: int, action: str) -> int:
        return state

    ctx = HookState()
    ctx._trigger_render = lambda: renders.append(1)
    _set_hook_state(ctx)
    try:
        _, dispatch = use_reducer(reducer, 5)
        dispatch("noop")
        assert len(renders) == 0
    finally:
        _set_hook_state(None)


def test_use_reducer_in_reconciler() -> None:
    captured_dispatch: list = [None]

    def reducer(state: int, action: str) -> int:
        if action == "increment":
            return state + 1
        return state

    @component
    def counter() -> Element:
        count, dispatch = use_reducer(reducer, 0)
        captured_dispatch[0] = dispatch
        return Element("Text", {"text": str(count)}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    re_rendered: list = []
    rec._screen_re_render = lambda: re_rendered.append(1)

    root = rec.mount(counter())
    assert root.props["text"] == "0"

    dispatch_fn = captured_dispatch[0]
    assert dispatch_fn is not None
    dispatch_fn("increment")
    assert len(re_rendered) == 1


# ======================================================================
# use_effect (deferred execution)
# ======================================================================


def test_use_effect_is_deferred() -> None:
    """Effects are queued during render, not run immediately."""
    calls: list = []
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        use_effect(lambda: calls.append("mounted"), [])
        assert calls == [], "Effect should NOT run during render"
    finally:
        _set_hook_state(None)

    ctx.flush_pending_effects()
    assert calls == ["mounted"], "Effect should run after flush"


def test_use_effect_cleanup_on_rerun() -> None:
    cleanups: list = []

    def make_effect(label: str):  # type: ignore[no-untyped-def]
        def effect() -> Any:
            return lambda: cleanups.append(label)

        return effect

    ctx = HookState()

    _set_hook_state(ctx)
    try:
        use_effect(make_effect("first"), None)
    finally:
        _set_hook_state(None)
    ctx.flush_pending_effects()

    ctx.reset_index()
    _set_hook_state(ctx)
    try:
        use_effect(make_effect("second"), None)
    finally:
        _set_hook_state(None)
    ctx.flush_pending_effects()

    assert "first" in cleanups


def test_use_effect_skips_with_same_deps() -> None:
    calls: list = []
    ctx = HookState()

    _set_hook_state(ctx)
    try:
        use_effect(lambda: calls.append("run"), [1, 2])
    finally:
        _set_hook_state(None)
    ctx.flush_pending_effects()

    ctx.reset_index()
    _set_hook_state(ctx)
    try:
        use_effect(lambda: calls.append("run"), [1, 2])
    finally:
        _set_hook_state(None)
    ctx.flush_pending_effects()

    assert calls == ["run"]


def test_use_effect_runs_after_reconciler_mount() -> None:
    """Effects run automatically after Reconciler.mount() completes."""
    calls: list = []

    @component
    def my_comp() -> Element:
        use_effect(lambda: calls.append("effect"), [])
        return Element("Text", {"text": "hi"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(my_comp())
    assert calls == ["effect"]


def test_use_effect_runs_after_reconciler_reconcile() -> None:
    """Effects run automatically after Reconciler.reconcile() completes."""
    calls: list = []

    @component
    def my_comp(dep: int = 0) -> Element:
        use_effect(lambda: calls.append(f"effect-{dep}"), [dep])
        return Element("Text", {"text": str(dep)}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(my_comp(dep=0))
    assert calls == ["effect-0"]

    rec.reconcile(my_comp(dep=1))
    assert calls == ["effect-0", "effect-1"]


def test_use_effect_cleanup_on_unmount() -> None:
    """Cleanup functions run when component is destroyed."""
    cleanups: list = []
    ctx = HookState()

    _set_hook_state(ctx)
    try:
        use_effect(lambda: (lambda: cleanups.append("cleaned")), [])
    finally:
        _set_hook_state(None)
    ctx.flush_pending_effects()

    assert cleanups == []
    ctx.cleanup_all_effects()
    assert cleanups == ["cleaned"]


# ======================================================================
# batch_updates
# ======================================================================


def test_batch_updates_defers_render() -> None:
    renders: list = []
    ctx = HookState()
    ctx._trigger_render = lambda: renders.append(1)
    _set_hook_state(ctx)
    try:
        _, set_a = use_state(0)
        _, set_b = use_state(0)
    finally:
        _set_hook_state(None)

    with batch_updates():
        set_a(1)
        set_b(2)
        assert len(renders) == 0, "Render should be deferred inside batch"

    assert len(renders) == 1, "Exactly one render after batch exits"


def test_batch_updates_nested() -> None:
    renders: list = []
    ctx = HookState()
    ctx._trigger_render = lambda: renders.append(1)
    _set_hook_state(ctx)
    try:
        _, set_a = use_state(0)
        _, set_b = use_state(0)
    finally:
        _set_hook_state(None)

    with batch_updates():
        set_a(1)
        with batch_updates():
            set_b(2)
            assert len(renders) == 0
        assert len(renders) == 0, "Nested batch should not trigger render"

    assert len(renders) == 1


def test_batch_updates_no_render_when_unchanged() -> None:
    renders: list = []
    ctx = HookState()
    ctx._trigger_render = lambda: renders.append(1)
    _set_hook_state(ctx)
    try:
        _, set_a = use_state(5)
    finally:
        _set_hook_state(None)

    with batch_updates():
        set_a(5)

    assert len(renders) == 0


# ======================================================================
# use_memo / use_callback
# ======================================================================


def test_use_memo_caches() -> None:
    calls: list = []
    ctx = HookState()

    def factory_a() -> int:
        calls.append(1)
        return 42

    def factory_b() -> int:
        calls.append(1)
        return 99

    _set_hook_state(ctx)
    try:
        val1 = use_memo(factory_a, [1])
    finally:
        _set_hook_state(None)

    ctx.reset_index()
    _set_hook_state(ctx)
    try:
        val2 = use_memo(factory_b, [1])
    finally:
        _set_hook_state(None)

    assert val1 == 42
    assert val2 == 42
    assert len(calls) == 1


def test_use_memo_recomputes_on_dep_change() -> None:
    ctx = HookState()

    _set_hook_state(ctx)
    try:
        val1 = use_memo(lambda: "first", ["a"])
    finally:
        _set_hook_state(None)

    ctx.reset_index()
    _set_hook_state(ctx)
    try:
        val2 = use_memo(lambda: "second", ["b"])
    finally:
        _set_hook_state(None)

    assert val1 == "first"
    assert val2 == "second"


def test_use_callback_returns_stable_reference() -> None:
    ctx = HookState()
    fn = lambda: None  # noqa: E731

    _set_hook_state(ctx)
    try:
        cb1 = use_callback(fn, [1])
    finally:
        _set_hook_state(None)

    ctx.reset_index()
    _set_hook_state(ctx)
    try:
        cb2 = use_callback(lambda: None, [1])
    finally:
        _set_hook_state(None)

    assert cb1 is fn
    assert cb2 is fn


# ======================================================================
# use_ref
# ======================================================================


def test_use_ref_persists() -> None:
    ctx = HookState()
    _set_hook_state(ctx)
    try:
        ref = use_ref(0)
        assert ref["current"] == 0
        ref["current"] = 5
    finally:
        _set_hook_state(None)

    ctx.reset_index()
    _set_hook_state(ctx)
    try:
        ref2 = use_ref(0)
        assert ref2["current"] == 5
        assert ref2 is ref
    finally:
        _set_hook_state(None)


# ======================================================================
# Context
# ======================================================================


def test_create_context_default() -> None:
    ctx = create_context("default_val")
    assert ctx._current() == "default_val"


def test_context_stack() -> None:
    ctx = create_context("default")
    ctx._stack.append("override")
    assert ctx._current() == "override"
    ctx._stack.pop()
    assert ctx._current() == "default"


def test_use_context_reads_current() -> None:
    my_ctx = create_context("fallback")
    my_ctx._stack.append("active")
    hook_state = HookState()
    _set_hook_state(hook_state)
    try:
        val = use_context(my_ctx)
        assert val == "active"
    finally:
        _set_hook_state(None)
        my_ctx._stack.pop()


# ======================================================================
# @component decorator
# ======================================================================


def test_component_decorator_creates_element() -> None:
    @component
    def my_comp(label: str = "hello") -> Element:
        return Element("Text", {"text": label}, [])

    el = my_comp(label="world")
    assert isinstance(el, Element)
    assert el.type is getattr(my_comp, "__wrapped__")
    assert el.props == {"label": "world"}


def test_component_with_positional_args() -> None:
    @component
    def greeting(name: str, age: int = 0) -> Element:
        return Element("Text", {"text": f"{name}, {age}"}, [])

    el = greeting("Alice", age=30)
    assert el.props == {"name": "Alice", "age": 30}


def test_component_key_extraction() -> None:
    @component
    def widget(text: str = "") -> Element:
        return Element("Text", {"text": text}, [])

    el = widget(text="hi", key="k1")
    assert el.key == "k1"
    assert "key" not in el.props


# ======================================================================
# Function components in reconciler
# ======================================================================


def test_reconciler_mounts_function_component() -> None:
    @component
    def greeting(name: str = "World") -> Element:
        return Element("Text", {"text": f"Hello {name}"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    root = rec.mount(greeting(name="Python"))
    assert root.type_name == "Text"
    assert root.props["text"] == "Hello Python"


def test_reconciler_reconciles_function_component() -> None:
    @component
    def display(value: int = 0) -> Element:
        return Element("Text", {"text": str(value)}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(display(value=1))

    backend.ops.clear()
    rec.reconcile(display(value=2))

    update_ops = [op for op in backend.ops if op[0] == "update"]
    assert len(update_ops) == 1
    assert "text" in update_ops[0][3]


def test_function_component_use_state() -> None:
    render_count = [0]
    captured_setter: list = [None]

    @component
    def counter() -> Element:
        count, set_count = use_state(0)
        render_count[0] += 1
        captured_setter[0] = set_count
        return Element("Text", {"text": str(count)}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    re_rendered: list = []
    rec._screen_re_render = lambda: re_rendered.append(1)

    root = rec.mount(counter())
    assert root.props["text"] == "0"
    assert render_count[0] == 1

    setter_fn = captured_setter[0]
    assert setter_fn is not None
    setter_fn(5)
    assert len(re_rendered) == 1


def test_function_component_preserves_state_across_reconcile() -> None:
    @component
    def stateful(label: str = "") -> Element:
        count, set_count = use_state(0)
        return Element("Text", {"text": f"{label}:{count}"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(stateful(label="A"))

    tree_node = rec._tree
    assert tree_node is not None
    assert tree_node.hook_state is not None
    tree_node.hook_state.states[0] = 42

    rec.reconcile(stateful(label="B"))
    assert rec._tree is not None
    assert rec._tree.hook_state is not None
    assert rec._tree.hook_state.states[0] == 42


# ======================================================================
# Provider in reconciler
# ======================================================================


def test_provider_in_reconciler() -> None:
    theme = create_context("light")

    @component
    def themed() -> Element:
        t = use_context(theme)
        return Element("Text", {"text": t}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    el = Provider(theme, "dark", themed())
    root = rec.mount(el)
    assert root.props["text"] == "dark"


# ======================================================================
# use_navigation
# ======================================================================


def test_use_navigation_reads_context() -> None:
    class FakeHost:
        def _get_nav_args(self) -> dict:
            return {"id": 42}

        def _push(self, page: Any, args: Any = None) -> None:
            pass

        def _pop(self) -> None:
            pass

    handle = NavigationHandle(FakeHost())
    _NavigationContext._stack.append(handle)
    hook_state = HookState()
    _set_hook_state(hook_state)
    try:
        nav = use_navigation()
        assert nav is handle
        assert nav.get_params() == {"id": 42}
    finally:
        _set_hook_state(None)
        _NavigationContext._stack.pop()


def test_navigation_handle_methods() -> None:
    pushed: list = []
    popped: list = []

    class FakeHost:
        def _push(self, page: Any, args: Any = None) -> None:
            pushed.append((page, args))

        def _pop(self) -> None:
            popped.append(1)

        def _get_nav_args(self) -> dict:
            return {"key": "value"}

    handle = NavigationHandle(FakeHost())

    handle.navigate("SomePage", params={"x": 1})
    assert pushed == [("SomePage", {"x": 1})]

    handle.go_back()
    assert len(popped) == 1

    assert handle.get_params() == {"key": "value"}
