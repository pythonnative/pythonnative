"""``WebTransport``: the browser preview as the native side of the bridge.

A ``FakePage`` stands in for the JavaScript in ``devserver/static``. The
real page runs the renderer core as WebAssembly; the fake answers the same
requests with the host build of that core (``FakeTransport``), so the
transport carries real acknowledgements, layout, command results, events,
and gestures. Requests are answered from the page's side of the socket
(another thread when ``answer_in_thread`` is set, as the dev server's socket
thread does), and everything the core emits comes back as page callbacks.
"""

from __future__ import annotations

import json
import threading
import time
import types
from typing import Any, Dict, Generator, List, Optional, Tuple

import pytest

import pythonnative as pn
from pythonnative import bridge
from pythonnative.bridge import PROTOCOL_VERSION, codec
from pythonnative.bridge.core import POINTER_DOWN, POINTER_UP
from pythonnative.bridge.fake import FakeTransport
from pythonnative.bridge.web import BROWSER_MODULES, WebTransport
from pythonnative.component import component
from pythonnative.element import Element
from pythonnative.native_modules import registry as modules
from pythonnative.native_views import set_backend
from pythonnative.native_views.bridge_backend import BridgeBackend, CommitError

CORE_REQUESTS = ("load_contracts", "commit", "layout", "command", "animate", "measure")


class FakePage:
    """Answers the transport's requests like the page: core calls go to a host core."""

    def __init__(self, transport: WebTransport) -> None:
        self.transport = transport
        self.core = FakeTransport(surface=1)
        # Messages the core emits, and command results, go back as page callbacks.
        self.core.callback = self._forward
        self.sent: List[List[Any]] = []
        self.viewport = {"width": 390.0, "height": 800.0, "insets": {"top": 0, "left": 0, "bottom": 34, "right": 0}}
        self.calls: List[Any] = []
        self.module_results: Dict[Tuple[str, str], Any] = {}
        self.answer_in_thread = False
        self.closed = threading.Event()

    # -- what PreviewPeer offers -------------------------------------------
    def send(self, text: str) -> None:
        message = json.loads(text)
        self.sent.append(message)
        if message[0] in (*CORE_REQUESTS, "call"):
            reply = codec.dumps(["res", message[1], self._answer(message)])
            if self.answer_in_thread:
                threading.Thread(target=self.transport.on_preview_message, args=(self, reply), daemon=True).start()
            else:
                self.transport.on_preview_message(self, reply)

    def close(self) -> None:
        self.closed.set()

    # -- page behavior ------------------------------------------------------
    def _answer(self, message: List[Any]) -> Any:
        kind = message[0]
        if kind == "load_contracts":
            try:
                self.core.load_contracts(message[2])
            except RuntimeError as error:
                return str(error)
            return None
        if kind == "commit":
            return self.core.commit(message[2])
        if kind == "layout":
            return self.core.layout(message[2])
        if kind == "command":
            _, _, surface, tag, name, args, call_id = message
            return self.core.command(surface, tag, name, args, call_id)
        if kind == "animate":
            _, _, surface, tag, request = message
            return self.core.animate(surface, tag, request)
        if kind == "measure":
            _, _, surface, tag = message
            return self.core.measure(surface, tag)
        _, _, module, method, envelope = message
        args = json.loads(envelope)["args"]
        self.calls.append((module, method, args))
        if (module, method) in self.module_results:
            return codec.dumps(self.module_results[(module, method)])
        if method in ("attach_root", "viewport"):
            return codec.dumps({"ok": True, "value": self.viewport})
        return codec.dumps({"ok": True, "value": None})

    def _forward(self, kind: str, tag: int, name: str, payload: str) -> None:
        self.transport.on_preview_message(self, codec.dumps(["cb", kind, tag, name, payload]))

    # -- helpers ------------------------------------------------------------
    def envelopes(self) -> List[Dict[str, Any]]:
        return [json.loads(message[2]) for message in self.sent if message[0] == "commit"]

    def ops(self) -> List[List[Any]]:
        return [op for envelope in self.envelopes() for op in envelope["ops"]]

    def callback(self, kind: str, tag: int, name: str, payload: Any) -> None:
        """A callback the page raises itself (host lifecycle, module events)."""
        text = payload if isinstance(payload, str) else codec.dumps(payload)
        self.transport.on_preview_message(self, codec.dumps(["cb", kind, tag, name, text]))


