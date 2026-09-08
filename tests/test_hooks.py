"""Unit tests for function components and hooks."""

from contextlib import contextmanager
from typing import Any, Iterator

from pythonnative.component import Component, component, memo
from pythonnative.element import Element
from pythonnative.hooks import (
    HookState,
    create_context,
    current_hook_state,
    install_hook_state,
    restore_hook_state,
    use_callback,
    use_context,
    use_effect,
    use_memo,
    use_reducer,
    use_ref,
    use_state,
)
from pythonnative.reconciler import Reconciler
from pythonnative.scheduler import batch_updates
from pythonnative.testing import FakeBackend as MockBackend
from pythonnative.testing import render, render_hook


@contextmanager
def _rendering(state: HookState) -> Iterator[None]:
    """Run a bare render pass against ``state`` (no reconciler involved)."""
    state.begin_render()
    token = install_hook_state(state)
    try:
        yield
        state.finish_render()
    finally:
        restore_hook_state(token)


# ======================================================================
# use_state
# ======================================================================


def test_use_state_returns_initial_value() -> None:
    result = render_hook(lambda: use_state(42))
    val, setter = result.current
    assert val == 42
    assert callable(setter)


def test_use_state_lazy_initialiser() -> None:
    calls: list = []

    def init() -> int:
        calls.append(1)
        return 99

    result = render_hook(lambda: use_state(init))
    assert result.current[0] == 99
    result.rerender()
    assert result.current[0] == 99
    assert len(calls) == 1, "lazy initialiser runs once"


def test_use_state_setter_triggers_render() -> None:
    result = render_hook(lambda: use_state(0))
    assert result.render_count == 1

    _, setter = result.current
    result.act(lambda: setter(1))
    assert result.render_count == 2
    assert result.current[0] == 1


def test_use_state_setter_functional_update() -> None:
    result = render_hook(lambda: use_state(10))
    _, setter = result.current
    result.act(lambda: setter(lambda prev: prev + 5))
    assert result.current[0] == 15


def test_use_state_outside_component_raises() -> None:
    assert current_hook_state() is None
    try:
        use_state(0)
    except RuntimeError as exc:
        assert "use_state" in str(exc)
    else:
        raise AssertionError("use_state outside a component should raise")


# ======================================================================
# use_reducer
# ======================================================================


def test_use_reducer_returns_initial_state() -> None:
    def reducer(state: int, action: str) -> int:
        return state

    result = render_hook(lambda: use_reducer(reducer, 42))
    state, dispatch = result.current
    assert state == 42
    assert callable(dispatch)


def test_use_reducer_lazy_initial_state() -> None:
    def reducer(state: int, action: str) -> int:
        return state

    result = render_hook(lambda: use_reducer(reducer, lambda: 99))
    assert result.current[0] == 99


def test_use_reducer_dispatch_triggers_render() -> None:
    def reducer(state: int, action: str) -> int:
        if action == "increment":
            return state + 1
        if action == "reset":
            return 0
        return state

    result = render_hook(lambda: use_reducer(reducer, 0))
    _, dispatch = result.current

    result.act(lambda: dispatch("increment"))
    assert result.current[0] == 1
    assert result.render_count == 2
    result.act(lambda: dispatch("increment"))
    assert result.current[0] == 2
    assert result.render_count == 3
    result.act(lambda: dispatch("reset"))
    assert result.current[0] == 0
    assert result.render_count == 4


def test_use_reducer_no_render_on_same_state() -> None:
    def reducer(state: int, action: str) -> int:
        return state

    result = render_hook(lambda: use_reducer(reducer, 5))
    _, dispatch = result.current
    result.act(lambda: dispatch("noop"))
    assert result.render_count == 1


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
    rec.on_render_requested = lambda: re_rendered.append(1)

    root = rec.mount(counter())
    assert root.props["text"] == "0"

    dispatch_fn = captured_dispatch[0]
    assert dispatch_fn is not None
    dispatch_fn("increment")
    assert len(re_rendered) == 1

    rec.flush_dirty()
    assert root.props["text"] == "1"


