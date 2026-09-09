"""Tests for the native bridge: codec, transport routing, view backend, modules, hosts.

Everything here runs against ``FakeTransport``, which decodes the same
JSON the Swift and Kotlin runtimes receive. The tests therefore pin the
wire protocol described in ``docs/concepts/bridge.md`` from the Python
side: what a commit serializes to, how events and module results come
back, and how the on-device screen host drives navigation.
"""

from __future__ import annotations

import asyncio
import inspect
import math
import types
from typing import Any, Dict, Generator, List

import pytest

import pythonnative as pn
from pythonnative import bridge
from pythonnative.bridge import codec
from pythonnative.bridge.fake import FakeTransport
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.hooks import use_state
from pythonnative.mutations import CreateOp, DestroyOp, InsertOp, Mutation, SetFrameOp, UpdateOp
from pythonnative.native_modules import registry as modules
from pythonnative.native_views import get_registry, set_registry
from pythonnative.native_views.bridge_backend import BridgeBackend, NativeViewRef
from pythonnative.reconciler import Reconciler
from pythonnative.sdk.schema import COMPONENTS


@pytest.fixture
def transport() -> Generator[FakeTransport, None, None]:
    fake = FakeTransport()
    bridge.set_transport(fake)
    backend = BridgeBackend(fake)
    set_registry(backend)
    modules._reset_for_tests()
    yield fake
    modules._reset_for_tests()
    set_registry(None)
    bridge._reset_for_tests()


@pytest.fixture
def backend(transport: FakeTransport) -> BridgeBackend:
    reg = get_registry()
    assert isinstance(reg, BridgeBackend)
    return reg


# ======================================================================
# Codec
# ======================================================================


def test_to_jsonable_normalizes_python_only_values() -> None:
    value = {
        "events": frozenset({"on_press", "on_change"}),
        "pair": (1, 2),
        "inf": math.inf,
        "neg": -math.inf,
        "nan": math.nan,
        "nested": [{"a": (True, None)}],
    }
    out = codec.to_jsonable(value)
    assert out["events"] == ["on_change", "on_press"]
    assert out["pair"] == [1, 2]
    assert out["inf"] == "inf"
    assert out["neg"] == "-inf"
    assert out["nan"] is None
    assert out["nested"] == [{"a": [True, None]}]
    codec.dumps(out)  # must be JSON-serializable


def test_to_jsonable_rejects_callables() -> None:
    with pytest.raises(TypeError):
        codec.to_jsonable({"on_bind_row": lambda i: i})


def test_split_props_keeps_callables_python_side() -> None:
    fn = lambda i: i  # noqa: E731
    wire, python = codec.split_props({"count": 3, "on_bind_row": fn, "obj": object()})
    assert wire == {"count": 3}
    assert python["on_bind_row"] is fn
    assert "obj" in python


def test_encode_transaction_shapes() -> None:
    render = lambda i: i  # noqa: E731
    ops: List[Mutation] = [
        CreateOp(1, "Column", {"flex": 1, "_pn_events": frozenset({"on_press"})}),
        CreateOp(2, "VirtualList", {"count": 2, "on_bind_row": render}),
        UpdateOp(1, {"flex": None, "padding": 4}),
        InsertOp(1, 2, 0),
        SetFrameOp(2, 0, 0, 100.5, math.nan),
        DestroyOp(2),
    ]
    text, sidecar = codec.encode_transaction(ops)
    decoded = codec.loads(text)
    assert decoded == [
        ["c", 1, "Column", {"flex": 1, "_pn_events": ["on_press"]}],
        ["c", 2, "VirtualList", {"count": 2}],
        ["u", 1, {"flex": None, "padding": 4}],
        ["i", 1, 2, 0],
        ["f", 2, 0.0, 0.0, 100.5, 0.0],
        ["d", 2],
    ]
    assert sidecar == [(2, {"on_bind_row": render})]


def test_loads_handles_empty_and_bytes() -> None:
    assert codec.loads(None) is None
    assert codec.loads("") is None
    assert codec.loads(b'{"a": 1}') == {"a": 1}