@pytest.fixture
def web() -> Generator[Any, None, None]:
    from pythonnative.hosts import native as hosts

    transport = WebTransport(log=lambda line: None)
    bridge.set_transport(transport)
    backend = BridgeBackend(transport)
    set_backend(backend)
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
    set_backend(None)
    bridge._reset_for_tests()


def _install_app(monkeypatch: pytest.MonkeyPatch, name: str, root: Any) -> str:
    import sys

    module = types.ModuleType(name)
    module.App = root  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, module)
    return name


def _envelope(revision: int, *ops: List[Any], application: str = "test") -> str:
    return codec.dumps(
        {"version": PROTOCOL_VERSION, "application": application, "surface": 1, "revision": revision, "ops": list(ops)}
    )


# ----------------------------------------------------------------------
# The renderer core over the socket
# ----------------------------------------------------------------------


def test_the_transport_satisfies_the_bridge_protocol() -> None:
    transport: bridge.Transport = WebTransport(log=lambda line: None)
    assert transport.name == "web" and transport.asynchronous_commits
    assert transport.protocol_version() == PROTOCOL_VERSION


def test_commits_go_to_the_page_core_as_text_and_return_its_acknowledgement(web: Any) -> None:
    bridge.ensure_contracts(web.transport)
    assert [m[0] for m in web.page.sent if m[0] == "load_contracts"]
    text = _envelope(1, ["c", 1, "View", {}])
    ack = json.loads(web.transport.commit(text))
    assert ack["ok"] and (ack["application"], ack["surface"], ack["revision"]) == ("test", 1, 1)
    # The envelope travels as the JSON text Python serialized; the page parses it once, in the core.
    assert web.page.sent[-1] == ["commit", web.page.sent[-1][1], text]
    assert web.page.core.find("View")


def test_rejections_name_the_component_and_prop(web: Any) -> None:
    bridge.ensure_contracts(web.transport)
    ack = json.loads(web.transport.commit(_envelope(1, ["c", 1, "Text", {"colour": "red"}])))
    assert ack["ok"] is False and ack["failed"] is False and ack["op"] == 0
    assert "Text" in ack["error"] and "colour" in ack["error"]


def test_contracts_reload_into_a_new_page(web: Any) -> None:
    bridge.ensure_contracts(web.transport)
    loads = lambda: sum(1 for m in web.page.sent if m[0] == "load_contracts")  # noqa: E731
    first = loads()
    bridge.ensure_contracts(web.transport)
    assert loads() == first  # unchanged contracts load once per page
    web.transport.on_preview_disconnected(web.page)
    web.page = FakePage(web.transport)
    web.transport.on_preview_connected(web.page, {})
    web.transport.drain_main()
    bridge.ensure_contracts(web.transport)
    assert loads() >= 1


def test_a_rejected_contract_document_raises(web: Any) -> None:
    with pytest.raises(RuntimeError, match="rejected the component contracts"):
        web.transport.load_contracts("{not json")


def test_layout_command_animate_and_measure_round_trip(web: Any) -> None:
    bridge.ensure_contracts(web.transport)
    web.transport.commit(
        _envelope(1, ["c", 1, "Column", {"_pn_layout": True}], ["c", 2, "TextInput", {"value": "a"}], ["i", 1, 2, 0])
    )
    layout = json.loads(web.transport.layout(codec.dumps({"surface": 1, "roots": [1], "width": 300, "height": 500})))
    assert layout["ok"] and layout["value"]["frames"][0][0] == 1
    web.page.core.command_results["get_value"] = "typed"
    assert json.loads(web.transport.command(1, 2, "get_value", "{}", 7)) == {"ok": True, "queued": True}
    assert web.page.core.commands[-1][:2] == (2, "get_value")
    reply = json.loads(web.transport.animate(1, 2, codec.dumps({"op": "set", "prop": "opacity", "value": 0.5})))
    assert reply["ok"] and (2, "opacity", 0.5) in web.page.core.writes
    frame = json.loads(web.transport.measure(1, 2))
    assert frame["frame"][2] == 300 and len(frame["window"]) == 4
    assert json.loads(web.transport.command(1, 2, "no_such_command", "{}", 8))["ok"] is False


