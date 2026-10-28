"""The devtools agent: answer DevTools and publish what the app is doing.

One [`Agent`][pythonnative.devtools.agent.Agent] runs in every dev client
(PythonNative Go, a project's debug build) and in the browser preview's
process. The dev server forwards DevTools requests to it with
[`Agent.dispatch`][pythonnative.devtools.agent.Agent.dispatch], and the
agent publishes events back through the ``publish`` callback its owner
supplies: the dev client sends them over the dev session, and the preview
hands them to the server directly.

Requests run on the application loop, so they see a consistent tree and
may await. See the method table in RFC 0006 for the request names.

The agent also owns the device-side development UI, through the native
``DevSupport`` module: the dev menu, the element inspector, the
highlight outline, and the performance monitor.
"""

from __future__ import annotations

import asyncio
import os
import threading
import traceback
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .. import diagnostics
from . import inspector
from .console import Console
from .perf import Sampler

__all__ = ["Agent", "MenuItem", "current", "install", "uninstall"]

Publish = Callable[[str, Any], None]
Reply = Callable[[Optional[Any], Optional[str]], None]

_current: Optional["Agent"] = None


def current() -> Optional["Agent"]:
    """The process's agent, if one is installed."""
    return _current


class MenuItem:
    """One dev menu entry."""

    def __init__(self, title: str, action: Callable[[], Any]) -> None:
        self.title = title
        self.action = action