# ======================================================================
# use_effect (deferred execution)
# ======================================================================


def test_use_effect_is_deferred() -> None:
    """Effects are queued during render, not run immediately."""
    calls: list = []
    ctx = HookState()
    with _rendering(ctx):
        use_effect(lambda: calls.append("mounted"), [])
        assert calls == [], "Effect should NOT run during render"

    ctx.flush_pending_effects()
    assert calls == ["mounted"], "Effect should run after flush"


def test_use_effect_cleanup_on_rerun() -> None:
    cleanups: list = []

    def make_effect(label: str):  # type: ignore[no-untyped-def]
        def effect() -> Any:
            return lambda: cleanups.append(label)

        return effect

    ctx = HookState()

    with _rendering(ctx):
        use_effect(make_effect("first"), None)
    ctx.flush_pending_effects()

    with _rendering(ctx):
        use_effect(make_effect("second"), None)
    ctx.flush_pending_effects()

    assert "first" in cleanups


def test_use_effect_skips_with_same_deps() -> None:
    calls: list = []
    ctx = HookState()

    with _rendering(ctx):
        use_effect(lambda: calls.append("run"), [1, 2])
    ctx.flush_pending_effects()

    with _rendering(ctx):
        use_effect(lambda: calls.append("run"), [1, 2])
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

    with _rendering(ctx):
        use_effect(lambda: lambda: cleanups.append("cleaned"), [])
    ctx.flush_pending_effects()

    assert cleanups == []
    ctx.cleanup_all_effects()
    assert cleanups == ["cleaned"]


def test_use_effect_cleanup_on_reconciler_unmount() -> None:
    cleanups: list = []

    @component
    def my_comp() -> Element:
        use_effect(lambda: lambda: cleanups.append("cleaned"), [])
        return Element("Text", {"text": "hi"}, [])

    result = render(my_comp())
    assert cleanups == []
    result.unmount()
    assert cleanups == ["cleaned"]


# ======================================================================
# batch_updates
# ======================================================================


def test_batch_updates_defers_render() -> None:
    result = render_hook(lambda: (use_state(0), use_state(0)))
    (_, set_a), (_, set_b) = result.current
    assert result.render_count == 1

    with batch_updates():
        set_a(1)
        set_b(2)
        assert result.render_count == 1, "Render should be deferred inside batch"

    assert result.render_count == 2, "Exactly one render after batch exits"
    assert result.current[0][0] == 1
    assert result.current[1][0] == 2


def test_batch_updates_nested() -> None:
    result = render_hook(lambda: (use_state(0), use_state(0)))
    (_, set_a), (_, set_b) = result.current

    with batch_updates():
        set_a(1)
        with batch_updates():
            set_b(2)
            assert result.render_count == 1
        assert result.render_count == 1, "Nested batch should not trigger render"

    assert result.render_count == 2


def test_batch_updates_no_render_when_unchanged() -> None:
    result = render_hook(lambda: use_state(5))
    _, set_a = result.current

    with batch_updates():
        set_a(5)

    assert result.render_count == 1


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

    with _rendering(ctx):
        val1 = use_memo(factory_a, [1])

    with _rendering(ctx):
        val2 = use_memo(factory_b, [1])

    assert val1 == 42
    assert val2 == 42
    assert len(calls) == 1


def test_use_memo_recomputes_on_dep_change() -> None:
    ctx = HookState()

    with _rendering(ctx):
        val1 = use_memo(lambda: "first", ["a"])

    with _rendering(ctx):
        val2 = use_memo(lambda: "second", ["b"])

    assert val1 == "first"
    assert val2 == "second"


def test_use_memo_in_component() -> None:
    calls: list = []

    def compute(n: int) -> int:
        calls.append(n)
        return n * 2

    result = render_hook(lambda n: use_memo(lambda: compute(n), [n]), 1)
    assert result.current == 2
    result.rerender(1)
    assert result.current == 2
    assert calls == [1]
    result.rerender(3)
    assert result.current == 6
    assert calls == [1, 3]


