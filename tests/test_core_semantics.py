"""Tests for the core-semantics overhaul: multi-child rendering, effect
phases, reactive context, portals, error boundary v2, back handlers, and
dev-mode diagnostics (hook order, style keys, warnings)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from pythonnative import diagnostics
from pythonnative.component import component, memo
from pythonnative.components import (
    ErrorBoundary,
    Fragment,
    Portal,
    Text,
)
from pythonnative.element import Element
from pythonnative.hooks import (
    Ref,
    create_context,
    use_back_handler,
    use_context,
    use_effect,
    use_imperative_handle,
    use_layout_effect,
    use_ref,
    use_state,
)
from pythonnative.reconciler import Reconciler
from pythonnative.testing import FakeBackend as MockBackend


def _make_reconciler() -> Tuple[Reconciler, MockBackend]:
    backend = MockBackend()
    rec = Reconciler(backend)
    rec.on_render_requested = lambda: None
    return rec, backend


@pytest.fixture()
def dev_mode() -> Any:
    """Enable dev diagnostics for one test and reset state afterwards."""
    diagnostics.set_dev_mode(True)
    diagnostics.clear_warnings()
    yield None
    diagnostics.clear_warnings()
    diagnostics.set_dev_mode(False)


# ======================================================================
# Multi-child components (None / list returns)
# ======================================================================


def test_component_returning_none_mounts_nothing() -> None:
    @component
    def Nothing() -> Any:
        return None

    rec, backend = _make_reconciler()
    root = rec.mount(Element("Column", {}, [Nothing()]))
    assert root.children == []
    assert backend.live_view_count() == 1  # just the Column


def test_component_returning_list_mounts_all_siblings() -> None:
    @component
    def Pair() -> Any:
        return [
            Element("Text", {"text": "one"}, []),
            Element("Text", {"text": "two"}, []),
        ]

    rec, _backend = _make_reconciler()
    root = rec.mount(Element("Column", {}, [Pair()]))
    assert [c.props["text"] for c in root.children] == ["one", "two"]


def test_component_toggling_none_and_element() -> None:
    setters: Dict[str, Any] = {}

    @component
    def Toggle() -> Any:
        visible, set_visible = use_state(False)
        setters["set"] = set_visible
        if not visible:
            return None
        return Element("Text", {"text": "now you see me"}, [])

    @component
    def App() -> Element:
        return Element(
            "Column",
            {},
            [
                Element("Text", {"text": "header"}, []),
                Toggle(),
                Element("Text", {"text": "footer"}, []),
            ],
        )

    rec, _backend = _make_reconciler()
    root = rec.mount(App())
    assert [c.props["text"] for c in root.children] == ["header", "footer"]

    setters["set"](True)
    rec.flush_dirty()
    assert [c.props["text"] for c in root.children] == [
        "header",
        "now you see me",
        "footer",
    ]

    setters["set"](False)
    rec.flush_dirty()
    assert [c.props["text"] for c in root.children] == ["header", "footer"]


def test_none_and_false_children_are_dropped() -> None:
    rec, _backend = _make_reconciler()
    root = rec.mount(
        Element(
            "Column",
            {},
            [
                Element("Text", {"text": "a"}, []),
                None,
                False,
                Element("Text", {"text": "b"}, []),
            ],
        )
    )
    assert [c.props["text"] for c in root.children] == ["a", "b"]


def test_component_list_grows_and_shrinks() -> None:
    setters: Dict[str, Any] = {}

    @component
    def Repeats() -> Any:
        n, set_n = use_state(1)
        setters["set"] = set_n
        return [Element("Text", {"text": f"row {i}"}, [], key=str(i)) for i in range(n)]

    rec, _backend = _make_reconciler()
    root = rec.mount(Element("Column", {}, [Repeats()]))
    assert len(root.children) == 1

    setters["set"](3)
    rec.flush_dirty()
    assert [c.props["text"] for c in root.children] == ["row 0", "row 1", "row 2"]

    setters["set"](2)
    rec.flush_dirty()
    assert [c.props["text"] for c in root.children] == ["row 0", "row 1"]


def test_keyed_fragment_moves_children_as_a_unit() -> None:
    def group(name: str) -> Element:
        return Fragment(
            Element("Text", {"text": f"{name}-1"}, []),
            Element("Text", {"text": f"{name}-2"}, []),
            key=name,
        )

    rec, _backend = _make_reconciler()
    root = rec.mount(Element("Column", {}, [group("a"), group("b")]))
    assert [c.props["text"] for c in root.children] == ["a-1", "a-2", "b-1", "b-2"]
    first_ids = [c.id for c in root.children]

    rec.reconcile(Element("Column", {}, [group("b"), group("a")]))
    assert [c.props["text"] for c in root.children] == ["b-1", "b-2", "a-1", "a-2"]
    # The same native views were reordered, not recreated.
    assert sorted(c.id for c in root.children) == sorted(first_ids)


# ======================================================================
# Effect phases: use_layout_effect before use_effect
# ======================================================================


def test_layout_effects_run_before_passive_effects() -> None:
    order: List[str] = []

    @component
    def App() -> Element:
        use_effect(lambda: order.append("passive"), [])
        use_layout_effect(lambda: order.append("layout"), [])
        return Element("Text", {"text": "x"}, [])

    rec, _backend = _make_reconciler()
    rec.mount(App())
    assert order == ["layout", "passive"]


def test_layout_effect_sees_committed_frame() -> None:
    frames: List[Any] = []

    @component
    def App() -> Element:
        ref: Ref = use_ref(None)

        def read_frame() -> None:
            frames.append(ref._pn_frame)

        use_layout_effect(read_frame, None)
        return Element(
            "Column",
            {},
            [Element("View", {"ref": ref, "height": 50}, [])],
        )

    rec, _backend = _make_reconciler()
    # Viewport known up front: the mount commit runs the layout pass
    # before layout effects flush, so the effect observes a real frame.
    rec.set_viewport_size(300.0, 600.0)
    rec.mount(App())
    committed = [f for f in frames if f is not None]
    assert committed, "layout effect should observe a committed frame"
    _x, _y, w, h = committed[-1]
    assert (w, h) == (300.0, 50.0)


def test_layout_effect_cleanup_on_unmount() -> None:
    cleaned: List[str] = []

    @component
    def Child() -> Element:
        use_layout_effect(lambda: lambda: cleaned.append("layout"), [])
        return Element("Text", {"text": "c"}, [])

    rec, _backend = _make_reconciler()
    rec.mount(Element("Column", {}, [Child()]))
    assert cleaned == []
    rec.reconcile(Element("Column", {}, []))
    assert cleaned == ["layout"]


# ======================================================================
# use_imperative_handle
# ======================================================================


def test_use_imperative_handle_publishes_and_clears() -> None:
    class Controller:
        def __init__(self) -> None:
            self.calls: List[str] = []

        def focus(self) -> None:
            self.calls.append("focus")

    @component
    def Field(ref: Any = None) -> Element:
        use_imperative_handle(ref, Controller, [])
        return Element("TextInput", {}, [])

    handle: Ref = Ref()
    rec, _backend = _make_reconciler()
    rec.mount(Element("Column", {}, [Field(ref=handle)]))

    assert isinstance(handle.current, Controller)
    handle.current.focus()
    assert handle.current.calls == ["focus"]

    rec.reconcile(Element("Column", {}, []))
    assert handle.current is None, "unmount must clear the published handle"


def test_use_imperative_handle_none_ref_is_noop() -> None:
    @component
    def Field(ref: Any = None) -> Element:
        use_imperative_handle(ref, lambda: object(), [])
        return Element("TextInput", {}, [])

    rec, _backend = _make_reconciler()
    rec.mount(Element("Column", {}, [Field()]))  # must not raise


# ======================================================================
# Reactive context
# ======================================================================


def test_context_change_rerenders_consumer_under_memo() -> None:
    theme_ctx = create_context("light")
    consumer_renders: List[str] = []
    setters: Dict[str, Any] = {}

    @component
    def Leaf() -> Element:
        theme = use_context(theme_ctx)
        consumer_renders.append(theme)
        return Element("Text", {"text": theme}, [])

    @memo
    @component
    def Wall() -> Element:
        # Memoized, props never change: would skip re-renders entirely
        # if context were not reactive.
        return Element("Column", {}, [Leaf()])

    @component
    def App() -> Element:
        theme, set_theme = use_state("light")
        setters["set"] = set_theme
        return theme_ctx.Provider(theme, Wall())

    rec, backend = _make_reconciler()
    rec.mount(App())
    assert consumer_renders == ["light"]

    setters["set"]("dark")
    rec.flush_dirty()
    assert consumer_renders == ["light", "dark"]
    root = rec.root_view()
    assert root.find_first("Text").props["text"] == "dark"
    assert backend.live_view_count() > 0


def test_context_same_value_does_not_rerender_consumer() -> None:
    ctx = create_context(0)
    consumer_renders: List[int] = []
    setters: Dict[str, Any] = {}

    @component
    def Leaf() -> Element:
        value = use_context(ctx)
        consumer_renders.append(value)
        return Element("Text", {"text": str(value)}, [])

    @memo
    @component
    def Wall() -> Element:
        return Element("Column", {}, [Leaf()])

    @component
    def App() -> Element:
        _tick, set_tick = use_state(0)
        setters["set"] = set_tick
        # Provider value is constant even though App re-renders.
        return ctx.Provider(42, Wall())

    rec, _backend = _make_reconciler()
    rec.mount(App())
    assert consumer_renders == [42]

    setters["set"](1)
    rec.flush_dirty()
    assert consumer_renders == [42], "unchanged context value must not re-render consumers"


def test_provider_multiple_children_render_flat() -> None:
    ctx = create_context("x")

    @component
    def Leaf(label: str = "") -> Element:
        value = use_context(ctx)
        return Element("Text", {"text": f"{label}:{value}"}, [])

    rec, _backend = _make_reconciler()
    root = rec.mount(
        Element(
            "Column",
            {},
            [ctx.Provider("v", Leaf(label="a"), Leaf(label="b"))],
        )
    )
    assert [c.props["text"] for c in root.children] == ["a:v", "b:v"]


# ======================================================================
# Portals
# ======================================================================


def test_portal_children_render_into_detached_overlay() -> None:
    rec, backend = _make_reconciler()
    root = rec.mount(
        Element(
            "Column",
            {},
            [
                Element("Text", {"text": "content"}, []),
                Portal(Element("Text", {"text": "floating"}, [])),
            ],
        )
    )
    # The portal contributes no native child to its parent.
    assert [c.props["text"] for c in root.children] == ["content"]

    overlays = backend.detached_views("Portal")
    assert len(overlays) == 1
    texts = overlays[0].find_all("Text")
    assert [t.props["text"] for t in texts] == ["floating"]


def test_portal_children_laid_out_against_viewport() -> None:
    rec, backend = _make_reconciler()
    rec.mount(
        Element(
            "Column",
            {},
            [
                Element("Text", {"text": "content"}, []),
                Portal(
                    Element(
                        "Column",
                        {"position": "absolute", "left": 10, "top": 20, "width": 100, "height": 40},
                        [],
                    )
                ),
            ],
        )
    )
    rec.set_viewport_size(390.0, 844.0)
    overlay = backend.detached_views("Portal")[0]
    child = overlay.children[0]
    assert child.frame == (10.0, 20.0, 100.0, 40.0)


def test_portal_unmount_destroys_overlay() -> None:
    setters: Dict[str, Any] = {}

    @component
    def App() -> Element:
        show, set_show = use_state(True)
        setters["set"] = set_show
        children = [Element("Text", {"text": "content"}, [])]
        if show:
            children.append(Portal(Element("Text", {"text": "floating"}, [])))
        return Element("Column", {}, children)

    rec, backend = _make_reconciler()
    rec.mount(App())
    assert len(backend.detached_views("Portal")) == 1

    setters["set"](False)
    rec.flush_dirty()
    assert backend.detached_views("Portal") == []


def test_portal_state_and_events_stay_wired() -> None:
    from pythonnative.events import dispatch_event

    presses: List[int] = []

    @component
    def App() -> Element:
        count, set_count = use_state(0)
        return Element(
            "Column",
            {},
            [
                Element("Text", {"text": f"count:{count}"}, []),
                Portal(
                    Element(
                        "Button",
                        {"title": "bump", "on_press": lambda: set_count(count + 1)},
                        [],
                    )
                ),
            ],
        )

    rec, backend = _make_reconciler()
    root = rec.mount(App())
    overlay = backend.detached_views("Portal")[0]
    button = overlay.find_first("Button")
    handled = dispatch_event(button.tag, "on_press")
    assert handled, "portal button press must reach the Python handler"
    rec.flush_dirty()
    assert root.find_first("Text").props["text"] == "count:1"
    assert presses == []  # unused, guards against accidental capture


# ======================================================================
# Error boundary v2
# ======================================================================


def test_error_boundary_on_error_callback() -> None:
    caught: List[BaseException] = []

    @component
    def Boom() -> Element:
        raise ValueError("kapow")

    rec, _backend = _make_reconciler()
    rec.mount(
        Element(
            "Column",
            {},
            [
                ErrorBoundary(
                    Boom(),
                    fallback=Text("failed"),
                    on_error=lambda exc: caught.append(exc),
                )
            ],
        )
    )
    assert len(caught) == 1
    assert isinstance(caught[0], ValueError)


def test_error_boundary_fallback_receives_error_and_reset() -> None:
    seen: Dict[str, Any] = {}

    @component
    def Boom() -> Element:
        raise ValueError("kapow")

    def fallback(error: BaseException, reset: Any) -> Element:
        seen["error"] = error
        seen["reset"] = reset
        return Element("Text", {"text": f"error: {error}"}, [])

    rec, _backend = _make_reconciler()
    root = rec.mount(Element("Column", {}, [ErrorBoundary(Boom(), fallback=fallback)]))
    assert isinstance(seen["error"], ValueError)
    assert callable(seen["reset"])
    assert root.find_first("Text").props["text"] == "error: kapow"


def test_error_boundary_reset_retries_children() -> None:
    attempts: List[int] = []
    resets: Dict[str, Any] = {}

    @component
    def Flaky() -> Element:
        attempts.append(1)
        if len(attempts) == 1:
            raise ValueError("first time fails")
        return Element("Text", {"text": "recovered"}, [])

    def fallback(error: BaseException, reset: Any) -> Element:
        resets["reset"] = reset
        return Element("Text", {"text": "failed"}, [])

    rec, _backend = _make_reconciler()
    root = rec.mount(Element("Column", {}, [ErrorBoundary(Flaky(), fallback=fallback)]))
    assert root.find_first("Text").props["text"] == "failed"

    resets["reset"]()
    rec.flush_dirty()
    assert root.find_first("Text").props["text"] == "recovered"
    assert len(attempts) == 2


# ======================================================================
# use_back_handler
# ======================================================================


def test_back_handler_consumes_event() -> None:
    @component
    def App() -> Element:
        use_back_handler(lambda: True)
        return Element("Text", {"text": "x"}, [])

    rec, _backend = _make_reconciler()
    rec.mount(App())
    assert rec.dispatch_back_press() is True


def test_back_handler_pass_through_and_priority() -> None:
    calls: List[str] = []

    @component
    def Outer() -> Element:
        def handle() -> bool:
            calls.append("outer")
            return False  # observe, do not consume

        use_back_handler(handle)
        return Element("Column", {}, [Inner()])

    @component
    def Inner() -> Element:
        def handle() -> bool:
            calls.append("inner")
            return True

        use_back_handler(handle)
        return Element("Text", {"text": "x"}, [])

    rec, _backend = _make_reconciler()
    rec.mount(Outer())
    assert rec.dispatch_back_press() is True
    # Effects flush children-first, so the parent registered *last* and
    # dispatch (last-registered first, matching React Native) runs it
    # first; it declines, then the child consumes.
    assert calls == ["outer", "inner"]


def test_back_handler_unregisters_on_unmount() -> None:
    setters: Dict[str, Any] = {}

    @component
    def Guard() -> Element:
        use_back_handler(lambda: True)
        return Element("Text", {"text": "guard"}, [])

    @component
    def App() -> Element:
        show, set_show = use_state(True)
        setters["set"] = set_show
        return Element("Column", {}, [Guard() if show else None])

    rec, _backend = _make_reconciler()
    rec.mount(App())
    assert rec.dispatch_back_press() is True

    setters["set"](False)
    rec.flush_dirty()
    assert rec.dispatch_back_press() is False


# ======================================================================
# Hook-order guard (dev mode)
# ======================================================================


def test_conditional_hook_raises_in_dev_mode(dev_mode: Any) -> None:
    setters: Dict[str, Any] = {}

    @component
    def Sneaky() -> Element:
        flag, set_flag = use_state(False)
        setters["set"] = set_flag
        if flag:
            use_ref(None)  # extra hook appears on the second render
        return Element("Text", {"text": str(flag)}, [])

    rec, _backend = _make_reconciler()
    rec.mount(Sneaky())

    setters["set"](True)
    with pytest.raises(diagnostics.HookOrderError):
        rec.flush_dirty()


def test_hook_kind_swap_raises_in_dev_mode(dev_mode: Any) -> None:
    setters: Dict[str, Any] = {}

    @component
    def Shifty() -> Element:
        flag, set_flag = use_state(False)
        setters["set"] = set_flag
        if flag:
            use_ref(None)
        else:
            use_state(0)
        return Element("Text", {"text": str(flag)}, [])

    rec, _backend = _make_reconciler()
    rec.mount(Shifty())

    setters["set"](True)
    with pytest.raises(diagnostics.HookOrderError):
        rec.flush_dirty()


def test_consistent_hooks_pass_in_dev_mode(dev_mode: Any) -> None:
    setters: Dict[str, Any] = {}

    @component
    def Steady() -> Element:
        count, set_count = use_state(0)
        setters["set"] = set_count
        use_ref(None)
        return Element("Text", {"text": str(count)}, [])

    rec, _backend = _make_reconciler()
    rec.mount(Steady())
    setters["set"](1)
    rec.flush_dirty()  # must not raise
    assert rec.root_view().props["text"] == "1"


def test_hook_order_not_checked_in_production() -> None:
    diagnostics.set_dev_mode(False)
    setters: Dict[str, Any] = {}

    @component
    def Sneaky() -> Element:
        flag, set_flag = use_state(False)
        setters["set"] = set_flag
        if flag:
            use_ref(None)
        return Element("Text", {"text": str(flag)}, [])

    rec, _backend = _make_reconciler()
    rec.mount(Sneaky())
    setters["set"](True)
    rec.flush_dirty()  # silently tolerated in production


# ======================================================================
# Style-key validation (dev mode)
# ======================================================================


def test_unknown_style_key_warns_with_suggestion(dev_mode: Any) -> None:
    Text("hi", style={"font_siez": 20})
    warnings = diagnostics.get_warnings()
    assert any("font_siez" in w for w in warnings)
    assert any("font_size" in w for w in warnings), "should suggest the close match"


def test_unknown_style_key_warns_once(dev_mode: Any) -> None:
    Text("hi", style={"font_siez": 20})
    Text("hi again", style={"font_siez": 22})
    warnings = [w for w in diagnostics.get_warnings() if "font_siez" in w]
    assert len(warnings) == 1


def test_known_style_keys_do_not_warn(dev_mode: Any) -> None:
    Text("hi", style={"font_size": 20, "color": "#333333", "margin_top": 4})
    assert diagnostics.get_warnings() == []


def test_style_validation_skipped_in_production() -> None:
    diagnostics.set_dev_mode(False)
    diagnostics.clear_warnings()
    Text("hi", style={"font_siez": 20})
    assert diagnostics.get_warnings() == []


# ======================================================================
# Duplicate-key warning (dev mode)
# ======================================================================


def test_duplicate_sibling_keys_warn(dev_mode: Any) -> None:
    rec, _backend = _make_reconciler()
    rec.mount(
        Element(
            "Column",
            {},
            [
                Element("Text", {"text": "a"}, [], key="same"),
                Element("Text", {"text": "b"}, [], key="same"),
            ],
        )
    )
    warnings = diagnostics.get_warnings()
    assert any("same" in w and "key" in w.lower() for w in warnings)


# ======================================================================
# Diagnostics primitives
# ======================================================================


def test_warn_once_dedupes_by_key(dev_mode: Any) -> None:
    diagnostics.warn_once("message one", key="k")
    diagnostics.warn_once("message two", key="k")
    assert diagnostics.get_warnings() == ["message one"]


def test_report_error_routes_to_last_reporter(dev_mode: Any) -> None:
    seen: List[Tuple[str, str]] = []
    owner_a = object()
    owner_b = object()
    diagnostics.set_error_reporter(owner_a, lambda exc, phase: seen.append(("a", phase)))
    diagnostics.set_error_reporter(owner_b, lambda exc, phase: seen.append(("b", phase)))
    try:
        assert diagnostics.report_error(ValueError("x"), phase="event") is True
        assert seen == [("b", "event")]

        diagnostics.set_error_reporter(owner_b, None)
        assert diagnostics.report_error(ValueError("y"), phase="render") is True
        assert seen == [("b", "event"), ("a", "render")]
    finally:
        diagnostics.set_error_reporter(owner_a, None)
        diagnostics.set_error_reporter(owner_b, None)


def test_report_error_without_reporter_returns_false(dev_mode: Any) -> None:
    assert diagnostics.report_error(ValueError("z")) is False


def test_event_handler_error_routed_to_reporter(dev_mode: Any) -> None:
    from pythonnative.events import dispatch_event

    reported: List[str] = []
    owner = object()
    diagnostics.set_error_reporter(owner, lambda exc, phase: reported.append(phase))
    try:

        @component
        def App() -> Element:
            def explode() -> None:
                raise RuntimeError("handler blew up")

            return Element("Button", {"title": "x", "on_press": explode}, [])

        rec, backend = _make_reconciler()
        root = rec.mount(App())
        dispatch_event(root.tag, "on_press")
        assert reported and "on_press" in reported[0]
    finally:
        diagnostics.set_error_reporter(owner, None)


# ======================================================================
# Multiple screen-level roots warning
# ======================================================================


def test_multi_root_screen_warns_in_dev(dev_mode: Any) -> None:
    @component
    def App() -> Any:
        return [
            Element("Text", {"text": "one"}, []),
            Element("Text", {"text": "two"}, []),
        ]

    rec, _backend = _make_reconciler()
    rec.mount(App())
    warnings = diagnostics.get_warnings()
    assert any("root" in w.lower() for w in warnings)