# ======================================================================
# Transport selection and handshake
# ======================================================================


def test_get_transport_off_device_raises() -> None:
    bridge._reset_for_tests()
    with pytest.raises(RuntimeError, match="off-device"):
        bridge.get_transport()
    assert bridge.has_transport() is False


def test_handshake_accepts_matching_version(transport: FakeTransport) -> None:
    assert bridge.handshake() == bridge.PROTOCOL_VERSION


def test_handshake_rejects_mismatch() -> None:
    fake = FakeTransport(version=bridge.PROTOCOL_VERSION + 1)
    bridge.set_transport(fake)
    try:
        with pytest.raises(RuntimeError, match="protocol mismatch"):
            bridge.handshake()
    finally:
        bridge._reset_for_tests()


def test_set_transport_installs_callback(transport: FakeTransport) -> None:
    assert transport.callback is bridge.native_callback
    assert bridge.get_transport() is transport


# ======================================================================
# Main-queue posting
# ======================================================================


def test_application_callbacks_do_not_cross_the_native_bridge(transport: FakeTransport) -> None:
    import threading

    from pythonnative import runtime

    runtime.start()
    done = threading.Event()
    threads: List[str] = []
    runtime.call_on_application_thread(lambda: threads.append(threading.current_thread().name))
    runtime.call_on_application_thread(done.set)
    assert done.wait(2)
    assert threads == ["PythonNative"]
    assert not any(module == "Host" and method == "post" for module, method, _ in transport.calls)


def test_application_callback_runs_inline_on_its_owner(transport: FakeTransport) -> None:
    from pythonnative import runtime

    runtime.start()

    async def check() -> list[int]:
        order = [1]
        runtime.call_on_application_thread(lambda: order.append(2))
        order.append(3)
        return order

    assert runtime.run_blocking(check()) == [1, 2, 3]


# ======================================================================
# View backend
# ======================================================================


def test_backend_applies_transaction_and_tracks_tags(backend: BridgeBackend, transport: FakeTransport) -> None:
    backend.apply_mutations(
        [
            CreateOp(1, "Column", {"flex": 1}),
            CreateOp(2, "Text", {"text": "hi", "_pn_events": frozenset({"on_press"})}),
            InsertOp(1, 2, 0),
            SetFrameOp(2, 8, 8, 100, 20),
        ]
    )
    assert len(transport.transactions) == 1
    assert transport.views[1].type_name == "Column"
    assert transport.views[1].children == [transport.views[2]]
    assert transport.views[2].props == {"text": "hi", "_pn_events": ["on_press"]}
    assert transport.views[2].frame == (8.0, 8.0, 100.0, 20.0)
    ref = backend.resolve_view(2)
    assert isinstance(ref, NativeViewRef) and ref.tag == 2 and ref.type_name == "Text"
    assert backend.live_view_count() == 2

    backend.apply_mutations([UpdateOp(2, {"text": None, "color": "#fff"}), DestroyOp(2)])
    assert 2 not in transport.views
    assert backend.resolve_view(2) is None
    assert backend.live_view_count() == 1


def test_backend_measure_command_and_animation(backend: BridgeBackend, transport: FakeTransport) -> None:
    backend.apply_mutations([CreateOp(7, "Text", {"text": "x"})])
    assert backend.measure_intrinsic(7, math.inf, 200) == (60.0, 16.0)
    assert backend.measure_intrinsic(99, 10, 10) == (0.0, 0.0)

    backend.apply_mutations([CreateOp(8, "ScrollView", {}), CreateOp(9, "TextInput", {})])
    transport.command_results["get_scroll_offset"] = {"x": 0, "y": 42}
    assert backend.command(8, "get_scroll_offset", {}) == {"x": 0, "y": 42}
    assert backend.command(9, "focus") is None
    assert transport.commands[-1] == (9, "focus", {})
    with pytest.raises(TypeError, match="Unknown command"):
        backend.command(7, "focus")

    backend.set_animated_property(7, "opacity", 0.5)
    assert transport.animations[-1] == (7, {"op": "set", "prop": "opacity", "value": 0.5})
    assert backend.start_animation(7, 3, "opacity", {"type": "timing", "to": 1.0, "duration": 100}) is True
    transport.animate_results["cancel"] = {"value": 0.7}
    assert backend.cancel_animation(7, 3) == 0.7
    assert backend.start_animation(404, 1, "opacity", {}) is False