def test_use_callback_returns_stable_reference() -> None:
    ctx = HookState()
    fn = lambda: None  # noqa: E731

    with _rendering(ctx):
        cb1 = use_callback(fn, [1])

    with _rendering(ctx):
        cb2 = use_callback(lambda: None, [1])

    assert cb1 is fn
    assert cb2 is fn


# ======================================================================
# use_ref
# ======================================================================


def test_use_ref_persists() -> None:
    ctx = HookState()
    with _rendering(ctx):
        ref = use_ref(0)
        assert ref.current == 0
        ref.current = 5

    with _rendering(ctx):
        ref2 = use_ref(0)
        assert ref2.current == 5
        assert ref2 is ref


def test_use_ref_mutation_does_not_rerender() -> None:
    result = render_hook(lambda: use_ref(0))
    ref = result.current
    result.act(lambda: setattr(ref, "current", 7))
    assert result.render_count == 1
    result.rerender()
    assert result.current is ref
    assert ref.current == 7


# ======================================================================
# Context
# ======================================================================


def test_create_context_default() -> None:
    ctx = create_context("default_val")
    assert ctx.current() == "default_val"


def test_context_stack() -> None:
    ctx = create_context("default")
    ctx._push("override")
    assert ctx.current() == "override"
    ctx._push("inner")
    assert ctx.current() == "inner"
    ctx._pop()
    assert ctx.current() == "override"
    ctx._pop()
    assert ctx.current() == "default"


def test_use_context_reads_current() -> None:
    my_ctx = create_context("fallback")
    seen: list = []

    @component
    def reader() -> None:
        seen.append(use_context(my_ctx))
        return None

    result = render(my_ctx.Provider("active", reader()))
    assert seen == ["active"]
    assert my_ctx.current() == "fallback", "Provider value is scoped to the render"
    result.unmount()


def test_use_context_without_provider_returns_default() -> None:
    my_ctx = create_context("fallback")
    result = render_hook(lambda: use_context(my_ctx))
    assert result.current == "fallback"


# ======================================================================
# @component decorator
# ======================================================================


def test_component_decorator_creates_element() -> None:
    @component
    def my_comp(label: str = "hello") -> Element:
        return Element("Text", {"text": label}, [])

    assert isinstance(my_comp, Component)
    el = my_comp(label="world")
    assert isinstance(el, Element)
    assert el.type is my_comp
    assert getattr(my_comp, "__wrapped__") is my_comp.fn
    assert el.props == {"label": "world"}
    assert el.children == []


def test_component_with_positional_args() -> None:
    @component
    def greeting(name: str, age: int = 0) -> Element:
        return Element("Text", {"text": f"{name}, {age}"}, [])

    el = greeting("Alice", age=30)
    assert el.props == {"name": "Alice", "age": 30}


def test_component_with_children() -> None:
    @component
    def card(*children: Element, title: str = "") -> Element:
        return Element("Column", {}, [Element("Text", {"text": title}, []), *children])

    child_a = Element("Text", {"text": "a"}, [])
    child_b = Element("Text", {"text": "b"}, [])
    el = card(child_a, child_b, title="Hello")
    assert el.props == {"title": "Hello"}
    assert el.children == [child_a, child_b]

    root = Reconciler(MockBackend()).mount(el)
    assert [v.props.get("text") for v in root.children] == ["Hello", "a", "b"]


def test_component_key_extraction() -> None:
    @component
    def widget(text: str = "") -> Element:
        return Element("Text", {"text": text}, [])

    el = widget(text="hi", key="k1")  # type: ignore[call-arg]
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

    update_ops = backend.ops_of("update")
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
    rec.on_render_requested = lambda: re_rendered.append(1)

    root = rec.mount(counter())
    assert root.props["text"] == "0"
    assert render_count[0] == 1

    setter_fn = captured_setter[0]
    assert setter_fn is not None
    setter_fn(5)
    assert len(re_rendered) == 1
    assert render_count[0] == 1, "host callback defers the actual render"

    rec.flush_dirty()
    assert render_count[0] == 2
    assert root.props["text"] == "5"