class Agent:
    """Serve DevTools requests and publish app events.

    Args:
        publish: ``publish(topic, data)``; called from any thread.
        kind: ``"go"``, ``"app"``, or ``"preview"``; shapes the dev menu.
        disconnect: Called by the dev menu's Disconnect item (Go only).
        reload: Remounts the app; defaults to reloading the app's modules
            and remounting every screen.
    """

    def __init__(
        self,
        publish: Publish,
        *,
        kind: str = "app",
        disconnect: Optional[Callable[[], None]] = None,
        reload: Optional[Callable[[], None]] = None,
    ) -> None:
        self.publish = publish
        self.kind = kind
        self._disconnect = disconnect
        self._reload = reload
        self.console = Console()
        self.sampler = Sampler(self._publish_perf, self._frame_stats)
        self.inspecting = False
        self.perf_monitor = False
        self.perf_panel = False
        self.selected: Optional[int] = None
        self._unsubscribe: List[Callable[[], None]] = []
        self._native_enabled = False
        self._menu_open = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to warnings, errors, network requests, and native dev events."""
        from .. import net

        self._unsubscribe.append(diagnostics.add_listener(self._on_problem))
        self._unsubscribe.append(net.observe_requests(self._on_request))
        self._enable_native()

    def stop(self) -> None:
        """Undo [`start`][pythonnative.devtools.agent.Agent.start]."""
        for remove in self._unsubscribe:
            try:
                remove()
            except Exception:
                pass
        self._unsubscribe = []

    def _devsupport(self) -> Any:
        from ..native_modules.registry import native_module

        return native_module("DevSupport")

    def _enable_native(self) -> None:
        """Turn on the native menu triggers and listen for dev events."""
        from ..utils import IS_NATIVE, IS_WEB

        if not (IS_NATIVE or IS_WEB) or self._native_enabled:
            return
        try:
            module = self._devsupport()
            self._unsubscribe.append(module.add_listener("menu", lambda _payload=None: self._on_menu_trigger()))
            self._unsubscribe.append(module.add_listener("inspect", self._on_inspect_tap))
            self._unsubscribe.append(module.add_listener("inspect_done", lambda _payload=None: self._inspect_done()))
            self._unsubscribe.append(
                module.add_listener("reload", lambda _payload=None: self.dispatch("reload", {}, _ignore))
            )
            if not IS_WEB:
                # The preview's toolbar and shortcuts send menu events on
                # their own; native hosts start listening for shakes here.
                module.call("enable")
            self._native_enabled = True
        except Exception:
            diagnostics.swallowed("devtools.enable_native")

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def dispatch(self, method: str, params: Optional[Dict[str, Any]], reply: Reply) -> None:
        """Run request ``method`` on the application loop and ``reply(result, error)``.

        Safe to call from any thread. ``reply`` runs on the application
        loop.
        """
        from ..runtime import call_threadsafe

        def run() -> None:
            asyncio.get_running_loop().create_task(self._serve(method, params or {}, reply))

        call_threadsafe(run)

    async def _serve(self, method: str, params: Dict[str, Any], reply: Reply) -> None:
        handler = getattr(self, f"rpc_{method}", None)
        if handler is None:
            reply(None, f"unknown devtools method {method!r}")
            return
        try:
            result = handler(**params)
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as exc:
            reply(None, f"{type(exc).__name__}: {exc}")
            return
        reply(result, None)

    async def request(self, method: str, **params: Any) -> Any:
        """Call a request handler directly (tests and the preview)."""
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        def reply(result: Optional[Any], error: Optional[str]) -> None:
            if error is not None:
                future.set_exception(RuntimeError(error))
            else:
                future.set_result(result)

        await self._serve(method, params, reply)
        return await future

    # -- tree ------------------------------------------------------------

    def rpc_tree(self) -> Dict[str, Any]:
        """Every live screen's component tree and the selected node."""
        return {"screens": inspector.tree(), "selected": self.selected}

    def _node(self, id: int) -> Any:
        node = inspector.find_node(int(id))
        if node is None:
            raise LookupError("that node is no longer mounted")
        return node

    def rpc_inspect(self, id: int) -> Dict[str, Any]:
        """One node's props, hooks, context, frame, and source; it becomes the selection."""
        node = self._node(id)
        self.selected = int(id)
        self.console.select(node)
        return inspector.inspect_node(node)

    def rpc_set_state(self, id: int, index: int, value: str) -> bool:
        """Replace a ``use_state`` slot of node ``id`` with a Python literal."""
        inspector.set_state(self._node(id), int(index), str(value))
        return True

    def rpc_highlight(self, id: Optional[int] = None) -> bool:
        """Outline node ``id`` on screen, or clear the outline when ``id`` is ``None``."""
        if id is None:
            self._call_native("highlight", tag=None, label="")
            return True
        node = inspector.find_node(int(id))
        if node is None:
            return False
        tag = inspector.native_root_tag(node)
        if tag is None:
            return False
        self._call_native("highlight", tag=tag, label=node.label)
        return True

    def rpc_set_inspecting(self, enabled: bool) -> bool:
        """Turn the on-device element inspector on or off."""
        self.inspecting = bool(enabled)
        self._call_native("set_inspecting", enabled=self.inspecting)
        if not self.inspecting:
            self._call_native("highlight", tag=None, label="")
        self.publish("inspecting", {"enabled": self.inspecting})
        return self.inspecting

    # -- console ---------------------------------------------------------

    async def rpc_eval(self, code: str) -> Dict[str, Any]:
        """Evaluate ``code`` in the REPL namespace (see ``Console.evaluate``)."""
        if self.selected is not None:
            self.console.select(inspector.find_node(self.selected))
        return await self.console.evaluate(str(code))

    # -- app control -----------------------------------------------------

    def rpc_reload(self) -> bool:
        """Remount the app with fresh state."""
        if self._reload is not None:
            self._reload()
        else:
            reload_app()
        return True

    def rpc_menu(self) -> bool:
        """Show the dev menu."""
        self.open_menu()
        return True

    def rpc_perf(self, enabled: bool, monitor: Optional[bool] = None) -> Dict[str, Any]:
        """Turn the DevTools panel's sampling (and optionally the on-device monitor) on or off."""
        if monitor is not None:
            self.set_perf_monitor(bool(monitor))
        if bool(enabled) != self.perf_panel:
            self.perf_panel = bool(enabled)
            if self.perf_panel:
                self.sampler.acquire()
            else:
                self.sampler.release()
        return {"panel": self.perf_panel, "monitor": self.perf_monitor}

    def rpc_trace(self, action: str) -> Any:
        """``"start"`` recording a Chrome trace, or ``"stop"`` and return it."""
        if action == "start":
            self.sampler.start_trace()
            return True
        if action == "stop":
            return self.sampler.stop_trace()
        raise ValueError(f"unknown trace action {action!r}")

    async def rpc_debug(self, host_paths: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start the in-process debug adapter; returns ``{"port"}``."""
        from .debugger import start

        # Starting pydevd installs tracing in every thread and can take a
        # few seconds; keep the application loop responsive meanwhile.
        port = await asyncio.to_thread(start, host_paths)
        return {"port": port}

    def rpc_status(self) -> Dict[str, Any]:
        """What the agent is doing: inspector, monitor, sampling, debugger."""
        from .debugger import attached

        return {
            "kind": self.kind,
            "inspecting": self.inspecting,
            "perf_monitor": self.perf_monitor,
            "perf_panel": self.perf_panel,
            "debugger_attached": attached(),
        }

    # ------------------------------------------------------------------
    # Native dev UI
    # ------------------------------------------------------------------

    def _call_native(self, method: str, **args: Any) -> Any:
        try:
            return self._devsupport().call(method, **args)
        except Exception:
            diagnostics.swallowed(f"devtools.DevSupport.{method}")
            return None

    def _frame_stats(self) -> Optional[Dict[str, Any]]:
        from ..utils import IS_NATIVE

        if not IS_NATIVE:
            return None
        result = self._call_native("frame_stats")
        return result if isinstance(result, dict) else None

    def _publish_perf(self, sample: Dict[str, Any]) -> None:
        if self.perf_panel:
            self.publish("perf", sample)
        if self.perf_monitor:
            self._call_native("set_perf_monitor", visible=True, lines=self.sampler.monitor_lines())

    def set_perf_monitor(self, visible: bool) -> None:
        """Show or hide the floating on-device performance monitor."""
        if visible == self.perf_monitor:
            return
        self.perf_monitor = visible
        if visible:
            self.sampler.acquire()
            self._call_native("set_perf_monitor", visible=True, lines=self.sampler.monitor_lines())
        else:
            self.sampler.release()
            self._call_native("set_perf_monitor", visible=False, lines=[])
        self.publish("perf_monitor", {"visible": visible})

    def _inspect_done(self) -> None:
        from ..runtime import call_threadsafe

        call_threadsafe(lambda: self.rpc_set_inspecting(False))

    def _on_inspect_tap(self, payload: Any) -> None:
        tag = payload.get("tag") if isinstance(payload, dict) else None
        if tag is None:
            return
        node = inspector.find_node_by_tag(int(tag))
        if node is None:
            return
        owner = inspector.owner_component(node) or node
        path = inspector.node_label_path(node)
        self.selected = id(owner)
        self.console.select(owner)
        label = " › ".join(path[-4:])
        self._call_native("highlight", tag=int(tag), label=label)
        self.publish("select", {"id": id(owner), "native_id": id(node), "path": path})

    # -- menu ------------------------------------------------------------

    def _on_menu_trigger(self) -> None:
        if self._menu_open:
            return
        self.open_menu()

    def menu_items(self) -> List[MenuItem]:
        """The dev menu's entries, in order."""
        items = [
            MenuItem("Reload", self.rpc_reload),
            MenuItem("Open DevTools on your computer", lambda: self.publish("open_devtools", {})),
            MenuItem(
                "Hide element inspector" if self.inspecting else "Show element inspector",
                lambda: self.rpc_set_inspecting(not self.inspecting),
            ),
            MenuItem(
                "Hide performance monitor" if self.perf_monitor else "Show performance monitor",
                lambda: self.set_perf_monitor(not self.perf_monitor),
            ),
            MenuItem("Debug with VS Code", self._debug_from_menu),
        ]
        if self.kind == "go" and self._disconnect is not None:
            items.append(MenuItem("Disconnect", self._disconnect))
        return items

    def menu_subtitle(self) -> str:
        """The dev menu's message: what this client runs and where it's connected."""
        from .. import devclient

        client = devclient.current()
        where = f"Connected to {client.server_label}" if client is not None and client.state == "connected" else ""
        runs = {"go": "PythonNative Go", "app": "Development build", "preview": "Browser preview"}.get(self.kind, "")
        return " · ".join(part for part in (runs, where) if part)

    def open_menu(self) -> None:
        """Show the dev menu (from any thread)."""
        from ..runtime import call_threadsafe

        def show() -> None:
            asyncio.get_running_loop().create_task(self._show_menu())

        call_threadsafe(show)

    async def _show_menu(self) -> None:
        if self._menu_open:
            return
        self._menu_open = True
        items = self.menu_items()
        try:
            from ..alerts import Alert

            title = await Alert.choose(
                "PythonNative", [item.title for item in items], message=self.menu_subtitle(), cancel_label="Cancel"
            )
        except Exception:
            diagnostics.swallowed("devtools.show_menu")
            title = None
        finally:
            self._menu_open = False
        chosen = next((item for item in items if item.title == title), None)
        if chosen is not None:
            try:
                result = chosen.action()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                if not diagnostics.report_error(exc, phase="dev menu"):
                    traceback.print_exc()

    def _debug_from_menu(self) -> None:
        self.publish("debug_target", {})
        message = (
            "In VS Code, run the 'PythonNative: Attach' configuration. It connects to port 5678 on your "
            "computer, and pn start forwards the session to this device."
        )
        try:
            from ..alerts import Alert

            Alert.show("Debug with VS Code", message)
        except Exception:
            print(f"[pn dev] {message}")

    # ------------------------------------------------------------------
    # Event sources
    # ------------------------------------------------------------------

    def _on_problem(self, report: Any) -> None:
        try:
            self.publish("problem", report.to_dict())
        except Exception:
            pass

    def _on_request(self, record: Dict[str, Any]) -> None:
        self.publish("network", record)


def _ignore(_result: Optional[Any], _error: Optional[str]) -> None:
    pass


# ======================================================================
# Reload
# ======================================================================


def reload_app() -> None:
    """Re-import the app's modules and remount every screen with fresh state."""
    import sys

    from ..hosts import live_hosts
    from ..hot_reload import ModuleReloader

    hosts = list(live_hosts())
    entry = os.environ.get("PN_ENTRY_MODULE") or (hosts[0].component_path if hosts else "app.main")
    top = entry.split(".")[0]
    modules = sorted((name for name in sys.modules if name == top or name.startswith(top + ".")), key=len)
    reloaded = ModuleReloader.reload_modules(modules) or modules
    for host in hosts:
        try:
            host.refresh(reloaded, force_remount=True)
        except Exception as exc:
            host.show_redbox(exc, phase="reload")


# ======================================================================
# Process-wide agent
# ======================================================================


def install(publish: Publish, **options: Any) -> Agent:
    """Create, start, and register the process's agent (replacing any previous one)."""
    global _current
    uninstall()
    agent = Agent(publish, **options)
    _current = agent
    try:
        agent.start()
    except Exception:
        diagnostics.swallowed("devtools.install")
    return agent


def uninstall() -> None:
    """Stop and forget the process's agent (and restore ``breakpoint()``)."""
    global _current
    import sys

    agent, _current = _current, None
    if agent is not None:
        agent.stop()
    if getattr(sys.breakpointhook, "__pn_dev_hook__", False):
        sys.breakpointhook = sys.__breakpointhook__


def run_threadsafe(coro_factory: Callable[[], Awaitable[Any]], timeout: float = 10.0) -> Any:
    """Run a coroutine on the application loop from another thread and wait for it."""
    from ..runtime import get_loop

    loop = get_loop()
    done = threading.Event()
    box: Dict[str, Any] = {}

    async def runner() -> None:
        try:
            box["result"] = await coro_factory()
        except BaseException as exc:
            box["error"] = exc
        finally:
            done.set()

    loop.call_soon_threadsafe(lambda: loop.create_task(runner()))
    if not done.wait(timeout):
        raise TimeoutError("the application loop didn't answer in time")
    if "error" in box:
        raise box["error"]
    return box.get("result")
