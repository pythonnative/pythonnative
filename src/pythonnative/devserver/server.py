"""The dev server: HTTP for static assets, WebSocket for live peers.

One [`DevServer`][pythonnative.devserver.server.DevServer] runs on its
own thread with a private ``asyncio`` loop, so it works both inside
``pn start`` (whose main thread runs the browser preview's app) and in
tests. It exposes:

- ``GET /``: the browser preview page.
- ``GET /static/<name>``: preview assets (JS, CSS).
- ``GET /manifest``: ``{"version", "entry", "files": {path: sha256}}``.
- ``GET /file/<path>``: raw bytes of one synced source file.
- ``GET /status``: server, project, and connected-peer information.
- ``WS /ws?role=client``: the dev-client protocol (see below).
- ``WS /ws?role=preview``: the browser preview's bridge channel; the
  server only relays text frames between the page and the
  [`PreviewChannel`][pythonnative.devserver.server.PreviewChannel]
  handler installed by the preview.

Dev-client protocol (JSON objects, one per text frame):

- client -> server ``hello``: ``{"type": "hello", "platform", "device",
  "app", "files": {path: sha256}}`` describing what the client already
  holds in its overlay.
- server -> client ``sync``: ``{"type": "sync", "version", "entry",
  "files": [{"path", "sha256", "content", "encoding"}], "removed": [...]}``
  bringing the client up to date. The same shape is sent as
  ``"update"`` whenever the watcher sees a change.
- client -> server ``log`` (``level``, ``text``), ``error`` (``phase``,
  ``text``), ``reloaded`` (``version``, ``mode``, ``modules``): streamed
  to the terminal.
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
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Protocol, Sequence
from urllib.parse import parse_qs, unquote, urlsplit

from . import ws
from .watcher import FileWatcher, SourceChange, SourceSnapshot, snapshot_sources

__all__ = [
    "DEFAULT_PORT",
    "DevServer",
    "PreviewChannel",
    "PreviewPeer",
    "ServerInfo",
    "lan_addresses",
]

DEFAULT_PORT = 8765
"""Default port for ``pn start`` / ``pn preview``."""

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

    def url(self, host: Optional[str] = None) -> str:
        """The HTTP base URL, substituting ``host`` for the bind address."""
        return f"http://{host or self.display_host}:{self.port}"

    def ws_url(self, host: Optional[str] = None) -> str:
        """The dev-client WebSocket URL."""
        return f"ws://{host or self.display_host}:{self.port}/ws?role=client"

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
    connected_at: float = field(default_factory=time.time)
    files: Dict[str, str] = field(default_factory=dict)

    def label(self) -> str:
        """A short human label for log lines."""
        parts = [self.platform]
        if self.device:
            parts.append(self.device)
        return " ".join(parts)


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
        static_dir: Where the preview page's assets live.
        log: Where to print client logs and connection events.
        watch: Whether to run the file watcher.
    """

    def __init__(
        self,
        project_root: str,
        entry_module: str = "app.main",
        *,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        project_name: str = "",
        static_dir: Optional[str] = None,
        log: Optional[Logger] = None,
        watch: bool = True,
    ) -> None:
        self.project_root = os.path.abspath(project_root)
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
        self.info = ServerInfo(
            host=host,
            port=port,
            project_root=self.project_root,
            entry_module=entry_module,
            project_name=project_name,
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
                "files": files,
                "removed": list(removed),
            }
        )

    def _broadcast(self, message: str) -> None:
        frame = ws.encode_frame(ws.TEXT, message.encode("utf-8"))
        for client in list(self._clients.values()):
            try:
                client.writer.write(frame)
            except Exception:
                self._drop_client(client)

    def _drop_client(self, client: DevClient) -> None:
        if self._clients.pop(client.id, None) is not None:
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
            await self._serve_http(writer, method, path, query)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def _serve_http(self, writer: asyncio.StreamWriter, method: str, path: str, query: Dict[str, str]) -> None:
        if method not in ("GET", "HEAD"):
            _respond(writer, 405, b"method not allowed", "text/plain")
            return
        if path in ("/", "/index.html"):
            _respond_file(writer, os.path.join(self.static_dir, "index.html"))
            return
        if path.startswith("/static/"):
            name = path[len("/static/") :]
            if not name or "/" in name or name.startswith("."):
                _respond(writer, 404, b"not found", "text/plain")
                return
            _respond_file(writer, os.path.join(self.static_dir, name))
            return
        if path == "/manifest":
            _respond_json(writer, self.manifest())
            return
        if path == "/status":
            _respond_json(writer, self.status())
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
        _respond(writer, 404, b"not found", "text/plain")

    async def _serve_websocket(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        headers: Dict[str, str],
        path: str,
        query: Dict[str, str],
    ) -> None:
        try:
            writer.write(ws.server_handshake(headers))
            await writer.drain()
        except (ws.HandshakeError, ConnectionError):
            writer.close()
            return
        role = query.get("role", "client")
        if path != "/ws":
            writer.write(ws.encode_close(1008, "unknown path"))
            writer.close()
            return
        if role == "preview":
            await self._preview_session(reader, writer, query)
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
        if kind == "hello":
            client.platform = str(message.get("platform") or "unknown")
            client.device = str(message.get("device") or "")
            client.app = str(message.get("app") or "")
            files = message.get("files")
            client.files = {str(k): str(v) for k, v in files.items()} if isinstance(files, dict) else {}
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
        if kind == "log":
            level = str(message.get("level") or "info")
            text = str(message.get("text") or "").rstrip("\n")
            prefix = f"[{client.label()}]"
            if level in ("error", "warn", "warning"):
                prefix = f"[{client.label()} {level}]"
            for line in text.split("\n"):
                self.log(f"{prefix} {line}")
            return
        if kind == "error":
            phase = str(message.get("phase") or "runtime")
            text = str(message.get("text") or "").rstrip("\n")
            self.log(f"[{client.label()}] error during {phase}:")
            for line in text.split("\n"):
                self.log(f"    {line}")
            return
        if kind == "reloaded":
            mode = str(message.get("mode") or "reload")
            modules = message.get("modules") or []
            what = ", ".join(str(m) for m in modules) if isinstance(modules, list) and modules else "app"
            self.log(f"[{client.label()}] {mode}: {what}")
            return

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


_STATUS_TEXT = {200: "OK", 404: "Not Found", 405: "Method Not Allowed", 500: "Internal Server Error"}


def _respond(writer: asyncio.StreamWriter, status: int, body: bytes, content_type: str) -> None:
    head = (
        f"HTTP/1.1 {status} {_STATUS_TEXT.get(status, 'OK')}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Access-Control-Allow-Origin: *\r\n"
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