def test_function_component_preserves_state_across_reconcile() -> None:
    @component
    def stateful(label: str = "") -> Element:
        count, set_count = use_state(0)
        return Element("Text", {"text": f"{label}:{count}"}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(stateful(label="A"))

    tree_node = rec.root
    assert tree_node is not None
    assert tree_node.hook_state is not None
    tree_node.hook_state.states[0] = 42

    root = rec.reconcile(stateful(label="B"))
    assert rec.root is not None
    assert rec.root.hook_state is not None
    assert rec.root.hook_state.states[0] == 42
    assert root.props["text"] == "B:42"


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
    el = theme.Provider("dark", themed())
    root = rec.mount(el)
    assert root.props["text"] == "dark"


# ======================================================================
# Provider with *children
# ======================================================================


def test_provider_with_multiple_children_kept_flat() -> None:
    """Multi-child providers rely on the reconciler's multi-child support."""
    theme = create_context("light")
    child_a = Element("Text", {"text": "a"}, [])
    child_b = Element("Text", {"text": "b"}, [])

    el = theme.Provider("dark", child_a, child_b)
    assert el.type is theme
    assert el.props == {"value": "dark"}
    assert el.children == [child_a, child_b]


def test_provider_with_single_child_no_fragment_wrap() -> None:
    theme = create_context("light")
    child = Element("Text", {"text": "single"}, [])

    el = theme.Provider("dark", child)
    assert el.type is theme
    assert el.children == [child]


# ======================================================================
# @memo
# ======================================================================


def test_memo_marks_component() -> None:
    @memo
    @component
    def my_comp(label: str = "x") -> Element:
        return Element("Text", {"text": label}, [])

    assert isinstance(my_comp, Component)
    assert my_comp.memoized is True


def test_memo_skips_rerender_with_same_props() -> None:
    render_count = [0]

    @memo
    @component
    def my_comp(label: str = "x") -> Element:
        render_count[0] += 1
        return Element("Text", {"text": label}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(my_comp(label="A"))
    assert render_count[0] == 1

    rec.reconcile(my_comp(label="A"))
    assert render_count[0] == 1, "memoized component should not re-render when props are unchanged"


def test_memo_rerenders_when_props_change() -> None:
    render_count = [0]

    @memo
    @component
    def my_comp(label: str = "x") -> Element:
        render_count[0] += 1
        return Element("Text", {"text": label}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    rec.mount(my_comp(label="A"))
    rec.reconcile(my_comp(label="B"))
    assert render_count[0] == 2


def test_memo_rerenders_when_internal_state_changes() -> None:
    render_count = [0]
    captured_setter: list = [None]

    @memo
    @component
    def stateful() -> Element:
        render_count[0] += 1
        value, set_value = use_state(0)
        captured_setter[0] = set_value
        return Element("Text", {"text": str(value)}, [])

    backend = MockBackend()
    rec = Reconciler(backend)
    # Defer the state-driven flush so the reconcile below is what
    # re-renders the memoized component.
    rec.on_render_requested = lambda: None
    root = rec.mount(stateful())
    assert render_count[0] == 1

    setter_fn = captured_setter[0]
    assert setter_fn is not None
    setter_fn(5)
    assert render_count[0] == 1

    rec.reconcile(stateful())
    assert render_count[0] == 2, "memo should still re-render when internal state changed"
    assert root.props["text"] == "5"


def test_memo_can_be_called_with_explicit_argument() -> None:
    """``memo`` works as a plain function as well as a decorator."""

    @component
    def my_comp(label: str = "x") -> Element:
        return Element("Text", {"text": label}, [])

    wrapped = memo(my_comp)
    assert wrapped.memoized is True
    el = wrapped(label="hi")
    assert isinstance(el, Element)
