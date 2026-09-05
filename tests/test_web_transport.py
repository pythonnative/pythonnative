"""``WebTransport``: the browser preview as the native side of the bridge.

A ``FakePage`` stands in for the JavaScript in ``devserver/static``: it
receives the frames the transport sends, answers synchronous requests
the way the page does (from another thread, since the real page answers
over the dev server's socket thread), and can raise callbacks.
"""

from __future__ import annotations

import json
import threading
import time
import types
from typing import Any, Dict, Generator, List, Tuple

import pytest

import pythonnative as pn
from pythonnative import bridge
from pythonnative.bridge import codec
from pythonnative.bridge.web import BROWSER_MODULES, WebTransport
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.native_modules import registry as modules
from pythonnative.native_views import set_registry
from pythonnative.native_views.bridge_backend import BridgeBackend


class FakePage:
    """Records everything Python sends and answers requests like the page would."""

    def __init__(self, transport: WebTransport) -> None:
        self.transport = transport
        self.sent: List[List[Any]] = []
        self.measure_size = (80.0, 20.0)
        self.viewport = {"width": 390.0, "height": 800.0, "insets": {"top": 0, "left": 0, "bottom": 34, "right": 0}}
        self.calls: List[Any] = []
        self.commands: List[Any] = []
        self.animations: List[Any] = []
        self.module_results: Dict[Tuple[str, str], Any] = {}
        self.answer_in_thread = True
        self.closed = threading.Event()

    # -- what PreviewPeer offers -------------------------------------------
    def send(self, text: str) -> None:
        message = json.loads(text)
        self.sent.append(message)
        kind = message[0]
        if kind in ("measure", "command", "animate", "call"):
            result = self._answer(message)
            reply = codec.dumps(["res", message[1], result])
            if self.answer_in_thread:
                threading.Thread(target=self.transport.on_preview_message, args=(self, reply), daemon=True).start()
            else:
                self.transport.on_preview_message(self, reply)

    def close(self) -> None:
        self.closed.set()

    # -- page behavior ------------------------------------------------------
    def _answer(self, message: List[Any]) -> Any:
        kind = message[0]
        if kind == "measure":
            return list(self.measure_size)
        if kind == "command":
            _, _, tag, name, args = message
            self.commands.append((tag, name, json.loads(args) if args else None))
            return codec.dumps({"ok": True}) if name == "get_value" else None
        if kind == "animate":
            self.animations.append(json.loads(message[3]))
            return codec.dumps({"ok": True})
        if kind == "call":
            _, _, module, method, envelope = message
            args = json.loads(envelope)["args"]
            self.calls.append((module, method, args))
            if (module, method) in self.module_results:
                return codec.dumps(self.module_results[(module, method)])
            if method in ("attach_root", "viewport"):
                return codec.dumps({"ok": True, "value": self.viewport})
            return codec.dumps({"ok": True, "value": None})
        return None

    # -- helpers ------------------------------------------------------------
    def ops(self) -> List[List[Any]]:
        out: List[List[Any]] = []
        for message in self.sent:
            if message[0] == "apply":
                out.extend(message[1])
        return out

    def dev_messages(self) -> List[Dict[str, Any]]:
        return [m[1] for m in self.sent if m[0] == "dev"]

    def callback(self, kind: str, tag: int, name: str, payload: Any) -> None:
        text = codec.dumps(["cb", kind, tag, name, payload if isinstance(payload, str) else codec.dumps(payload)])
        self.transport.on_preview_message(self, text)

    def request(self, request_id: int, kind: str, tag: int, name: str, payload: Any) -> None:
        text = codec.dumps(
            ["req", request_id, kind, tag, name, payload if isinstance(payload, str) else codec.dumps(payload)]
        )
        self.transport.on_preview_message(self, text)


@pytest.fixture
def web() -> Generator[Any, None, None]:
    from pythonnative.hosts import native as hosts

    transport = WebTransport(log=lambda line: None)
    bridge.set_transport(transport)
    backend = BridgeBackend(transport)
    set_registry(backend)
    modules._reset_for_tests()
    hosts._reset_for_tests()
    page = FakePage(transport)
    transport.on_preview_connected(page, {})
    transport.drain_main()
    yield types.SimpleNamespace(transport=transport, page=page, backend=backend)
    transport.on_preview_disconnected(page)
    transport.drain_main()
    hosts._reset_for_tests()
    modules._reset_for_tests()
    set_registry(None)
    bridge._reset_for_tests()


def _install_app(monkeypatch: pytest.MonkeyPatch, name: str, root: Any) -> str:
    import sys

    module = types.ModuleType(name)
    module.App = root  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, module)
    return name


# ----------------------------------------------------------------------
# Wire format
# ----------------------------------------------------------------------


def test_apply_forwards_the_transaction_verbatim(web: Any) -> None:
    web.transport.apply('[["c", 1, "View", {}]]')
    assert web.page.sent[-1] == ["apply", [["c", 1, "View", {}]]]


