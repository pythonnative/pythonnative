"""The dev server: HTTP for static assets, WebSocket for live peers.

One [`DevServer`][pythonnative.devserver.server.DevServer] runs on its
own thread with a private ``asyncio`` loop, so it works both inside
``pn start`` and in tests independently of the Python application
loop. It exposes:

- ``GET /``: the browser preview page. With a valid ``?token=``, the
  response instead sets the ``pn_token`` cookie and redirects to ``/``,
  so the token doesn't stay in the address bar.
- ``GET /static/<name>``: preview assets (JS, CSS).
- ``GET /manifest``: ``{"version", "entry", "files": {path: sha256}}``.
- ``GET /file/<path>``: raw bytes of one synced source file.
- ``GET /assets/<path>``: a file under ``app/assets/``; ``/assets/pn_assets.json``
  is the asset manifest and ``/assets/fonts.css`` declares the bundled
  fonts for the browser preview.
- ``GET /status``: server, project, and connected-peer information.
- ``GET /devtools``: the DevTools page (``/devtools/<name>`` for its
  assets), authenticated like ``/``.
- ``GET /connect``: connect links, server URLs, and their QR codes.
- ``WS /ws?role=client``: the dev-client protocol (see below).
- ``WS /ws?role=preview``: the browser preview's bridge channel; the
  server only relays text frames between the page and the
  [`PreviewChannel`][pythonnative.devserver.server.PreviewChannel]
  handler installed by the preview.

Every route except the page and ``/static/`` requires the per-user dev
token (see ``pythonnative.devserver.auth``) as a ``token`` query
parameter, an ``X-PN-Token`` header, or the ``pn_token`` cookie.
Requests without it get ``401``; requests with a wrong one get ``403``.
A WebSocket upgrade that carries an ``Origin`` header (every browser
sends one) must also come from the server's own origin: the ``Origin``
host and port must equal the ``Host`` header. Native dev clients send no
``Origin``.

Dev session protocol, version 2 (JSON objects, one per text frame; see
RFC 0006 and ``pythonnative.devclient``):

- client -> server ``hello``: ``{"type": "hello", "session": 2, "client":
  "go" | "app", "platform", "device", "app", "runtime": {...}, "files":
  {path: sha256}, "packages": {name: version}}``.
- server -> client ``incompatible`` (``reason``, ``fix``) when the client
  can't run the project (see ``pythonnative.devserver.compat``), or
  ``sync``: ``{"type": "sync", "version", "entry", "project", "files":
  [{"path", "sha256", "content", "encoding"}], "removed": [...]}``
  followed by ``packages`` for missing pure-Python distributions. The
  ``sync`` shape is sent as ``"update"`` whenever the watcher sees a
  change.
- server -> client ``rpc`` (``id``, ``method``, ``params``), ``tunnel``,
  ``menu``, and ``reload``; client -> server ``rpc_result``, ``event``
  (``topic``, ``data``), ``tunnel``, and ``packages_ready``.
- client -> server ``log`` (``level``, ``text``), ``error`` (``phase``,
  ``text``), ``reloaded`` (``version``, ``mode``, ``modules``): streamed
  to the terminal and DevTools.

``WS /ws?role=devtools`` carries DevTools pages (see
``pythonnative.devserver.hub``), and a separate listener on
``127.0.0.1:5678`` accepts Debug Adapter Protocol connections.
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Protocol, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urlsplit

from . import auth, ws
from .hub import ClientTarget, Hub, LocalTarget
from .watcher import FileWatcher, SourceChange, SourceSnapshot, snapshot_sources

__all__ = [
    "DEFAULT_DEBUG_PORT",
    "DEFAULT_PORT",
    "GO_APP_ID",
    "DevServer",
    "PreviewChannel",
    "PreviewPeer",
    "ServerInfo",
    "lan_addresses",
]

DEFAULT_PORT = 8765
"""Default port for ``pn start`` / ``pn preview``."""

DEFAULT_DEBUG_PORT = 5678
"""Default port of the debugger proxy (``debugpy``'s conventional port)."""

GO_APP_ID = "com.pythonnative.go"
"""PythonNative Go's application id; its connect scheme is ``pn-com.pythonnative.go``."""

_MAX_HEAD = 64 * 1024
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

Logger = Callable[[str], None]


def lan_addresses() -> List[str]:
    """Best-effort list of this machine's non-loopback IPv4 addresses.

    Used to print a URL a physical device on the same Wi-Fi can reach.
    """
    found: List[str] = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # No packets are sent; connecting a UDP socket just selects
            # the interface that routes to the internet.
            probe.connect(("10.255.255.255", 1))
            found.append(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = str(info[4][0])
            if not addr.startswith("127.") and addr not in found:
                found.append(addr)
    except OSError:
        pass
    return found


@dataclass
class ServerInfo:
    """What the server is serving and where."""

    host: str
    port: int
    project_root: str
    entry_module: str
    project_name: str = ""
    token: str = field(default="", repr=False)

    def url(self, host: Optional[str] = None) -> str:
        """The HTTP base URL, substituting ``host`` for the bind address."""
        return f"http://{host or self.display_host}:{self.port}"

    def preview_url(self, host: Optional[str] = None) -> str:
        """The browser preview URL, carrying the dev token once."""
        return auth.with_token(self.url(host) + "/", self.token)

    def ws_url(self, host: Optional[str] = None) -> str:
        """The dev-client WebSocket URL, including the dev token."""
        return auth.with_token(f"ws://{host or self.display_host}:{self.port}/ws?role=client", self.token)

    def devtools_url(self, host: Optional[str] = None) -> str:
        """The DevTools page URL, carrying the dev token once."""
        return auth.with_token(self.url(host) + "/devtools", self.token)

    def connect_url(self, host: Optional[str] = None) -> str:
        """The server URL a connect link carries (``http://host:port/?token=...``)."""
        return auth.with_token(self.url(host) + "/", self.token)

    @property
    def display_host(self) -> str:
        """A host suitable for a URL (``0.0.0.0`` becomes ``localhost``)."""
        return "localhost" if self.host in ("", "0.0.0.0", "::") else self.host


# ======================================================================
# Preview channel
# ======================================================================


class PreviewPeer:
    """A connected browser preview page; ``send`` is safe from any thread."""

    def __init__(self, server: "DevServer", writer: asyncio.StreamWriter) -> None:
        self._server = server
        self._writer = writer
        self.closed = threading.Event()

    def send(self, text: str) -> None:
        """Queue one text frame to the page (dropped once the peer is closed)."""
        if self.closed.is_set():
            return
        self._server._call_soon(self._send_now, text)

    def _send_now(self, text: str) -> None:
        if self.closed.is_set():
            return
        try:
            self._writer.write(ws.encode_frame(ws.TEXT, text.encode("utf-8")))
        except Exception:
            self.closed.set()

    def close(self) -> None:
        """Ask the server to close this page's socket."""
        self._server._call_soon(self._close_now)

    def _close_now(self) -> None:
        if self.closed.is_set():
            return
        self.closed.set()
        try:
            self._writer.write(ws.encode_close())
            self._writer.close()
        except Exception:
            pass


class PreviewChannel(Protocol):
    """What the preview installs to receive the page's bridge traffic.

    Every method is called on the server thread; implementations hop
    to their own thread as needed.
    """

    def on_preview_connected(self, peer: PreviewPeer, info: Dict[str, Any]) -> None:
        """A page connected (``info`` carries its query parameters)."""

    def on_preview_message(self, peer: PreviewPeer, text: str) -> None:
        """A text frame arrived from the page."""

    def on_preview_disconnected(self, peer: PreviewPeer) -> None:
        """The page went away."""


# ======================================================================
# Dev clients
# ======================================================================


@dataclass
class DevClient:
    """One connected on-device dev client."""

    id: int
    writer: asyncio.StreamWriter
    platform: str = "unknown"
    device: str = ""
    app: str = ""
    kind: str = "app"
    connected_at: float = field(default_factory=time.time)
    files: Dict[str, str] = field(default_factory=dict)
    target: Optional[ClientTarget] = None
    synced: bool = False

    def send(self, message: Dict[str, Any]) -> None:
        """Queue one JSON message (call on the server loop)."""
        try:
            self.writer.write(ws.encode_frame(ws.TEXT, json.dumps(message, default=str).encode("utf-8")))
        except Exception:
            pass

    def label(self) -> str:
        """A short human label for log lines."""
        parts = [self.platform]
        if self.device:
            parts.append(self.device)
        if self.kind == "go":
            parts.append("(Go)")
        return " ".join(parts)


class DevToolsPeer:
    """A connected DevTools page; ``send`` is safe from the server loop."""

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self._writer = writer

    def send(self, message: Dict[str, Any]) -> None:
        """Queue one JSON message to the page."""
        self._writer.write(ws.encode_frame(ws.TEXT, json.dumps(message, default=str).encode("utf-8")))


# ======================================================================
# The server
# ======================================================================


class DevServer:
    """Serve sources, assets, and the live protocol for one project.

    Args:
        project_root: Directory containing ``app/`` and ``pythonnative.toml``.
        entry_module: The app's entry module (``"app.main"``).
        host: Bind address. ``0.0.0.0`` so devices on the LAN can reach
            it; pass ``127.0.0.1`` to stay local.
        port: TCP port; ``0`` picks a free one.
        project_name: Shown in the preview page and ``/status``.
        token: The dev token clients must present; defaults to this
            user's token from
            [`load_token`][pythonnative.devserver.auth.load_token].
        static_dir: Where the preview page's assets live.
        log: Where to print client logs and connection events.
        watch: Whether to run the file watcher.
        config: The project's ``AppConfig``, for compatibility checks,
            package sync, and the app's connect scheme.
        debug_port: Port of the debugger proxy on ``127.0.0.1``
            (``0`` picks a free one, ``None`` disables it).
        open_devtools: Called when an app's dev menu asks to open DevTools.
    """

    def __init__(
        self,
        project_root: str,
        entry_module: str = "app.main",
        *,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        project_name: str = "",
        token: Optional[str] = None,
        static_dir: Optional[str] = None,
        log: Optional[Logger] = None,
        watch: bool = True,
        config: Any = None,
        debug_port: Optional[int] = None,
        open_devtools: Optional[Callable[[], None]] = None,
    ) -> None:
        self.project_root = os.path.abspath(project_root)
        self.token = token or auth.load_token()
        self.entry_module = entry_module
        self.project_name = project_name
        self.static_dir = static_dir or _STATIC_DIR
        self.log: Logger = log or (lambda line: print(line, file=sys.stderr, flush=True))
        self._host = host
        self._port = port
        self._watch = watch
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[asyncio.base_events.Server] = None
        self._started = threading.Event()
        self._start_error: Optional[BaseException] = None
        self._clients: Dict[int, DevClient] = {}
        self._client_ids = 0
        self._preview: Optional[PreviewChannel] = None
        self._preview_peer: Optional[PreviewPeer] = None
        self._watcher: Optional[FileWatcher] = None
        self._snapshot: SourceSnapshot = snapshot_sources(self.project_root)
        self._snapshot_lock = threading.Lock()
        self._change_listeners: List[Callable[[SourceChange, SourceSnapshot], None]] = []
        self.config = config
        self.debug_port = debug_port
        self._debug_server: Optional[asyncio.base_events.Server] = None
        self._runtime: Any = None
        self.hub = Hub(
            self.log,
            on_open_devtools=open_devtools,
            on_open_editor=lambda file, line: self._open_in_editor({"file": file, "line": line}),
        )
        self.info = ServerInfo(
            host=host,
            port=port,
            project_root=self.project_root,
            entry_module=entry_module,
            project_name=project_name,
            token=self.token,
        )

    # -- lifecycle -------------------------------------------------------

    def start(self) -> ServerInfo:
        """Bind the socket on a background thread and return the address.

        Raises:
            OSError: When the port is taken (the CLI prints a hint).
        """
        if self._thread is not None:
            return self.info
        self._thread = threading.Thread(target=self._run, name="pn-dev-server", daemon=True)
        self._thread.start()
        self._started.wait(timeout=10.0)
        if self._start_error is not None:
            error, self._start_error = self._start_error, None
            self._thread = None
            raise error
        if self._watch:
            self._watcher = FileWatcher(self.project_root, self._on_files_changed)
            with self._snapshot_lock:
                self._snapshot = self._watcher.snapshot
            self._watcher.start()
        return self.info

    def stop(self) -> None:
        """Close every connection and stop the thread."""
        watcher, self._watcher = self._watcher, None
        if watcher is not None:
            watcher.stop()
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._shutdown)
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=5.0)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            server = loop.run_until_complete(asyncio.start_server(self._handle_connection, self._host, self._port))
        except BaseException as exc:
            self._start_error = exc
            self._started.set()
            loop.close()
            return
        self._server = server
        sockets: Sequence[Any] = server.sockets or []
        if sockets:
            self.info.port = int(sockets[0].getsockname()[1])
        if self.debug_port is not None:
            try:
                debug = loop.run_until_complete(
                    asyncio.start_server(self.hub.debug_connection, "127.0.0.1", self.debug_port)
                )
            except OSError as exc:
                self.log(f"[pn] debugger proxy disabled: can't listen on 127.0.0.1:{self.debug_port} ({exc})")
                self.debug_port = None
            else:
                self._debug_server = debug
                debug_sockets: Sequence[Any] = debug.sockets or []
                if debug_sockets:
                    self.debug_port = int(debug_sockets[0].getsockname()[1])
                self.hub.debug_port = self.debug_port or 0
        self._started.set()
        try:
            loop.run_forever()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    def _shutdown(self) -> None:
        loop = self._loop
        if self._server is not None:
            self._server.close()
        if self._debug_server is not None:
            self._debug_server.close()
        for client in list(self._clients.values()):
            try:
                client.writer.write(ws.encode_close())
                client.writer.close()
            except Exception:
                pass
        self._clients.clear()
        if self._preview_peer is not None:
            self._preview_peer._close_now()
        if loop is not None:
            loop.call_soon(loop.stop)

    def _call_soon(self, fn: Callable[..., Any], *args: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(fn, *args)
        except RuntimeError:
            pass

    # -- state -----------------------------------------------------------

    @property
    def snapshot(self) -> SourceSnapshot:
        """The current source snapshot."""
        with self._snapshot_lock:
            return self._snapshot

    @property
    def clients(self) -> List[DevClient]:
        """Connected dev clients (a copy)."""
        return list(self._clients.values())

    def set_preview_channel(self, channel: Optional[PreviewChannel]) -> None:
        """Install the handler for the browser preview's bridge traffic."""
        self._preview = channel

    def add_change_listener(self, listener: Callable[[SourceChange, SourceSnapshot], None]) -> Callable[[], None]:
        """Be told (on the watcher thread) when sources change; returns an unsubscribe."""
        self._change_listeners.append(listener)

        def _remove() -> None:
            try:
                self._change_listeners.remove(listener)
            except ValueError:
                pass

        return _remove

    @property
    def project_runtime(self) -> Any:
        """What the project needs from a dev client (computed once, on first use)."""
        if self._runtime is None:
            from .compat import project_runtime

            self._runtime = project_runtime(self.config)
        return self._runtime

    def app_scheme(self) -> Optional[str]:
        """The connect scheme of the project's own debug build, when the config names an app id."""
        from ..devclient import dev_scheme

        app_id = getattr(self.config, "app_id", None)
        return dev_scheme(str(app_id)) if app_id else None

    def connect_links(self, host: Optional[str] = None) -> Dict[str, Any]:
        """Connect links for PythonNative Go and the project's own debug build.

        The preferred link is Go's when the project can run in it.
        """
        from ..devclient import connect_link, dev_scheme

        server_url = self.info.connect_url(host)
        links: Dict[str, Any] = {"server": server_url, "go": connect_link(dev_scheme(GO_APP_ID), server_url)}
        scheme = self.app_scheme()
        if scheme:
            links["app"] = connect_link(scheme, server_url)
        try:
            go_ok = bool(self.project_runtime.go_compatible)
        except Exception:
            go_ok = True
        links["go_compatible"] = go_ok
        links["preferred"] = links["go"] if go_ok or "app" not in links else links["app"]
        return links

    def preview_target(self, agent: Any) -> None:
        """Register the browser preview's in-process agent as a DevTools target (any thread)."""

        def register() -> None:
            assert self._loop is not None
            self.hub.add_target(LocalTarget(agent, self._loop))

        self._call_soon(register)

    def publish_local(self, target_id: str, topic: str, data: Any) -> None:
        """Publish an event for an in-process target (any thread)."""
        self._call_soon(self.hub.on_event, target_id, topic, data)

    def broadcast_command(self, name: str) -> None:
        """Send ``reload`` or ``menu`` to every connected dev client (any thread)."""

        def send() -> None:
            for client in list(self._clients.values()):
                if client.synced:
                    client.send({"type": name})
            preview = self.hub.targets.get("preview")
            if name == "reload" and isinstance(preview, LocalTarget):
                preview.agent.dispatch("reload", {}, lambda _result, _error: None)

        self._call_soon(send)

    def manifest(self) -> Dict[str, Any]:
        """The ``/manifest`` document."""
        snap = self.snapshot
        return {"version": snap.version, "entry": self.entry_module, "files": dict(snap.files)}

    def status(self) -> Dict[str, Any]:
        """The ``/status`` document."""
        snap = self.snapshot
        return {
            "name": self.project_name,
            "entry": self.entry_module,
            "project_root": self.project_root,
            "version": snap.version,
            "file_count": len(snap.files),
            "clients": [
                {"id": c.id, "platform": c.platform, "device": c.device, "app": c.app, "connected_at": c.connected_at}
                for c in self._clients.values()
            ],
            "preview_connected": self._preview_peer is not None and not self._preview_peer.closed.is_set(),
            "lan": lan_addresses(),
            "port": self.info.port,
            "debug_port": self.debug_port,
            "targets": self.hub.describe_targets(),
        }

    # -- file changes ----------------------------------------------------

    def _on_files_changed(self, change: SourceChange, snapshot: SourceSnapshot) -> None:
        with self._snapshot_lock:
            self._snapshot = snapshot
        summary = ", ".join(change.changed + [f"-{p}" for p in change.removed])
        self.log(f"[pn] changed: {summary}")
        for listener in list(self._change_listeners):
            try:
                listener(change, snapshot)
            except Exception as exc:
                self.log(f"[pn] change listener failed: {exc!r}")
        if self._clients:
            message = self._sync_message("update", snapshot, change.changed, change.removed)
            self._call_soon(self._broadcast, message)

    def _sync_message(self, kind: str, snapshot: SourceSnapshot, paths: Sequence[str], removed: Sequence[str]) -> str:
        files: List[Dict[str, Any]] = []
        for path in paths:
            data = snapshot.read(path)
            if data is None:
                continue
            files.append(_encode_file(path, snapshot.files.get(path, ""), data))
        return json.dumps(
            {
                "type": kind,
                "version": snapshot.version,
                "entry": self.entry_module,
                "project": self.project_name,
                "files": files,
                "removed": list(removed),
            }
        )

    def _broadcast(self, message: str) -> None:
        frame = ws.encode_frame(ws.TEXT, message.encode("utf-8"))
        for client in list(self._clients.values()):
            if not client.synced:
                continue
            try:
                client.writer.write(frame)
            except Exception:
                self._drop_client(client)

    def _drop_client(self, client: DevClient) -> None:
        if self._clients.pop(client.id, None) is not None:
            if client.target is not None:
                self.hub.remove_target(client.target.id)
            if client.synced:
                self.log(f"[pn] {client.label()} disconnected")
        try:
            client.writer.close()
        except Exception:
            pass

    # -- connections -----------------------------------------------------

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            writer.close()
            return
        if len(head) > _MAX_HEAD:
            writer.close()
            return
        start_line, headers = ws.parse_http_headers(head)
        parts = start_line.split()
        if len(parts) < 2:
            writer.close()
            return
        method, target = parts[0], parts[1]
        url = urlsplit(target)
        path = unquote(url.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        if "websocket" in headers.get("upgrade", "").lower():
            await self._serve_websocket(reader, writer, headers, path, query)
            return
        try:
            await self._serve_http(writer, method, path, query, headers)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    def _check_token(self, headers: Dict[str, str], query: Dict[str, str]) -> int:
        """``200`` for a valid token, ``401`` when none was presented, ``403`` for a wrong one."""
        presented = auth.request_token(headers, query)
        if presented is None:
            return 401
        return 200 if auth.token_matches(presented, self.token) else 403

    async def _serve_http(
        self, writer: asyncio.StreamWriter, method: str, path: str, query: Dict[str, str], headers: Dict[str, str]
    ) -> None:
        if method not in ("GET", "HEAD"):
            _respond(writer, 405, b"method not allowed", "text/plain")
            return
        if path in ("/", "/index.html", "/devtools", "/devtools/"):
            page = "/devtools" if path.startswith("/devtools") else "/"
            if auth.QUERY_PARAM in query:
                # Trade the URL's token for a cookie, then drop it from the address bar.
                if not auth.token_matches(query[auth.QUERY_PARAM], self.token):
                    _respond_refusal(writer, 403)
                    return
                cookie = f"{auth.COOKIE_NAME}={self.token}; HttpOnly; SameSite=Strict; Path=/"
                _respond(writer, 302, b"", "text/plain", headers={"Location": page, "Set-Cookie": cookie})
                return
            name = "devtools/index.html" if page == "/devtools" else "index.html"
            _respond_file(writer, os.path.join(self.static_dir, name))
            return
        if path == "/static/schema.js":
            from ..sdk.schema import manifest

            _respond(
                writer, 200, ("export default " + json.dumps(manifest(), default=str) + ";").encode(), "text/javascript"
            )
            return
        if path.startswith("/devtools/"):
            path = "/static/devtools/" + path[len("/devtools/") :]
        if path.startswith("/static/"):
            name = path[len("/static/") :]
            root = os.path.realpath(self.static_dir)
            candidate = os.path.realpath(os.path.join(root, name))
            if (
                not name
                or any(part.startswith(".") for part in name.split("/"))
                or os.path.commonpath([root, candidate]) != root
            ):
                _respond(writer, 404, b"not found", "text/plain")
                return
            _respond_file(writer, candidate)
            return
        # Everything past the page and its static files needs the token,
        # including routes that don't exist (so they reveal nothing).
        status = self._check_token(headers, query)
        if status != 200:
            _respond_refusal(writer, status)
            return
        if path == "/manifest":
            _respond_json(writer, self.manifest())
            return
        if path == "/status":
            _respond_json(writer, self.status())
            return
        if path == "/connect":
            _respond_json(writer, self._connect_document(headers))
            return
        if path.startswith("/file/"):
            rel = path[len("/file/") :]
            snap = self.snapshot
            if rel not in snap.files:
                _respond(writer, 404, b"not found", "text/plain")
                return
            data = snap.read(rel)
            if data is None:
                _respond(writer, 404, b"not found", "text/plain")
                return
            _respond(writer, 200, data, mimetypes.guess_type(rel)[0] or "application/octet-stream")
            return
        if path.startswith("/assets/"):
            self._serve_asset(writer, path[len("/assets/") :])
            return
        _respond(writer, 404, b"not found", "text/plain")

    def _connect_document(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """``/connect``: links for the LAN address (phones) and localhost, with QR codes."""
        from .qr import encode, to_svg

        lan = next(iter(lan_addresses()), None)
        local = self.connect_links("localhost")
        remote = self.connect_links(lan) if lan else local
        preferred = str(remote["preferred"])
        return {
            "project": self.project_name,
            "lan": lan,
            "links": remote,
            "local": local,
            "qr_svg": to_svg(encode(preferred), border=4),
            "devtools": self.info.devtools_url("localhost"),
            "debug_port": self.debug_port,
        }

    def _serve_asset(self, writer: asyncio.StreamWriter, rel: str) -> None:
        """Serve ``app/assets/<rel>``, the manifest, or the generated font CSS.

        The browser preview resolves ``asset://`` URIs against this
        route: ``/assets/pn_assets.json`` is the
        [`AssetManifest`][pythonnative.assets.AssetManifest] of the
        current tree, ``/assets/fonts.css`` declares one ``@font-face``
        per bundled font so ``font_family`` names work in the page, and
        anything else is the file itself.
        """
        from .. import assets as assets_module

        root = os.path.join(self.snapshot.root, "app", assets_module.ASSETS_DIR)
        if rel == assets_module.MANIFEST_NAME:
            _respond_json(writer, assets_module.scan(root).to_dict())
            return
        if rel == "fonts.css":
            css = "\n".join(
                "@font-face {\n"
                f'  font-family: "{face.family}";\n'
                f"  font-weight: {face.weight};\n"
                f"  font-style: {'italic' if face.italic else 'normal'};\n"
                f'  src: url("/assets/{face.path}");\n'
                "}"
                for face in assets_module.scan(root).fonts
            )
            _respond(writer, 200, css.encode("utf-8"), "text/css; charset=utf-8")
            return
        try:
            normalized = assets_module.normalize_path(unquote(rel))
        except ValueError:
            _respond(writer, 404, b"not found", "text/plain")
            return
        snap = self.snapshot
        key = f"app/{assets_module.ASSETS_DIR}/{normalized}"
        data = snap.read(key) if key in snap.files else None
        if data is None:
            _respond(writer, 404, b"not found", "text/plain")
            return
        _respond(writer, 200, data, mimetypes.guess_type(normalized)[0] or "application/octet-stream")

    async def _serve_websocket(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        headers: Dict[str, str],
        path: str,
        query: Dict[str, str],
    ) -> None:
        # Refuse with a plain HTTP response before upgrading, so a rejected
        # peer never gets a socket.
        refusal: Optional[int] = None
        if path != "/ws":
            refusal = 404
        elif not _same_origin(headers):
            refusal = 403
        else:
            status = self._check_token(headers, query)
            refusal = None if status == 200 else status
        if refusal is not None:
            _respond_refusal(writer, refusal)
            try:
                await writer.drain()
            except ConnectionError:
                pass
            writer.close()
            return
        try:
            writer.write(ws.server_handshake(headers))
            await writer.drain()
        except (ws.HandshakeError, ConnectionError):
            writer.close()
            return
        role = query.get("role", "client")
        if role == "preview":
            await self._preview_session(reader, writer, query)
        elif role == "devtools":
            await self._devtools_session(reader, writer)
        else:
            await self._client_session(reader, writer)

    async def _read_messages(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> AsyncIterator[str]:
        """Yield text messages until the peer closes; answers pings."""
        decoder = ws.FrameDecoder()
        while True:
            try:
                chunk = await reader.read(65536)
            except (ConnectionError, asyncio.CancelledError, OSError):
                return
            if not chunk:
                return
            try:
                messages = list(decoder.feed(chunk))
            except ws.WebSocketError:
                try:
                    writer.write(ws.encode_close(1002, "protocol error"))
                except Exception:
                    pass
                return
            for opcode, payload in messages:
                if opcode == ws.TEXT:
                    try:
                        yield payload.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                elif opcode == ws.PING:
                    writer.write(ws.encode_frame(ws.PONG, payload))
                elif opcode == ws.CLOSE:
                    try:
                        writer.write(ws.encode_close())
                    except Exception:
                        pass
                    return

    async def _client_session(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._client_ids += 1
        client = DevClient(id=self._client_ids, writer=writer)
        self._clients[client.id] = client
        try:
            async for text in self._read_messages(reader, writer):
                try:
                    message = json.loads(text)
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self._on_client_message(client, message)
        finally:
            self._drop_client(client)

    def _on_client_message(self, client: DevClient, message: Dict[str, Any]) -> None:
        kind = message.get("type")
        target = client.target
        if kind == "hello":
            self._on_hello(client, message)
            return
        if kind == "log":
            level = str(message.get("level") or "info")
            text = str(message.get("text") or "").rstrip("\n")
            prefix = f"[{client.label()}]"
            if level in ("error", "warn", "warning"):
                prefix = f"[{client.label()} {level}]"
            for line in text.split("\n"):
                self.log(f"{prefix} {line}")
            if target is not None:
                self.hub.log_line(target.id, level, text)
            return
        if kind == "error":
            phase = str(message.get("phase") or "runtime")
            text = str(message.get("text") or "").rstrip("\n")
            self.log(f"[{client.label()}] error during {phase}:")
            for line in text.split("\n"):
                self.log(f"    {line}")
            if target is not None:
                self.hub.log_line(target.id, "error", f"error during {phase}:\n{text}")
            return
        if kind == "reloaded":
            mode = str(message.get("mode") or "reload")
            modules = message.get("modules") or []
            what = ", ".join(str(m) for m in modules) if isinstance(modules, list) and modules else "app"
            self.log(f"[{client.label()}] {mode}: {what}")
            if target is not None:
                self.hub.on_event(target.id, "reload", {"mode": mode, "modules": modules})
            return
        if target is None:
            return
        if kind == "event":
            self.hub.on_event(target.id, str(message.get("topic") or ""), message.get("data"))
        elif kind == "rpc_result":
            target.settle(message)
        elif kind == "tunnel":
            target.tunnel(message)
        elif kind == "packages_ready":
            target.packages_ready(message)

    def _on_hello(self, client: DevClient, message: Dict[str, Any]) -> None:
        from .compat import check

        client.platform = str(message.get("platform") or "unknown")
        client.device = str(message.get("device") or "")
        client.app = str(message.get("app") or "")
        client.kind = str(message.get("client") or "app")
        files = message.get("files")
        client.files = {str(k): str(v) for k, v in files.items()} if isinstance(files, dict) else {}
        try:
            problem = check(message, self.project_runtime)
        except Exception as exc:
            problem = None
            self.log(f"[pn] couldn't check {client.label()}'s compatibility: {exc!r}")
        runtime = message.get("runtime") if isinstance(message.get("runtime"), dict) else {}
        assert isinstance(runtime, dict)
        bundled = {str(k): str(v) for k, v in (runtime.get("distributions") or {}).items()}
        synced = {str(k): str(v) for k, v in (message.get("packages") or {}).items()}
        plan, missing_native = self._package_plan(bundled, synced)
        if problem is None and missing_native and client.kind == "app":
            from .compat import Incompatibility

            platform = client.platform if client.platform in ("ios", "android") else "<platform>"
            problem = Incompatibility(
                f"The project now needs {', '.join(missing_native)}, which contain compiled code this "
                "build doesn't include.",
                f"Rebuild it with `pn run {platform} --rebuild`.",
            )
        if problem is not None:
            self.log(f"[pn] {client.label()} can't run this project: {problem.reason} {problem.fix}")
            client.send(problem.to_message())
            return
        target = ClientTarget(client.id, client.send)
        target.kind = client.kind
        target.platform = client.platform
        target.device = client.device
        target.distributions = bundled
        target.packages = synced
        target.host_paths = self._host_paths()
        target.sync_packages = lambda names, request: self._send_packages(client, names, request)
        client.target = target
        client.synced = True
        self.log(f"[pn] {client.label()} connected")
        snap = self.snapshot
        changed = sorted(p for p, digest in snap.files.items() if client.files.get(p) != digest)
        removed = sorted(p for p in client.files if p not in snap.files)
        try:
            client.writer.write(
                ws.encode_frame(ws.TEXT, self._sync_message("sync", snap, changed, removed).encode("utf-8"))
            )
        except Exception:
            self._drop_client(client)
            return
        if plan:
            self._send_packages(client, [dist.name for dist in plan], None, plan=plan)
        self.hub.add_target(target)

    def _package_plan(self, bundled: Dict[str, str], synced: Dict[str, str]) -> Tuple[List[Any], List[str]]:
        """``(pure distributions to sync, required native distributions the client lacks)``."""
        from . import packages as packages_mod

        requirements = list(getattr(self.config, "requirements", ()) or ())
        if not requirements:
            return [], []
        distributions, _missing = packages_mod.resolve(requirements, skip=bundled.keys())
        plan = [dist for dist in distributions if dist.pure and synced.get(dist.name) != dist.version]
        native = sorted(dist.name for dist in distributions if not dist.pure)
        return plan, native

    def _send_packages(self, client: DevClient, names: List[str], request: Optional[int], *, plan: Any = None) -> int:
        """Send ``names`` (or a precomputed ``plan``) to ``client``; returns how many were sent."""
        from . import packages as packages_mod

        if plan is None:
            target = client.target
            skip = set(target.distributions) if target is not None else set()
            distributions, _missing = packages_mod.resolve(names, skip=skip)
            plan = []
            for dist in distributions:
                if packages_mod.normalize(dist.name) == "debugpy" or not dist.pure:
                    found = packages_mod.find_distribution(dist.name)
                    if found is None:
                        continue
                    dist = packages_mod.distribution_files(found, sources_only=True)
                plan.append(dist)
            if not plan:
                missing = ", ".join(names)
                self.log(f"[pn] can't sync {missing}: install it in this environment (`pip install {missing}`)")
                return 0
        for index, dist in enumerate(plan):
            files = []
            for rel, path in dist.files:
                try:
                    data = path.read_bytes()
                except OSError:
                    continue
                files.append(_encode_file(rel, "", data))
            last = index == len(plan) - 1
            client.send(
                {
                    "type": "packages",
                    "packages": [{"name": dist.name, "version": dist.version, "files": files}],
                    "request": request if last else None,
                }
            )
            if client.target is not None:
                client.target.packages[dist.name] = dist.version
            self.log(f"[pn] syncing {dist.name} {dist.version} to {client.label()} ({len(files)} files)")
        return len(plan)

    def _host_paths(self) -> Dict[str, Any]:
        """Paths on this machine that device paths map to, for the debugger."""
        import sysconfig

        sites = {sysconfig.get_paths().get("purelib"), sysconfig.get_paths().get("platlib")}
        return {
            "project": self.project_root,
            "pythonnative": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "site_packages": sorted(path for path in sites if path),
        }

    async def _devtools_session(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        page = DevToolsPeer(writer)
        self.hub.add_page(page)
        tasks: List[asyncio.Task[Any]] = []
        try:
            async for text in self._read_messages(reader, writer):
                try:
                    message = json.loads(text)
                except ValueError:
                    continue
                if not isinstance(message, dict):
                    continue
                kind = message.get("type")
                if kind == "rpc":
                    tasks.append(asyncio.get_running_loop().create_task(self.hub.page_request(page, message)))
                    tasks = [task for task in tasks if not task.done()]
                elif kind == "open":
                    page.send(self._open_in_editor(message))
                elif kind == "debug_target":
                    target_id = message.get("target")
                    self.hub.debug_target = str(target_id) if target_id else None
                    self.hub.broadcast_targets()
                elif kind == "command":
                    self._page_command(str(message.get("name") or ""), message.get("target"))
                elif kind == "clear":
                    target_id = message.get("target")
                    self.hub.clear(str(target_id) if target_id else None, str(message.get("topic") or ""))
                elif kind == "connect":
                    page.send({"type": "connect", **self._connect_document({})})
        finally:
            self.hub.remove_page(page)
            for task in tasks:
                task.cancel()
            try:
                writer.close()
            except Exception:
                pass

    def _page_command(self, name: str, target_id: Any) -> None:
        if name not in ("reload", "menu"):
            return
        for client in list(self._clients.values()):
            if client.target is not None and target_id in (None, client.target.id):
                client.send({"type": name})
        preview = self.hub.targets.get("preview")
        if isinstance(preview, LocalTarget) and target_id in (None, "preview"):
            preview.agent.dispatch(name, {}, lambda _result, _error: None)

    def _open_in_editor(self, message: Dict[str, Any]) -> Dict[str, Any]:
        from .editor import open_in_editor

        file = str(message.get("file") or "")
        line = int(message.get("line") or 1)
        opened = open_in_editor(file, line, self.project_root, self._host_paths()["site_packages"])
        if opened is None:
            return {"type": "opened", "file": file, "error": f"{file} isn't in this project"}
        self.log(f"[pn] opened {opened}:{line}")
        return {"type": "opened", "file": file, "path": opened}

    async def _preview_session(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, query: Dict[str, str]
    ) -> None:
        channel = self._preview
        if channel is None:
            writer.write(ws.encode_close(1013, "no preview running"))
            writer.close()
            return
        previous = self._preview_peer
        if previous is not None and not previous.closed.is_set():
            # One page at a time: the newest tab takes over the app.
            try:
                previous._send_now(json.dumps(["dev", {"type": "superseded"}]))
            except Exception:
                pass
            previous._close_now()
            channel.on_preview_disconnected(previous)
        peer = PreviewPeer(self, writer)
        self._preview_peer = peer
        channel.on_preview_connected(peer, dict(query))
        try:
            async for text in self._read_messages(reader, writer):
                channel.on_preview_message(peer, text)
        finally:
            peer.closed.set()
            if self._preview_peer is peer:
                self._preview_peer = None
            channel.on_preview_disconnected(peer)
            try:
                writer.close()
            except Exception:
                pass


# ======================================================================
# HTTP helpers
# ======================================================================


def _encode_file(path: str, digest: str, data: bytes) -> Dict[str, Any]:
    try:
        return {"path": path, "sha256": digest, "content": data.decode("utf-8"), "encoding": "utf8"}
    except UnicodeDecodeError:
        return {"path": path, "sha256": digest, "content": base64.b64encode(data).decode("ascii"), "encoding": "base64"}


_STATUS_TEXT = {
    200: "OK",
    302: "Found",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
}

_REFUSALS: Dict[int, bytes] = {
    401: b"This dev server needs its token. Open the URL that `pn start` printed.\n",
    403: b"Forbidden: wrong dev token or a cross-origin request. Open the URL that `pn start` printed.\n",
    404: b"not found",
}


def _same_origin(headers: Dict[str, str]) -> bool:
    """Whether a WebSocket upgrade may proceed given its ``Origin``.

    Browsers always send ``Origin`` on a WebSocket upgrade, and any page
    can open a socket to any host, so a browser peer must come from this
    server's own origin: the ``Origin`` host and port must equal the
    ``Host`` header. Native dev clients send no ``Origin`` and pass.
    """
    origin = headers.get("origin")
    if origin is None:
        return True
    host = headers.get("host", "").strip().lower()
    try:
        netloc = urlsplit(origin.strip()).netloc.lower()
    except ValueError:
        return False
    return bool(host) and netloc == host


def _respond_refusal(writer: asyncio.StreamWriter, status: int) -> None:
    _respond(writer, status, _REFUSALS.get(status, b""), "text/plain; charset=utf-8")


def _respond(
    writer: asyncio.StreamWriter,
    status: int,
    body: bytes,
    content_type: str,
    *,
    headers: Optional[Dict[str, str]] = None,
) -> None:
    extra = "".join(f"{name}: {value}\r\n" for name, value in (headers or {}).items())
    head = (
        f"HTTP/1.1 {status} {_STATUS_TEXT.get(status, 'OK')}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        f"{extra}"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    try:
        writer.write(head + body)
    except Exception:
        pass


def _respond_json(writer: asyncio.StreamWriter, document: Any) -> None:
    _respond(writer, 200, json.dumps(document).encode("utf-8"), "application/json; charset=utf-8")


def _respond_file(writer: asyncio.StreamWriter, path: str) -> None:
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        _respond(writer, 404, b"not found", "text/plain")
        return
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if path.endswith(".js"):
        content_type = "text/javascript"
    if content_type.startswith("text/") and "charset" not in content_type:
        content_type += "; charset=utf-8"
    _respond(writer, 200, data, content_type)