def test_backend_holds_callable_props_in_sidecar(backend: BridgeBackend, transport: FakeTransport) -> None:
    render = lambda i: Element("Text", {"text": str(i)}, [])  # noqa: E731
    backend.apply_mutations([CreateOp(5, "VirtualList", {"count": 3, "on_bind_row": render})])
    assert transport.views[5].props == {"count": 3}
    assert backend.python_props(5)["on_bind_row"] is render
    backend.apply_mutations([UpdateOp(5, {"on_bind_row": None})])
    assert backend.python_props(5) == {}
    assert transport.views[5].props == {"count": 3}


def test_reconciler_commits_through_bridge(transport: FakeTransport) -> None:
    @component
    def App() -> Element:
        count, set_count = use_state(0)
        return pn.Column(
            pn.Text(f"count={count}"),
            pn.Button("+", on_press=lambda: set_count(count + 1)),
            style={"flex": 1},
        )

    rec = Reconciler(get_registry())
    rec.on_render_requested = lambda: rec.flush_dirty()
    root = rec.mount(App())
    rec.set_viewport_size(320, 480)
    assert isinstance(root, NativeViewRef)
    column = transport.views[root.tag]
    assert column.type_name == "Column"
    texts = transport.find("Text")
    assert texts and texts[0].props["text"] == "count=0"
    button = transport.find("Button")[0]
    assert "on_press" in button.props["_pn_events"]
    assert column.frame[2:] == (320.0, 480.0) or column.frame == (0.0, 0.0, 0.0, 0.0)

    transport.fire(button.tag, "on_press")
    assert transport.find("Text")[0].props["text"] == "count=1"
    rec.unmount()
    assert transport.views == {}


@pytest.mark.parametrize(
    "name",
    [
        name
        for name in pn.components.__all__
        if name in COMPONENTS
        and inspect.isfunction(getattr(pn, name))
        and name
        not in {
            "KeyboardAvoidingView",
            "SafeAreaView",
            "FlatList",
            "SectionList",
            "ErrorBoundary",
            "Fragment",
            "Suspense",
        }
    ],
)
def test_builtin_factory_defaults_cross_the_bridge(name: str, backend: BridgeBackend, transport: FakeTransport) -> None:
    element = getattr(pn, name)()
    assert isinstance(element.type, str)
    backend.apply_mutations([CreateOp(1, element.type, dict(element.props))])
    assert transport.views[1].type_name == element.type
    if name in {"Checkbox", "DatePicker", "Picker"}:
        assert transport.views[1].props["accessibility_role"] == ("checkbox" if name == "Checkbox" else "button")


@pytest.mark.parametrize("name", ["View", "Text", "Image"])
def test_animated_transform_shorthands_cross_the_bridge(name: str, transport: FakeTransport) -> None:
    scale = pn.Animated.Value(0.5)
    translate = pn.Animated.Value(10)
    factory = getattr(pn.Animated, name)
    children = [] if name == "View" else ["box" if name == "Text" else "https://example.com/image.png"]
    rec = Reconciler(get_registry())
    try:
        rec.mount(factory(*children, style={"scale": scale, "translate_x": translate, "rotate": 45}))
        props = transport.find(name)[0].props
        assert props["transform"] == [{"scale": 0.5}, {"translate_x": 10.0}, {"rotate": 45}]
        assert not {"scale", "translate_x", "rotate"} & props.keys()
    finally:
        rec.unmount()