def test_measure_blocks_until_the_page_answers(web: Any) -> None:
    web.page.measure_size = (123.5, 17.0)
    assert web.transport.measure(7, 390.0, float("inf")) == (123.5, 17.0)
    message = web.page.sent[-1]
    # Infinity has no JSON spelling; the unconstrained axis travels as the 1e6 sentinel.
    assert message[0] == "measure" and message[2:] == [7, 390.0, 1e6]


def test_measure_returns_zero_when_no_page_is_attached() -> None:
    transport = WebTransport(log=lambda line: None)
    assert transport.measure(1, 10.0, 10.0) == (0.0, 0.0)
    assert transport.command(1, "focus", "{}") is None


def test_command_and_animate_round_trip_json_text(web: Any) -> None:
    assert web.transport.command(4, "focus", "{}") is None
    assert json.loads(web.transport.command(4, "get_value", '{"x": 1}') or "") == {"ok": True}
    assert web.page.commands == [(4, "focus", {}), (4, "get_value", {"x": 1})]
    assert json.loads(web.transport.animate(4, '{"op": "start", "id": 9}') or "") == {"ok": True}
    assert web.page.animations == [{"op": "start", "id": 9}]


def test_request_timeout_is_reported_not_raised(web: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative.bridge import web as web_mod

    monkeypatch.setattr(web_mod, "REQUEST_TIMEOUT_S", 0.05)
    web.page.send = lambda text: web.page.sent.append(json.loads(text))  # never answers
    assert web.transport.measure(1, 1.0, 1.0) == (0.0, 0.0)


def test_disconnect_fails_waiting_requests(web: Any) -> None:
    results: List[Any] = []
    web.page.send = lambda text: web.page.sent.append(json.loads(text))  # never answers

    def _measure() -> None:
        results.append(web.transport.measure(1, 1.0, 1.0))

    thread = threading.Thread(target=_measure)
    thread.start()
    time.sleep(0.05)
    web.transport.on_preview_disconnected(web.page)
    thread.join(timeout=2.0)
    assert results == [(0.0, 0.0)]
    assert not web.transport.connected


# ----------------------------------------------------------------------
# Module routing
# ----------------------------------------------------------------------


def test_browser_modules_go_to_the_page_and_others_fall_back_to_python(web: Any) -> None:
    web.page.module_results[("Clipboard", "get_string")] = {"ok": True, "value": "from page"}
    assert modules.native_module("Clipboard").call("get_string") == "from page"
    assert ("Clipboard", "get_string", {}) in web.page.calls
    # Storage has no browser implementation: the Python fallback serves it.
    storage = modules.native_module("Storage")
    storage.call("set", key="k", value="v")
    assert storage.call("get", key="k") == "v"
    storage.call("delete", key="k")
    assert all(module != "Storage" for module, _, _ in web.page.calls)
    assert "Host" in BROWSER_MODULES and "Alert" in BROWSER_MODULES


def test_host_post_pumps_the_main_queue_without_touching_the_page(web: Any) -> None:
    ran: List[int] = []
    bridge.post_to_main(lambda: ran.append(1))
    assert ran == []  # queued, not inline
    assert not any(m[0] == "call" for m in web.page.sent)
    web.transport.drain_main()
    assert ran == [1]


def test_python_fallback_reports_unknown_modules_and_errors(web: Any) -> None:
    from pythonnative.native_modules.registry import NativeModuleError

    with pytest.raises(NativeModuleError):
        modules.native_module("NoSuchModule").call("anything")


def test_async_python_fallbacks_settle_through_module_messages(web: Any) -> None:
    from pythonnative.runtime import run_blocking

    async def _go() -> Any:
        return await modules.native_module("Storage").call_async("get", key="missing")

    assert run_blocking(_go(), timeout=2.0) is None


# ----------------------------------------------------------------------
# Callbacks from the page
# ----------------------------------------------------------------------


def test_events_from_the_page_reach_handlers_on_the_main_thread(web: Any) -> None:
    from pythonnative.events import get_event_registry

    seen: List[Any] = []
    get_event_registry().set_events(42, {"on_press": lambda *args: seen.append(args)})
    web.page.callback("event", 42, "on_press", [])
    assert seen == []  # delivered on the main loop, not on the socket thread
    web.transport.drain_main()
    assert seen == [()]


def test_requests_from_the_page_are_answered(web: Any) -> None:
    from pythonnative.events import get_event_registry

    get_event_registry().set_events(5, {"on_bind_row": lambda payload: {"root": 77}})
    web.page.request(3, "event", 5, "on_bind_row", [{"index": 0}])
    web.transport.drain_main()
    assert web.page.sent[-1][:2] == ["res", 3]
    assert json.loads(web.page.sent[-1][2]) == {"root": 77}


def test_dev_messages_and_peer_changes_run_hooks_on_the_main_thread(web: Any) -> None:
    devs: List[Dict[str, Any]] = []
    peers: List[bool] = []
    web.transport.on_dev_message = devs.append
    web.transport.on_peer_changed = peers.append
    web.transport.on_preview_message(web.page, json.dumps(["dev", {"type": "log", "text": "hi"}]))
    web.transport.on_preview_message(web.page, "not json")
    web.transport.on_preview_message(web.page, json.dumps(["mystery"]))
    web.transport.drain_main()
    assert devs == [{"type": "log", "text": "hi"}]
    web.transport.send_dev({"type": "hello", "entry": "app.main"})
    assert web.page.sent[-1] == ["dev", {"type": "hello", "entry": "app.main"}]
    other = FakePage(web.transport)
    web.transport.on_preview_connected(other, {})
    web.transport.drain_main()
    assert peers == [True]
    web.transport.on_preview_disconnected(other)
    web.transport.drain_main()
    assert peers == [True, False]


def test_stale_peer_messages_are_ignored(web: Any) -> None:
    stale = FakePage(web.transport)
    seen: List[Any] = []
    web.transport.on_dev_message = seen.append
    web.transport.on_preview_message(stale, json.dumps(["dev", {"type": "log"}]))
    web.transport.drain_main()
    assert seen == []


def test_gesture_stream_drives_the_python_arbiter(web: Any) -> None:
    from pythonnative.events import get_event_registry

    taps: List[Any] = []
    get_event_registry().set_events(9, {"gesture:0": lambda payload: taps.append(payload)})
    specs = [{"kind": "tap", "n_taps": 1, "max_distance": 20.0}]
    t = web.transport

    def _pointer(phase: str, x: float, y: float) -> None:
        t.on_preview_message(web.page, json.dumps(["gesture", 9, phase, {"id": 1, "x": x, "y": y, "specs": specs}]))

    _pointer("down", 10, 10)
    _pointer("up", 11, 10)
    t.drain_main(timeout=0.5)
    assert len(taps) == 1
    _pointer("clear", 0, 0)
    t.drain_main()
    assert 9 not in t._gestures


# ----------------------------------------------------------------------
# Full mount: the page hosts a screen rendered by the reconciler
# ----------------------------------------------------------------------


def test_screen_mounts_through_the_page(web: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative import platform_metrics
    from pythonnative.hosts import native as hosts

    pressed: List[int] = []

    @component
    def Root() -> Element:
        count, set_count = pn.use_state(0)

        def tap() -> None:
            pressed.append(1)
            set_count(count + 1)

        return pn.Column(
            pn.Text(f"count {count}"),
            pn.Button("Tap", on_press=tap),
            style={"flex": 1},
        )

    path = _install_app(monkeypatch, "web_preview_app", Root)
    payload = {"path": path, "args": None, **web.page.viewport, "color_scheme": "light"}
    web.page.request(1, "host", 1, "create", payload)
    web.transport.drain_main(timeout=1.0)

    reply = next(m for m in web.page.sent if m[0] == "res" and m[1] == 1)
    root_tag = json.loads(reply[2])["root"]
    created = {op[1]: op[2] for op in web.page.ops() if op[0] == "c"}
    assert created[root_tag] == "Column"
    assert "Text" in created.values() and "Button" in created.values()
    assert ("Host", "attach_root", {"screen": 1, "tag": root_tag}) in web.page.calls
    # Children get frames (the root fills the viewport), and the Text was measured by the page.
    framed = {op[1] for op in web.page.ops() if op[0] == "f"}
    assert framed >= {tag for tag in created if tag != root_tag}
    assert any(m[0] == "measure" for m in web.page.sent)
    assert platform_metrics.get_window_dimensions() == (390.0, 800.0)

    host = hosts.host_for_screen(1)
    assert host is not None
    button_tag = next(tag for tag, name in created.items() if name == "Button")
    text_tag = next(tag for tag, name in created.items() if name == "Text")
    web.page.callback("event", button_tag, "on_press", [])
    web.transport.drain_main(timeout=1.0)
    assert pressed == [1]
    updates = [op for op in web.page.ops() if op[0] == "u" and op[1] == text_tag]
    assert updates and updates[-1][2]["text"] == "count 1"

    web.page.callback("host", 1, "layout", {"width": 800.0, "height": 390.0})
    web.transport.drain_main(timeout=1.0)
    assert host.reconciler is not None and host.reconciler.viewport_size == (800.0, 390.0)

    web.page.callback("host", 1, "destroy", {})
    web.transport.drain_main(timeout=1.0)
    assert hosts.host_for_screen(1) is None
    assert any(op[0] == "d" and op[1] == root_tag for op in web.page.ops())
    platform_metrics.reset_window_dimensions()
    platform_metrics.reset_safe_area_insets()
    pn.appearance.reset_color_scheme()


def test_backend_reset_forgets_every_view_when_the_page_goes_away(web: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    @component
    def Root() -> Element:
        return pn.Text("bye")

    path = _install_app(monkeypatch, "web_preview_reset_app", Root)
    web.page.request(1, "host", 1, "create", {"path": path, **web.page.viewport})
    web.transport.drain_main(timeout=1.0)
    assert web.backend.live_view_count() > 0
    from pythonnative.hosts.native import live_hosts

    for host in list(live_hosts()):
        host.on_destroy()
    web.backend.reset()
    assert web.backend.live_view_count() == 0