def test_requests_without_a_page_answer_like_a_failed_core() -> None:
    transport = WebTransport(log=lambda line: None)
    for reply in (
        transport.commit(_envelope(1)),
        transport.layout("{}"),
        transport.command(1, 1, "focus", "{}", 1),
        transport.animate(1, 1, "{}"),
    ):
        body = json.loads(reply)
        assert body["ok"] is False and "no browser preview page" in body["error"]
    assert transport.measure(1, 1) == "null"
    transport.load_contracts("{}")  # nothing to compile into until a page connects


def test_request_timeout_is_reported_not_raised(web: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative.bridge import web as web_mod

    monkeypatch.setattr(web_mod, "REQUEST_TIMEOUT_S", 0.05)
    web.page.send = lambda text: web.page.sent.append(json.loads(text))  # never answers
    assert json.loads(web.transport.command(1, 1, "focus", "{}", 1))["ok"] is False


def test_disconnect_fails_waiting_requests(web: Any) -> None:
    results: List[Any] = []
    web.page.send = lambda text: web.page.sent.append(json.loads(text))  # never answers

    def _commit() -> None:
        results.append(json.loads(web.transport.commit(_envelope(1))))

    thread = threading.Thread(target=_commit)
    thread.start()
    time.sleep(0.05)
    web.transport.on_preview_disconnected(web.page)
    thread.join(timeout=2.0)
    assert len(results) == 1 and results[0]["ok"] is False
    assert not web.transport.connected


def test_replies_from_the_socket_thread_settle_requests(web: Any) -> None:
    web.page.answer_in_thread = True
    bridge.ensure_contracts(web.transport)
    assert json.loads(web.transport.commit(_envelope(1, ["c", 1, "View", {}])))["ok"]


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
    # Layout runs in the page's core; there is no Layout module.
    assert "Layout" not in BROWSER_MODULES


def test_host_post_pumps_the_main_queue_without_touching_the_page(web: Any) -> None:
    ran: List[int] = []
    web.transport.post_to_application(lambda: ran.append(1))
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


def test_new_device_modules_are_served_by_the_page(web: Any) -> None:
    for name in ("Keyboard", "AccessibilityInfo", "Localization", "Device"):
        assert name in BROWSER_MODULES
    web.page.module_results[("Keyboard", "is_visible")] = {"ok": True, "value": True}
    web.page.module_results[("Localization", "get_timezone")] = {"ok": True, "value": "Europe/Paris"}
    assert modules.native_module("Keyboard").call("is_visible") is True
    assert modules.native_module("Localization").call("get_timezone") == "Europe/Paris"
    assert ("Keyboard", "is_visible", {}) in web.page.calls
    assert ("Localization", "get_timezone", {}) in web.page.calls


# ----------------------------------------------------------------------
# Callbacks from the page
# ----------------------------------------------------------------------


def _mount(web: Any, *ops: Any) -> None:
    from pythonnative.mutations import CreateOp

    web.backend.apply_mutations([CreateOp(*op) for op in ops])
    web.transport.drain_main()


def test_events_from_the_page_core_reach_handlers_on_the_main_thread(web: Any) -> None:
    from pythonnative.events import get_event_registry

    seen: List[Any] = []
    _mount(web, (42, "Button", {"title": "Press", "_pn_events": ["on_press"]}))
    get_event_registry().set_events(42, {"on_press": lambda *args: seen.append(args)})
    web.page.core.fire(42, "on_press")
    assert seen == []  # delivered on the main loop, not on the socket thread
    web.transport.drain_main()
    assert seen == [()]


def test_page_callbacks_are_never_answered(web: Any) -> None:
    from pythonnative.events import get_event_registry

    _mount(web, (5, "VirtualList", {"dataset": {"base": 0, "revision": 1, "changes": [["reset", []]]}}))
    seen: List[Any] = []

    def bind_row(payload: Any) -> Dict[str, int]:
        seen.append(payload)
        return {"root": 77}

    get_event_registry().set_events(5, {"on_bind_row": bind_row})
    before = len(web.page.sent)
    web.page.core.fire(
        5, "on_bind_row", {"index": 0, "key": "a", "revision": 1, "extent": 44.0, "width": 390.0, "sticky": -1}
    )
    web.transport.drain_main()
    assert len(seen) == 1 and _field(seen[0], "index") == 0
    assert not any(message[0] == "res" for message in web.page.sent[before:])


def test_command_results_resolve_awaiting_futures(web: Any) -> None:
    import asyncio

    _mount(web, (6, "TextInput", {"value": "a"}))
    web.page.core.command_results["get_value"] = "typed"
    future = web.backend.command(6, "get_value")
    web.transport.drain_main()
    assert future.done() and future.result() == "typed"
    assert isinstance(future, asyncio.Future)
    # The page's core rejects a command for a view it doesn't hold.
    web.backend._types[77] = "TextInput"
    with pytest.raises(CommitError, match="stale view 77"):
        web.backend.command(77, "focus")


def test_gestures_are_recognized_by_the_page_core(web: Any) -> None:
    from pythonnative.events import get_event_registry

    taps: List[Any] = []
    _mount(web, (9, "View", {"gestures": [{"kind": "tap", "n_taps": 1, "max_distance": 20.0}]}))
    get_event_registry().set_events(9, {"gesture:0": lambda payload: taps.append(payload)})
    # The page forwards view-local and window coordinates to pn_core_pointer.
    web.page.core.pointer(9, [(POINTER_DOWN, 1, 10.0, 10.0, 110.0, 210.0, 1.0)])
    web.page.core.pointer(9, [(POINTER_UP, 1, 11.0, 10.0, 111.0, 210.0, 1.05)])
    web.transport.drain_main()
    ended = [tap for tap in taps if _field(tap, "state") == "ended"]
    assert len(ended) == 1
    assert _field(ended[0], "absolute_x") - _field(ended[0], "x") == 100.0
    assert _field(ended[0], "absolute_y") - _field(ended[0], "y") == 200.0


def _field(payload: Any, name: str) -> Any:
    return payload[name] if isinstance(payload, dict) else getattr(payload, name)


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


# ----------------------------------------------------------------------
# Full mount: the page hosts a screen rendered by the reconciler
# ----------------------------------------------------------------------


def _created(web: Any) -> Dict[int, str]:
    return {op[1]: op[2] for op in web.page.ops() if op[0] == "c"}


def _root_tag(web: Any) -> Optional[int]:
    return next(
        (args["tag"] for module, method, args in web.page.calls if (module, method) == ("Host", "attach_root")), None
    )


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
    web.page.callback("host", 1, "create", payload)
    web.transport.drain_main(timeout=1.0)

    root_tag = _root_tag(web)
    created = _created(web)
    assert root_tag is not None and created[root_tag] == "Column"
    assert "Text" in created.values() and "Button" in created.values()
    # The page's core laid the root out against the viewport and measured the leaves.
    assert any(envelope.get("layout", {}).get("roots") == [root_tag] for envelope in web.page.envelopes())
    assert {component for _, component in web.page.core.measured} >= {"Text", "Button"}
    text_view = web.page.core.find("Text")[0]
    assert text_view.frame[2] == 390.0
    window = platform_metrics.get_window_dimensions()
    assert (window.width, window.height) == (390.0, 800.0)

    host = hosts.host_for_screen(1)
    assert host is not None
    button_tag = next(tag for tag, name in created.items() if name == "Button")
    web.page.core.fire(button_tag, "on_press")
    web.transport.drain_main(timeout=1.0)
    from pythonnative.runtime import drain

    drain()
    assert pressed == [1]
    assert web.page.core.find("Text")[0].props["text"] == "count 1"

    web.page.callback("host", 1, "layout", {"width": 800.0, "height": 390.0})
    web.transport.drain_main(timeout=1.0)
    assert host.reconciler is not None and host.reconciler.viewport_size == (800.0, 390.0)

    web.page.callback("host", 1, "destroy", {})
    web.transport.drain_main(timeout=1.0)
    assert hosts.host_for_screen(1) is None
    assert any(op[0] == "d" and op[1] == root_tag for op in web.page.ops())
    assert root_tag not in web.page.core.views
    platform_metrics.reset_window_dimensions()
    platform_metrics.reset_safe_area_insets()
    pn.appearance.reset_color_scheme()


def test_backend_reset_forgets_every_view_when_the_page_goes_away(web: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    @component
    def Root() -> Element:
        return pn.Text("bye")

    path = _install_app(monkeypatch, "web_preview_reset_app", Root)
    web.page.callback("host", 1, "create", {"path": path, **web.page.viewport})
    web.transport.drain_main(timeout=1.0)
    assert web.backend.live_view_count() > 0
    from pythonnative.hosts.native import live_hosts

    for host in list(live_hosts()):
        host.on_destroy()
    web.backend.reset()
    assert web.backend.live_view_count() == 0