def test_event_handler_return_value_is_returned_to_native(transport: FakeTransport) -> None:
    from pythonnative.events import get_event_registry

    get_registry().apply_mutations([CreateOp(11, "VirtualList", {})])
    get_event_registry().set_events(11, {"on_bind_row": lambda payload: {"root": payload["index"] * 2}})
    try:
        assert transport.fire(11, "on_bind_row", {"index": 21}) == {"root": 42}
        assert transport.fire(11, "on_missing") is None
    finally:
        get_event_registry().clear(11)


def test_destroyed_view_drops_queued_event(transport: FakeTransport) -> None:
    from pythonnative.events import get_event_registry

    backend = get_registry()
    backend.apply_mutations([CreateOp(50, "Button", {"title": "Press"})])
    seen: list[str] = []
    get_event_registry().set_events(50, {"on_press": lambda: seen.append("press")})
    transport.fire(50, "on_press")
    backend.apply_mutations([DestroyOp(50)])
    transport.fire(50, "on_press")
    assert seen == ["press"]


def test_animation_completion_callback_routes_to_animated(
    transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pythonnative import animated

    seen: List[Any] = []
    monkeypatch.setattr(
        animated, "native_animation_completed", lambda anim_id, finished=True: seen.append((anim_id, finished))
    )
    transport.complete_animation(9, finished=False)
    assert seen == [(9, False)]


# ======================================================================
# Native modules
# ======================================================================


def test_bridge_module_sync_call_and_error(transport: FakeTransport) -> None:
    def clipboard(method: str, args: Dict[str, Any]) -> Any:
        if method == "get_string":
            return "pasted"
        raise ValueError("nope")

    transport.module_handlers["Clipboard"] = clipboard
    module = modules.native_module("Clipboard")
    assert isinstance(module, modules.BridgeModule)
    assert module.call("get_string") == "pasted"
    assert transport.calls[-1] == ("Clipboard", "get_string", {})
    with pytest.raises(modules.NativeModuleError, match="nope"):
        module.call("set_string", text="x")


def test_bridge_module_pending_call_resolves_later(transport: FakeTransport) -> None:
    transport.module_handlers["Camera"] = lambda method, args: FakeTransport.pending()

    async def scenario() -> Any:
        task = asyncio.ensure_future(modules.native_module("Camera").call_async("take_photo", quality=0.8))
        await asyncio.sleep(0)
        _module, call_id, method, args = transport.pending_calls[0]
        assert method == "take_photo" and args == {"quality": 0.8, "allow_editing": False}
        transport.resolve_pending(call_id, "/tmp/photo.jpg")
        return await task

    assert asyncio.run(scenario()) == "/tmp/photo.jpg"


def test_bridge_module_pending_call_rejects(transport: FakeTransport) -> None:
    transport.module_handlers["Biometrics"] = lambda method, args: FakeTransport.pending()

    async def scenario() -> None:
        task = asyncio.ensure_future(modules.native_module("Biometrics").call_async("authenticate", reason="x"))
        await asyncio.sleep(0)
        transport.resolve_pending(transport.pending_calls[0][1], error="cancelled")
        await task

    with pytest.raises(modules.NativeModuleError, match="cancelled"):
        asyncio.run(scenario())


def test_facades_use_bridge_modules_on_device(transport: FakeTransport) -> None:
    store: Dict[str, str] = {}

    def secure(method: str, args: Dict[str, Any]) -> Any:
        if method == "set_item":
            store[args["key"]] = args["value"]
            return True
        if method == "get_item":
            return store.get(args["key"])
        return store.pop(args["key"], None) is not None

    transport.module_handlers["SecureStore"] = secure
    assert pn.SecureStore.set_item("token", "abc") is None
    assert pn.SecureStore.get_item("token") == "abc"
    assert pn.SecureStore.delete_item("token") is True
    assert pn.SecureStore.get_item("token") is None


def test_facade_surfaces_native_errors(transport: FakeTransport) -> None:
    """Facades don't turn a rejected native call into a default value."""

    def failing(method: str, args: Dict[str, Any]) -> Any:
        raise RuntimeError("keychain locked")

    transport.module_handlers["SecureStore"] = failing
    with pytest.raises(modules.NativeModuleError, match="keychain locked"):
        pn.SecureStore.get_item("token")
    transport.module_handlers["Clipboard"] = failing
    with pytest.raises(modules.NativeModuleError, match="keychain locked"):
        pn.Clipboard.get_string()


def test_module_event_from_native_reaches_listeners(transport: FakeTransport) -> None:
    seen: List[Any] = []
    unsubscribe = modules.native_module("NetInfo").add_listener("change", seen.append)
    transport.emit_module_event("NetInfo", "change", {"is_connected": False, "type": "none"})
    assert seen == [{"is_connected": False, "type": "none"}]
    unsubscribe()
    transport.emit_module_event("NetInfo", "change", {})
    assert len(seen) == 1


def test_python_module_registration_and_entry_points_off_device() -> None:
    modules._reset_for_tests()
    bridge._reset_for_tests()

    class Weather:
        def forecast(self, city: str) -> str:
            return f"sunny in {city}"

        async def slow(self) -> int:
            return 7

    modules.register_python_module("Weather", Weather)
    module = modules.native_module("Weather")
    assert isinstance(module, modules.PythonModule)
    assert module.call("forecast", city="Oslo") == "sunny in Oslo"
    with pytest.raises(RuntimeError, match="asynchronous"):
        module.call("slow")
    assert asyncio.run(module.call_async("slow")) == 7
    with pytest.raises(modules.NativeModuleError, match="unknown method"):
        module.call("missing")
    modules.unregister_python_module("Weather")
    # Facades call native_module() at import time, so a missing fallback
    # implementation only surfaces on the first method call.
    unresolved = modules.native_module("Weather")
    with pytest.raises(KeyError):
        unresolved.call("forecast", city="Oslo")
    # Registering afterwards makes the same facade handle work.
    modules.register_python_module("Weather", Weather)
    assert unresolved.call("forecast", city="Oslo") == "sunny in Oslo"
    modules._reset_for_tests()


def test_fallback_defaults_resolve_for_every_builtin() -> None:
    modules._reset_for_tests()
    bridge._reset_for_tests()
    for name in (
        "Device",
        "AppState",
        "Storage",
        "SecureStore",
        "Clipboard",
        "Alert",
        "Share",
        "Linking",
        "Haptics",
        "Battery",
        "NetInfo",
        "Permissions",
        "Notifications",
        "Camera",
        "Location",
        "Biometrics",
    ):
        assert isinstance(modules.native_module(name), modules.PythonModule), name
    assert modules.native_module("Device").call("info")["platform"] == "test"
    modules._reset_for_tests()


# ======================================================================
# On-device screen host
# ======================================================================


def _install_app(monkeypatch: pytest.MonkeyPatch, name: str, root: Any) -> str:
    import sys

    module = types.ModuleType(name)
    module.App = root  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, module)
    return name


def test_native_host_lifecycle_and_navigation(transport: FakeTransport, monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative import platform_metrics
    from pythonnative.hosts import native as hosts

    hosts._reset_for_tests()

    @component
    def Root() -> Element:
        return pn.Column(pn.Text("hello"), style={"flex": 1})

    path = _install_app(monkeypatch, "bridge_host_app", Root)
    metrics = {
        "width": 390.0,
        "height": 844.0,
        "insets": {"top": 0, "left": 0, "bottom": 34, "right": 0},
        "color_scheme": "dark",
    }
    result = transport.host_event(1, "create", {"path": path, "args": None, "dev_root": None, **metrics})
    host = hosts.host_for_screen(1)
    assert host is not None and host.reconciler is not None
    root_tag = result["root"]
    assert transport.views[root_tag].type_name == "Column"
    assert ("Host", "attach_root", {"screen": 1, "tag": root_tag}) in transport.calls
    assert platform_metrics.get_safe_area_insets().bottom == 34.0
    assert platform_metrics.get_window_dimensions() == (390.0, 844.0)
    assert pn.appearance.get_system_color_scheme() == "dark"
    assert host.reconciler.viewport_size == (390.0, 844.0)

    transport.host_event(1, "layout", {"width": 844.0, "height": 390.0})
    assert host.reconciler.viewport_size == (844.0, 390.0)

    transport.host_event(1, "pause")
    assert host.is_focused is False
    transport.host_event(1, "save_state")
    transport.host_event(1, "restore_state", {"state": "{}"})
    transport.host_event(1, "save_state")
    transport.host_event(1, "restore_state", {"state": "{}"})
    transport.host_event(1, "resume", {"width": 390.0, "height": 844.0})
    assert host.is_focused is True
    assert transport.host_event(1, "back_pressed") is None

    assert transport.calls[-1] == ("Host", "finish", {"screen": 1})
    host.set_screen_options({"title": "T"})
    assert transport.calls[-1] == ("Host", "set_options", {"screen": 1, "options": {"title": "T"}})

    transport.host_event(1, "destroy")
    assert hosts.host_for_screen(1) is None
    assert transport.views == {}
    pn.appearance.reset_color_scheme()
    platform_metrics.reset_safe_area_insets()
    platform_metrics.reset_window_dimensions()


def test_native_host_defers_renders_to_application_loop(
    transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pythonnative.hosts import native as hosts

    hosts._reset_for_tests()
    setters: List[Any] = []

    @component
    def Root() -> Element:
        n, set_n = use_state(0)
        setters.append(set_n)
        return pn.Text(f"n={n}")

    path = _install_app(monkeypatch, "bridge_host_defer_app", Root)
    transport.host_event(2, "create", {"path": path, "width": 100, "height": 100})
    assert transport.find("Text")[0].props["text"] == "n=0"
    setters[-1](5)
    # The state change is committed on the next main-queue turn, not inline.
    assert transport.find("Text")[0].props["text"] == "n=0"
    from pythonnative.runtime import drain

    drain()
    assert transport.find("Text")[0].props["text"] == "n=5"
    transport.host_event(2, "destroy")


def test_drawing_only_commit_skips_layout_until_geometry_changes(
    backend: BridgeBackend, transport: FakeTransport
) -> None:
    from pythonnative.profiling import Profiler

    def layout(_method: str, _args: Dict[str, Any]) -> Dict[str, Any]:
        identity = transport.commit_state.acknowledgement()
        identity.pop("ok")
        return identity | {"frames": [], "metrics": {"layout_ns": 1000, "views": 1}}

    transport.module_handlers["Layout"] = layout
    with Profiler() as profiler:
        backend.apply_mutations([CreateOp(91, "Text", {"text": "before"})])
        backend.compute_layout([91], 300, 500)
        backend.apply_mutations([UpdateOp(91, {"color": "#ff0000", "opacity": 0.5})])
        backend.compute_layout([91], 300, 500)
        assert profiler.counters["layout.requests"] == 1
        backend.apply_mutations([UpdateOp(91, {"text": "a longer label"})])
        backend.compute_layout([91], 300, 500)
        assert profiler.counters["layout.requests"] == 2
        backend.compute_layout([91], 500, 300)
        assert profiler.counters["layout.requests"] == 3
        assert profiler.counters["native.layout.views"] == 3


def test_geometry_from_an_obsolete_revision_cannot_update_the_tree(backend: BridgeBackend) -> None:
    accepted: list[Any] = []
    backend.on_layout = accepted.append
    backend.apply_mutations([CreateOp(92, "Text", {"text": "before"})])
    identity = backend._commit.acknowledgement()
    identity.pop("ok")
    backend.apply_mutations([UpdateOp(92, {"text": "after"})])
    backend.accept_layout(identity | {"frames": [[92, 0, 0, 10, 10]]})
    assert accepted == []
    current = backend._commit.acknowledgement()
    current.pop("ok")
    backend.accept_layout(current | {"frames": [[92, 0, 0, 20, 10]]})
    assert accepted == [[[92, 0, 0, 20, 10]]]
