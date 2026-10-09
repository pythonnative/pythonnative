"""The on-device dev client: pair with ``pn start``, sync sources, and serve DevTools.

Every debug build is a *dev client*: PythonNative Go (the prebuilt,
project-independent client) and a project's own ``pn run`` build alike.
It connects to the dev server over WebSocket and speaks version 2 of the
dev session protocol (RFC 0006):

- **Handshake.** ``hello`` describes the client's runtime (framework and
  Python versions, bridge protocol, contract fingerprint, plugins,
  bundled distributions) and the sources its overlay already holds. The
  server answers with a ``sync`` of whatever is missing, or with
  ``incompatible`` and the command that fixes the mismatch.
- **Sources and packages.** ``sync`` and ``update`` write files into the
  writable overlay that shadows the bundle (see
  ``pythonnative.hot_reload.configure_dev_environment``) and apply them
  with Fast Refresh. ``packages`` installs pure-Python distributions
  from the developer's environment into the overlay's ``site-packages``.
- **DevTools.** ``rpc`` requests go to the
  [devtools agent][pythonnative.devtools.agent.Agent] and are answered
  with ``rpc_result``; the agent's events go back as ``event``. ``tunnel``
  messages carry TCP streams, which the debugger uses.
- **Logs.** ``print`` output and errors stream back to the terminal and
  DevTools as ``log`` and ``error`` messages.

Clients are pointed at a server by a connect link,
``pn-<application id>://connect?url=<server URL>``, which ``pn run``, ``pn
go``, and a scanned QR code open. The last server is remembered, so a
relaunch reconnects. Without one, PythonNative Go shows its
[home screen][pythonnative.devclient.GoHome].

All network I/O runs on daemon threads; file writes happen there too,
and reloads run on the application thread.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import shutil
import socket
import sys
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from .assets import configure_native, manifest_for_sync
from .devserver import ws
from .devserver.watcher import is_synced_file, modules_for_paths
from .utils import overlay_root

__all__ = [
    "LINK_ENV",
    "SESSION_PROTOCOL",
    "DevClient",
    "GoHome",
    "client_info",
    "connect_link",
    "current",
    "dev_scheme",
    "display_server_url",
    "go_home",
    "handle_link",
    "normalize_server_url",
    "parse_connect_link",
    "recent_servers",
    "start",
    "start_if_configured",
    "stop",
]

SESSION_PROTOCOL = 2
"""Version of the dev session protocol spoken with ``pn start``."""

LINK_ENV = "PN_CONNECT_LINK"
"""Launch environment variable carrying a connect link.

``pn run ios`` and ``pn go ios`` launch with it: iOS asks the user to
confirm a link opened with ``simctl openurl``, while a launch environment
variable reaches the app silently."""

CLIENT_INFO_FILE = "_dev_client.json"
"""Written into the bundled ``pythonnative`` package of debug builds: ``{"kind", "app_id", "scheme"}``."""

_SERVERS_FILE = "servers.json"
_PACKAGES_MANIFEST = ".pn-packages.json"
_MAX_RECENT = 6
_RECONNECT_DELAYS = (0.5, 1.0, 2.0, 3.0, 5.0)

Logger = Callable[[str], None]

_current: Optional["DevClient"] = None
_lock = threading.Lock()
_pending_link: Optional[str] = None
_startup_checked = False


# ======================================================================
# Identity and links
# ======================================================================


def dev_scheme(app_id: str) -> str:
    """The connect-link URL scheme of the dev client for ``app_id``.

    ``pn-`` plus the application id, lowercased, with underscores turned
    into hyphens (URL schemes allow letters, digits, ``+``, ``-``, and
    ``.``): ``com.example.my_app`` becomes ``pn-com.example.my-app``.
    """
    return "pn-" + app_id.lower().replace("_", "-")


def connect_link(scheme: str, server_url: str) -> str:
    """``<scheme>://connect?url=<server URL>``, the link a QR code carries."""
    return f"{scheme}://connect?url={quote(server_url, safe='')}"


def parse_connect_link(link: str) -> Optional[str]:
    """The server URL inside a connect link, or ``None`` when ``link`` isn't one."""
    try:
        parts = urlsplit(link.strip())
    except ValueError:
        return None
    if not parts.scheme.startswith("pn-") or parts.netloc != "connect":
        return None
    url = dict(parse_qsl(parts.query)).get("url")
    return url or None


_info: Optional[Dict[str, Any]] = None


def client_info() -> Dict[str, Any]:
    """What kind of dev client this build is: ``{"kind": "go" | "app", "app_id", "scheme"}``.

    The builder writes it into debug builds; a process without one (tests,
    the host) is an ``"app"`` client.
    """
    global _info
    if _info is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CLIENT_INFO_FILE)
        data: Dict[str, Any] = {}
        try:
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            pass
        data.setdefault("kind", "app")
        _info = data
    return dict(_info)


# ======================================================================
# URLs
# ======================================================================


def normalize_server_url(text: str) -> str:
    """Turn whatever the developer typed into a dev-client WebSocket URL.

    Accepts ``192.168.1.20``, ``192.168.1.20:8765``, ``http://host:port``,
    ``ws://host:port``, full URLs with a path such as the device URL
    ``pn start`` prints (``http://192.168.1.20:8765/?token=...``), and
    connect links. The result always has the path ``/ws`` and the query
    ``role=client&token=...``; the dev token is kept when the input
    carries one.
    """
    from .devserver.auth import QUERY_PARAM

    value = (text or "").strip()
    if not value:
        raise ValueError("empty server address")
    inner = parse_connect_link(value)
    if inner is not None:
        value = inner
    if "://" not in value:
        value = "ws://" + value
    parts = urlsplit(value)
    scheme = {"http": "ws", "ws": "ws", "https": "wss", "wss": "wss"}.get(parts.scheme.lower())
    if scheme is None:
        raise ValueError(f"unsupported dev server scheme in {text!r}")
    hostport = parts.netloc
    if not hostport:
        raise ValueError(f"missing host in {text!r}")
    if ":" not in hostport:
        from .devserver.server import DEFAULT_PORT

        hostport = f"{hostport}:{DEFAULT_PORT}"
    query: List[Tuple[str, str]] = [("role", "client")]
    token = dict(parse_qsl(parts.query)).get(QUERY_PARAM)
    if token:
        query.append((QUERY_PARAM, token))
    return urlunsplit((scheme, hostport, "/ws", urlencode(query), ""))


def display_server_url(url: str) -> str:
    """The short form of a dev-client URL (``host:port``), without the token."""
    return urlsplit(url).netloc


# ======================================================================
# Recent servers
# ======================================================================


def _servers_path(overlay: str) -> str:
    return os.path.join(overlay, _SERVERS_FILE)


def recent_servers(overlay: Optional[str] = None) -> List[Dict[str, Any]]:
    """Servers this client connected to, most recent first: ``[{"url", "project", "last"}]``."""
    root = overlay or overlay_root()
    if not root:
        return []
    try:
        with open(_servers_path(root), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    entries = data.get("servers") if isinstance(data, dict) else None
    return [entry for entry in entries or [] if isinstance(entry, dict) and entry.get("url")]


def _remember_server(overlay: str, url: str, project: str) -> None:
    entries = [entry for entry in recent_servers(overlay) if entry.get("url") != url]
    entries.insert(0, {"url": url, "project": project, "last": time.time()})
    try:
        os.makedirs(overlay, exist_ok=True)
        with open(_servers_path(overlay), "w", encoding="utf-8") as handle:
            json.dump({"servers": entries[:_MAX_RECENT]}, handle)
    except OSError:
        pass


def _forget_last_server(overlay: str) -> None:
    """Keep the history but stop reconnecting automatically at launch."""
    entries = recent_servers(overlay)
    for entry in entries:
        entry["auto"] = False
    try:
        with open(_servers_path(overlay), "w", encoding="utf-8") as handle:
            json.dump({"servers": entries}, handle)
    except OSError:
        pass


# ======================================================================
# Log forwarding
# ======================================================================


class _Tee:
    """A text stream that writes through and also forwards whole lines."""

    def __init__(self, inner: Any, forward: Callable[[str], None]) -> None:
        self._inner = inner
        self._forward = forward
        self._buffer = ""

    def write(self, text: str) -> int:
        try:
            self._inner.write(text)
        except Exception:
            pass
        self._buffer += text
        if "\n" in self._buffer:
            lines = self._buffer.split("\n")
            self._buffer = lines.pop()
            for line in lines:
                if line:
                    self._forward(line)
        return len(text)

    def flush(self) -> None:
        try:
            self._inner.flush()
        except Exception:
            pass
        if self._buffer:
            line, self._buffer = self._buffer, ""
            self._forward(line)

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return int(self._inner.fileno())

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# ======================================================================
# Runtime description
# ======================================================================


def _bundled_distributions(exclude: str) -> Dict[str, str]:
    """``{name: version}`` of the distributions the build bundles (not the overlay's)."""
    import importlib.metadata as metadata

    excluded = os.path.abspath(exclude)
    search = [p for p in sys.path if p and not os.path.abspath(p).startswith(excluded)]
    found: Dict[str, str] = {}
    try:
        for dist in metadata.distributions(path=search):
            name = dist.metadata.get("Name") if dist.metadata is not None else None
            if name:
                found[str(name)] = str(dist.version)
    except Exception:
        pass
    return found


def _runtime(overlay: str) -> Dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version

    from .bridge.commits import PROTOCOL_VERSION
    from .sdk import schema

    try:
        framework = version("pythonnative")
    except PackageNotFoundError:
        framework = ""
    try:
        contracts = schema.fingerprint()
    except Exception:
        contracts = ""
    info = client_info()
    return {
        "pythonnative": framework,
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "protocol": PROTOCOL_VERSION,
        "contracts": contracts,
        "plugins": list(info.get("plugins") or []),
        "distributions": _bundled_distributions(overlay),
    }


# ======================================================================
# The client
# ======================================================================


class DevClient:
    """Keep this process in sync with a dev server and serve DevTools.

    Args:
        url: Server URL (any form accepted by
            [`normalize_server_url`][pythonnative.devclient.normalize_server_url]).
        overlay: Writable directory that shadows the bundled sources.
        entry_module: The app's entry module, for the ``hello`` message.
        forward_logs: Mirror ``print`` output to the server.
        log: Local logger for the client's own status lines.
        kind: ``"go"`` or ``"app"``; defaults to this build's
            [`client_info`][pythonnative.devclient.client_info].
        agent: Install the devtools agent (off in unit tests that only
            exercise syncing).
    """

    def __init__(
        self,
        url: str,
        overlay: str,
        *,
        entry_module: str = "app.main",
        forward_logs: bool = True,
        log: Optional[Logger] = None,
        kind: Optional[str] = None,
        agent: bool = True,
    ) -> None:
        self.url = normalize_server_url(url)
        self.overlay = os.path.abspath(overlay)
        self.entry_module = entry_module
        self.kind = kind or str(client_info().get("kind") or "app")
        self.project = ""
        self.incompatible: Optional[Dict[str, Any]] = None
        self._forward_logs = forward_logs
        self._log: Logger = log or self._default_log
        self._use_agent = agent
        self._agent: Any = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._socket: Optional[ws.WebSocketClient] = None
        self._send_lock = threading.Lock()
        self._state = "idle"
        self._state_lock = threading.Lock()
        self._listeners: List[Callable[[str, str], None]] = []
        self._outbox: List[str] = []
        self._outbox_lock = threading.Lock()
        self._tee_installed = False
        self._orig_stdout: Any = None
        self._orig_stderr: Any = None
        self._device = ""
        self._streams: Dict[int, socket.socket] = {}
        # Data that arrives while a stream's local connection is opening.
        self._opening: Dict[int, List[bytes]] = {}
        self._streams_lock = threading.Lock()
        self.synced_version: Optional[str] = None
        self.synced_once = threading.Event()

    # -- state -----------------------------------------------------------

    @property
    def server_label(self) -> str:
        """``host:port`` of the server, for logs (the full URL carries the dev token)."""
        return urlsplit(self.url).netloc

    @property
    def state(self) -> str:
        """``"idle"``, ``"connecting"``, ``"connected"``, ``"syncing"``, ``"incompatible"``, or ``"disconnected"``."""
        with self._state_lock:
            return self._state

    @property
    def agent(self) -> Any:
        """The devtools agent this client serves, once started."""
        return self._agent

    def add_listener(self, callback: Callable[[str, str], None]) -> Callable[[], None]:
        """Subscribe to ``(state, detail)`` changes (called on the client thread)."""
        self._listeners.append(callback)

        def _remove() -> None:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

        return _remove

    def _set_state(self, state: str, detail: str = "") -> None:
        with self._state_lock:
            self._state = state
        for listener in list(self._listeners):
            try:
                listener(state, detail)
            except Exception:
                pass

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Connect on a daemon thread (idempotent)."""
        if self._thread is not None:
            return
        self._stop.clear()
        # Resolve device metadata before starting the network worker.
        self._device = _device_name()
        self._install_tee()
        if self._use_agent:
            self._install_agent()
        self._thread = threading.Thread(target=self._run, name="pn-dev-client", daemon=True)
        _mark_dev_thread(self._thread)
        self._thread.start()

    def stop(self) -> None:
        """Disconnect and stop the thread."""
        self._stop.set()
        sock = self._socket
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._close_streams()
        self._remove_tee()
        if self._agent is not None:
            from .devtools import agent as agent_module

            if agent_module.current() is self._agent:
                agent_module.uninstall()
            self._agent = None
        self._set_state("idle")

    def _install_agent(self) -> None:
        from .devtools import install
        from .devtools.debugger import install_breakpoint_hook

        self._agent = install(
            lambda topic, data: self.send({"type": "event", "topic": topic, "data": data}),
            kind=self.kind,
            disconnect=go_home if self.kind == "go" else None,
        )
        install_breakpoint_hook()

    def _run(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            self._set_state("connecting", self.server_label)
            try:
                self._session()
                attempt = 0
            except (OSError, ws.WebSocketError) as exc:
                detail = f"{type(exc).__name__}: {exc}"
                refused = isinstance(exc, ws.HandshakeError) and any(f" {code} " in f"{exc} " for code in (401, 403))
                if refused:
                    detail = "the dev server refused this client's token"
                self._set_state("disconnected", detail)
                if attempt == 0 and refused:
                    self._log(
                        f"[pn dev] {self.server_label} refused the connection: the link is missing the dev "
                        "token or carries an old one. Scan the QR code `pn start` prints, or relaunch with "
                        "`pn run`."
                    )
                elif attempt == 0:
                    self._log(f"[pn dev] cannot reach {self.server_label} ({detail}); retrying")
            except Exception as exc:
                self._set_state("disconnected", repr(exc))
                self._log(f"[pn dev] client error: {exc!r}")
                traceback.print_exc(file=self._local_stderr())
            if self._stop.is_set() or self.incompatible is not None:
                break
            delay = _RECONNECT_DELAYS[min(attempt, len(_RECONNECT_DELAYS) - 1)]
            attempt += 1
            self._stop.wait(delay)

    def _session(self) -> None:
        client = ws.WebSocketClient(self.url, timeout=1.0)
        client.connect()
        self._socket = client
        try:
            self._send_now(json.dumps(self._hello()))
            self._set_state("connected", self.server_label)
            self._flush_outbox()
            while not self._stop.is_set():
                try:
                    text = client.recv()
                except socket.timeout:
                    self._flush_outbox()
                    continue
                if text is None:
                    break
                try:
                    message = json.loads(text)
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self._handle(message)
                self._flush_outbox()
        finally:
            self._socket = None
            try:
                client.close()
            except Exception:
                pass
            self._close_streams()
            if not self._stop.is_set() and self.incompatible is None:
                self._set_state("disconnected", "connection closed")

    # -- protocol --------------------------------------------------------

    def _hello(self) -> Dict[str, Any]:
        from .platform import Platform

        self._seed_overlay_from_bundle()
        return {
            "type": "hello",
            "session": SESSION_PROTOCOL,
            "client": self.kind,
            "platform": Platform.OS,
            "device": self._device,
            "app": self.entry_module,
            "runtime": _runtime(self.overlay),
            "files": self._overlay_manifest(),
            "packages": self._installed_packages(),
        }

    def _seed_overlay_from_bundle(self) -> None:
        """Copy the bundled sources into an empty overlay before the first ``hello``.

        The overlay must be a complete tree (a partial ``app/`` without
        ``__init__.py`` would lose to the bundled package on ``sys.path``).
        Seeding from the bundle lets the manifest report what the app
        already runs; the server then sends only real differences, and an
        up-to-date build connects without a reload.
        """
        top = self.entry_module.split(".")[0]
        if not top or self._overlay_has_files(top):
            return
        seeded = seed_overlay(self.overlay, top, log=self._log)
        if seeded:
            self._log(f"[pn dev] seeded the overlay with {seeded} bundled file(s)")

    def _overlay_has_files(self, top: str) -> bool:
        for _dirpath, dirnames, filenames in os.walk(os.path.join(self.overlay, top)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if filenames:
                return True
        return False

    def _overlay_manifest(self) -> Dict[str, str]:
        files: Dict[str, str] = {}
        base = self.overlay
        for dirpath, dirnames, filenames in os.walk(base):
            rel_dir = os.path.relpath(dirpath, base).replace(os.sep, "/")
            if rel_dir == _PACKAGES_ROOT or rel_dir.startswith(_PACKAGES_ROOT + "/"):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d != "__pycache__" and d != _PACKAGES_ROOT]
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, base).replace(os.sep, "/")
                if rel == _SERVERS_FILE or not is_synced_file(rel):
                    continue
                try:
                    with open(full, "rb") as handle:
                        files[rel] = hashlib.sha256(handle.read()).hexdigest()
                except OSError:
                    continue
        return files

    def _handle(self, message: Dict[str, Any]) -> None:
        kind = message.get("type")
        if kind in ("sync", "update"):
            self._apply_sync(message)
        elif kind == "packages":
            self._apply_packages(message)
        elif kind == "incompatible":
            self._on_incompatible(message)
        elif kind == "rpc":
            self._on_rpc(message)
        elif kind == "tunnel":
            self._on_tunnel(message)
        elif kind == "menu":
            if self._agent is not None:
                self._agent.open_menu()
        elif kind == "reload":
            if self._agent is not None:
                self._agent.dispatch("reload", {}, lambda _result, _error: None)

    def _apply_sync(self, message: Dict[str, Any]) -> None:
        self._set_state("syncing", str(message.get("version") or ""))
        self.project = str(message.get("project") or self.project)
        written: List[str] = []
        for entry in message.get("files") or []:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "")
            if not path or not _safe_relpath(path) or path.startswith(_PACKAGES_ROOT + "/"):
                continue
            data = _decode_content(entry)
            if data is None:
                continue
            if self._write(path, data):
                written.append(path)
        for path in message.get("removed") or []:
            rel = str(path)
            if not _safe_relpath(rel) or rel.startswith(_PACKAGES_ROOT + "/"):
                continue
            try:
                os.remove(os.path.join(self.overlay, *rel.split("/")))
            except OSError:
                pass
            written.append(rel)
        version = str(message.get("version") or "")
        self.synced_version = version
        self.synced_once.set()
        _remember_server(self.overlay, self.url, self.project)
        self._set_state("connected", version)
        if not written:
            # The app already runs these exact sources (a fresh build, or an
            # overlay from the last session): nothing to reload.
            return
        self._log(f"[pn dev] synced {len(written)} file(s) from {self.server_label}")
        modules = modules_for_paths(written)
        assets_changed = bool(manifest_for_sync(written))
        if modules or assets_changed:
            self._schedule_reload(modules, version, assets_changed=assets_changed)

    def _write(self, rel: str, data: bytes) -> bool:
        target = os.path.join(self.overlay, *rel.split("/"))
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(data)
            return True
        except OSError as exc:
            self._log(f"[pn dev] could not write {rel}: {exc}")
            return False

    # -- packages --------------------------------------------------------

    def _packages_dir(self) -> str:
        return os.path.join(self.overlay, _PACKAGES_ROOT)

    def _packages_manifest(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(os.path.join(self._packages_dir(), _PACKAGES_MANIFEST), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}

    def _installed_packages(self) -> Dict[str, str]:
        """``{name: version}`` of the distributions synced into the overlay."""
        return {name: str(entry.get("version") or "") for name, entry in self._packages_manifest().items()}

    def _apply_packages(self, message: Dict[str, Any]) -> None:
        manifest = self._packages_manifest()
        root = self._packages_dir()
        changed: List[str] = []
        for name in message.get("removed") or []:
            self._remove_package(manifest, str(name))
            changed.append(str(name))
        for package in message.get("packages") or []:
            if not isinstance(package, dict) or not package.get("name"):
                continue
            name = str(package["name"])
            self._remove_package(manifest, name)
            files: List[str] = []
            for entry in package.get("files") or []:
                if not isinstance(entry, dict):
                    continue
                rel = str(entry.get("path") or "")
                data = _decode_content(entry)
                if not rel or not _safe_relpath(rel) or data is None:
                    continue
                if self._write(f"{_PACKAGES_ROOT}/{rel}", data):
                    files.append(rel)
            manifest[name] = {"version": str(package.get("version") or ""), "files": files}
            changed.append(name)
            self._log(f"[pn dev] installed {name} {package.get('version') or ''} ({len(files)} files)")
        try:
            os.makedirs(root, exist_ok=True)
            with open(os.path.join(root, _PACKAGES_MANIFEST), "w", encoding="utf-8") as handle:
                json.dump(manifest, handle)
        except OSError:
            pass
        if root not in sys.path:
            sys.path.append(root)
        importlib.invalidate_caches()
        if message.get("request") is not None:
            self.send({"type": "packages_ready", "request": message.get("request"), "packages": changed})

    def _remove_package(self, manifest: Dict[str, Dict[str, Any]], name: str) -> None:
        entry = manifest.pop(name, None)
        if not entry:
            return
        root = self._packages_dir()
        for rel in entry.get("files") or []:
            if _safe_relpath(str(rel)):
                try:
                    os.remove(os.path.join(root, *str(rel).split("/")))
                except OSError:
                    pass

    # -- compatibility ---------------------------------------------------

    def _on_incompatible(self, message: Dict[str, Any]) -> None:
        self.incompatible = {"reason": str(message.get("reason") or ""), "fix": str(message.get("fix") or "")}
        detail = self.incompatible["reason"]
        if self.incompatible["fix"]:
            detail += f" {self.incompatible['fix']}"
        self._log(f"[pn dev] {self.server_label} can't run on this client: {detail}")
        self._set_state("incompatible", detail)
        self._stop.set()

    # -- devtools --------------------------------------------------------

    def _on_rpc(self, message: Dict[str, Any]) -> None:
        request_id = message.get("id")
        agent = self._agent
        if agent is None:
            self.send({"type": "rpc_result", "id": request_id, "error": "DevTools aren't available in this client"})
            return

        def reply(result: Optional[Any], error: Optional[str]) -> None:
            if error is not None:
                self.send({"type": "rpc_result", "id": request_id, "error": error})
                return
            try:
                json.dumps(result)
            except (TypeError, ValueError):
                result = repr(result)
            self.send({"type": "rpc_result", "id": request_id, "result": result})

        agent.dispatch(str(message.get("method") or ""), message.get("params") or {}, reply)

    # -- tunnels ---------------------------------------------------------

    def _on_tunnel(self, message: Dict[str, Any]) -> None:
        stream = int(message.get("stream") or 0)
        op = message.get("op")
        if op == "open":
            port = int(message.get("port") or 0)
            with self._streams_lock:
                self._opening[stream] = []
            threading.Thread(
                target=self._open_stream, args=(stream, port), name=f"pn-tunnel-{stream}", daemon=True
            ).start()
        elif op == "data":
            data = message.get("data")
            with self._streams_lock:
                sock = self._streams.get(stream)
                pending = self._opening.get(stream)
                if sock is None and pending is not None and isinstance(data, str):
                    pending.append(base64.b64decode(data))
                    return
            if sock is not None and isinstance(data, str):
                try:
                    sock.sendall(base64.b64decode(data))
                except OSError:
                    self._close_stream(stream)
        elif op == "close":
            self._close_stream(stream, notify=False)

    def _open_stream(self, stream: int, port: int) -> None:
        _mark_dev_thread()
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=5.0)
            sock.settimeout(None)
        except OSError as exc:
            with self._streams_lock:
                self._opening.pop(stream, None)
            self.send({"type": "tunnel", "stream": stream, "op": "close", "error": str(exc)})
            return
        with self._streams_lock:
            pending = self._opening.pop(stream, [])
            try:
                for chunk in pending:
                    sock.sendall(chunk)
            except OSError:
                pass
            self._streams[stream] = sock
        while True:
            try:
                chunk = sock.recv(65536)
            except OSError:
                chunk = b""
            if not chunk:
                break
            self.send({"type": "tunnel", "stream": stream, "op": "data", "data": base64.b64encode(chunk).decode()})
        self._close_stream(stream)

    def _close_stream(self, stream: int, *, notify: bool = True) -> None:
        with self._streams_lock:
            self._opening.pop(stream, None)
            sock = self._streams.pop(stream, None)
        if sock is None:
            return
        try:
            sock.close()
        except OSError:
            pass
        if notify:
            self.send({"type": "tunnel", "stream": stream, "op": "close"})

    def _close_streams(self) -> None:
        with self._streams_lock:
            streams, self._streams = self._streams, {}
        for sock in streams.values():
            try:
                sock.close()
            except OSError:
                pass

    # -- reloads ---------------------------------------------------------

    def _schedule_reload(self, modules: List[str], version: str, *, assets_changed: bool = False) -> None:
        from .runtime import call_on_application_thread

        def _apply() -> None:
            from .hot_reload import apply_reload

            if assets_changed:
                # Push the overlay manifest first so reloaded components
                # (and the native image views) resolve the new files.
                configure_native()
            if not modules:
                return
            result = apply_reload(modules)
            if result.mode == "error":
                self.send({"type": "error", "phase": "hot reload", "text": result.error or "unknown error"})
            elif result.mode != "none":
                self.send(
                    {"type": "reloaded", "version": version, "mode": result.mode, "modules": result.reloaded or modules}
                )

        call_on_application_thread(_apply)

    # -- outbound --------------------------------------------------------

    def send(self, message: Dict[str, Any]) -> None:
        """Send a message to the server from any thread (queued while offline)."""
        try:
            text = json.dumps(message)
        except (TypeError, ValueError):
            text = json.dumps({"type": "log", "level": "error", "text": f"unserializable message {message!r}"})
        with self._outbox_lock:
            if len(self._outbox) > 1000:
                del self._outbox[:200]
            self._outbox.append(text)
        self._flush_outbox()

    def _send_now(self, text: str) -> None:
        sock = self._socket
        if sock is None:
            raise OSError("not connected")
        with self._send_lock:
            sock.send_text(text)

    def _flush_outbox(self) -> None:
        if self._socket is None:
            return
        while True:
            with self._outbox_lock:
                if not self._outbox:
                    return
                text = self._outbox.pop(0)
            try:
                self._send_now(text)
            except Exception:
                with self._outbox_lock:
                    self._outbox.insert(0, text)
                return

    def log(self, text: str, level: str = "info") -> None:
        """Forward one log line to the server."""
        self.send({"type": "log", "level": level, "text": text})

    def report_error(self, phase: str, text: str) -> None:
        """Forward an error report (a traceback) to the server."""
        self.send({"type": "error", "phase": phase, "text": text})

    # -- stdout / stderr tee -----------------------------------------------

    def _local_stderr(self) -> Any:
        """The process's real stderr, bypassing the tee (so status lines stay local).

        Not ``sys.__stderr__``: embedded interpreters replace ``sys.stderr``
        with a stream that reaches the platform log (logcat, the Xcode
        console) while the original file descriptor goes nowhere.
        """
        stream = sys.stderr
        while isinstance(stream, _Tee):
            stream = stream._inner
        return stream if stream is not None else sys.__stderr__

    def _default_log(self, line: str) -> None:
        try:
            print(line, file=self._local_stderr(), flush=True)
        except Exception:
            pass

    def _install_tee(self) -> None:
        if not self._forward_logs or self._tee_installed:
            return
        self._tee_installed = True
        self._orig_stdout, self._orig_stderr = sys.stdout, sys.stderr
        sys.stdout = _Tee(self._orig_stdout, lambda line: self.log(line, "info"))
        sys.stderr = _Tee(self._orig_stderr, lambda line: self.log(line, "error"))

    def _remove_tee(self) -> None:
        if not self._tee_installed:
            return
        self._tee_installed = False
        if isinstance(sys.stdout, _Tee):
            sys.stdout = self._orig_stdout
        if isinstance(sys.stderr, _Tee):
            sys.stderr = self._orig_stderr


_PACKAGES_ROOT = "site-packages"


def _mark_dev_thread(thread: Optional[threading.Thread] = None) -> None:
    from .devtools.debugger import mark_dev_thread

    mark_dev_thread(thread)


def _safe_relpath(rel: str) -> bool:
    parts = rel.split("/")
    return bool(parts) and all(part and part not in (".", "..") for part in parts)


def _device_name() -> str:
    """A short device label for the server's client list (``iPhone``, ``Pixel 8``)."""
    try:
        from .native_modules.registry import native_module

        info = native_module("Device").call("info")
        if isinstance(info, dict):
            return str(info.get("model") or info.get("os") or "")
    except Exception:
        pass
    return ""


def _bundled_package_root(top: str, *, exclude: str) -> Optional[Any]:
    """A ``Traversable`` for the bundled top-level package ``top``, ignoring the overlay.

    Resolves through ``sys.path`` the way the import system would once the
    overlay is out of the picture, without importing anything, then asks
    the loader for its resource reader. On iOS that is a plain directory;
    under Chaquopy the ``.py`` sources live in the APK's asset archive and
    only the reader can list and read them (``os.walk`` on the extracted
    directory sees data files alone).
    """
    import importlib.machinery

    excluded = os.path.abspath(exclude)
    search = [p for p in sys.path if p and not os.path.abspath(p).startswith(excluded)]
    try:
        spec = importlib.machinery.PathFinder.find_spec(top, search)
    except Exception:
        return None
    if spec is None or not spec.submodule_search_locations or spec.loader is None:
        return None
    get_reader = getattr(spec.loader, "get_resource_reader", None)
    if get_reader is None:
        return None
    try:
        reader = get_reader(top)
        files = getattr(reader, "files", None)
        root = files() if files is not None else None
    except Exception:
        return None
    if root is None or not root.is_dir():
        return None
    return root


def seed_overlay(overlay: str, top: str, *, log: Optional[Logger] = None) -> int:
    """Copy the bundled ``top`` package into ``overlay``; returns the number of files."""
    emit = log or (lambda line: None)
    root = _bundled_package_root(top, exclude=overlay)
    if root is None:
        emit(f"[pn dev] bundled sources for '{top}' not found; the server will send everything")
        return 0
    seeded = 0

    def copy_tree(node: Any, rel: str) -> None:
        nonlocal seeded
        try:
            children = list(node.iterdir())
        except Exception as exc:
            emit(f"[pn dev] could not list bundled {rel}: {exc}")
            return
        for child in children:
            child_rel = f"{rel}/{child.name}"
            if child.is_dir():
                if child.name != "__pycache__":
                    copy_tree(child, child_rel)
                continue
            if not is_synced_file(child_rel):
                continue
            target = os.path.join(overlay, *child_rel.split("/"))
            try:
                data = child.read_bytes()
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as handle:
                    handle.write(data)
                seeded += 1
            except Exception as exc:
                emit(f"[pn dev] could not seed {child_rel}: {exc}")

    copy_tree(root, top)
    return seeded


def _decode_content(entry: Dict[str, Any]) -> Optional[bytes]:
    content = entry.get("content")
    if not isinstance(content, str):
        return None
    if entry.get("encoding") == "base64":
        try:
            return base64.b64decode(content)
        except (ValueError, TypeError):
            return None
    return content.encode("utf-8")


# ======================================================================
# Process-wide client
# ======================================================================


def current() -> Optional[DevClient]:
    """The running dev client, if any."""
    return _current


def start(url: str, overlay: Optional[str] = None, **kwargs: Any) -> DevClient:
    """Start (or replace) the process-wide dev client for ``url``."""
    global _current
    from .hot_reload import configure_dev_environment

    root = overlay or overlay_root()
    if root is None:
        root = configure_dev_environment(os.path.join(os.path.expanduser("~"), ".pythonnative"))
    with _lock:
        previous = _current
        if previous is not None:
            previous.stop()
        client = DevClient(url, root, **kwargs)
        _current = client
    client.start()
    _notify_home()
    return client


def stop() -> None:
    """Stop the process-wide dev client; the dev menu keeps working locally."""
    global _current
    with _lock:
        client, _current = _current, None
    if client is not None:
        client.stop()
        if client._use_agent:
            install_local_agent()
    _notify_home()


def install_local_agent() -> None:
    """Install a devtools agent that isn't connected to a server (dev menu, inspector, monitor)."""
    from .devtools import install
    from .devtools.debugger import install_breakpoint_hook

    kind = str(client_info().get("kind") or "app")
    install(lambda _topic, _data: None, kind=kind, disconnect=go_home if kind == "go" else None)
    install_breakpoint_hook()


def handle_link(link: str) -> bool:
    """Connect to the server a connect link names; ``True`` when ``link`` was one.

    Installed as the deep-link interceptor by
    ``pythonnative.hot_reload.configure_dev_environment``. A link that
    arrives before the dev client starts (a cold launch from a QR code)
    is kept for [`start_if_configured`][pythonnative.devclient.start_if_configured].
    """
    global _pending_link
    url = parse_connect_link(link)
    if url is None:
        return False
    client = _current
    if client is None:
        if not _startup_checked:
            # Startup hasn't looked for a server yet; it will use this one.
            _pending_link = url
            return True
        # A cold-start link can arrive after startup (Android delivers the
        # launch intent's link as an ordinary event): connect now.
        root = overlay_root()
        if root is not None:
            start(url, root, entry_module=os.environ.get("PN_ENTRY_MODULE") or "app.main")
        return True
    try:
        if normalize_server_url(url) == client.url and client.state not in ("incompatible", "idle"):
            return True
    except ValueError:
        return True
    entry = client.entry_module
    start(url, client.overlay, entry_module=entry)
    return True


def start_if_configured(entry_module: Optional[str] = None) -> Optional[DevClient]:
    """Start the dev client when a connect link or a remembered server names one.

    Called by ``bootstrap.start(dev=True)``. A connect link that launched
    the app (as a deep link, or in ``PN_CONNECT_LINK``) wins; otherwise the
    most recent server reconnects. Returns the
    client, or ``None`` when nothing is configured (PythonNative Go then
    shows its home screen).
    """
    global _pending_link, _startup_checked
    _startup_checked = True
    root = overlay_root()
    if root is None:
        return None
    url = _pending_link or parse_connect_link(os.environ.pop(LINK_ENV, "") or "")
    _pending_link = None
    if not url:
        recent = recent_servers(root)
        if recent and recent[0].get("auto", True):
            url = str(recent[0]["url"])
    if not url:
        return None
    entry = entry_module or os.environ.get("PN_ENTRY_MODULE") or "app.main"
    try:
        return start(url, root, entry_module=entry)
    except Exception as exc:
        print(f"[pn dev] could not start the dev client: {exc!r}", file=sys.stderr)
        return None


def go_home() -> None:
    """Disconnect PythonNative Go and return to its home screen.

    Stops the client, replaces the overlay's app with the bundled home
    screen, stops reconnecting at launch, and remounts.
    """
    client = _current
    root = client.overlay if client is not None else overlay_root()
    entry = client.entry_module if client is not None else "app.main"
    stop()
    if root is None:
        return
    _forget_last_server(root)
    top = entry.split(".")[0]
    shutil.rmtree(os.path.join(root, top), ignore_errors=True)
    seed_overlay(root, top)
    from .runtime import call_on_application_thread

    def remount() -> None:
        from .devtools.agent import reload_app

        reload_app()

    call_on_application_thread(remount)


# ======================================================================
# PythonNative Go home screen
# ======================================================================

_home_listeners: List[Callable[[], None]] = []


def _notify_home() -> None:
    for listener in list(_home_listeners):
        try:
            listener()
        except Exception:
            pass


def _go_home_screen() -> Any:
    from . import components as c
    from .component import component
    from .hooks import use_effect, use_state

    colors = {
        "background": "#0B0D12",
        "card": "#161A22",
        "text": "#F5F7FA",
        "muted": "#8A93A6",
        "accent": "#3B82F6",
        "good": "#22C55E",
        "warn": "#F59E0B",
        "bad": "#EF4444",
    }
    state_colors = {
        "connecting": colors["warn"],
        "connected": colors["good"],
        "syncing": colors["accent"],
        "disconnected": colors["bad"],
        "incompatible": colors["bad"],
        "error": colors["bad"],
    }

    @component
    def GoHome() -> Any:
        tick, set_tick = use_state(0)
        typed, set_typed = use_state("")
        status, set_status = use_state(("idle", ""))

        def subscribe() -> Callable[[], None]:
            from .runtime import call_on_application_thread

            def refresh() -> None:
                call_on_application_thread(lambda: set_tick(lambda value: value + 1))

            _home_listeners.append(refresh)
            client = current()
            remove_state: Optional[Callable[[], None]] = None
            if client is not None:

                def on_state(state: str, detail: str) -> None:
                    call_on_application_thread(lambda: set_status((state, detail)))

                remove_state = client.add_listener(on_state)
                set_status((client.state, client.server_label))

            def unsubscribe() -> None:
                if refresh in _home_listeners:
                    _home_listeners.remove(refresh)
                if remove_state is not None:
                    remove_state()

            return unsubscribe

        use_effect(subscribe, [tick])

        def connect(url: str) -> None:
            try:
                normalized = normalize_server_url(url)
            except ValueError as exc:
                set_status(("error", str(exc)))
                return
            start(normalized, entry_module=os.environ.get("PN_ENTRY_MODULE") or "app.main")

        state, detail = status
        client = current()
        incompatible = client.incompatible if client is not None else None
        recents = recent_servers()

        def recent_row(entry: Dict[str, Any]) -> Any:
            url = str(entry.get("url") or "")
            title = str(entry.get("project") or display_server_url(url))
            return c.Pressable(
                c.Column(
                    c.Text(title, style={"color": colors["text"], "font_size": 16, "font_weight": "600"}),
                    c.Text(display_server_url(url), style={"color": colors["muted"], "font_size": 13}),
                    style={"gap": 2},
                ),
                on_press=lambda: connect(url),
                accessibility_label=f"Open {title}",
                style={"padding": 14, "background_color": colors["card"], "border_radius": 12},
            ).with_key(url)

        from . import __version__ as framework_version

        return c.ScrollView(
            c.Column(
                c.Column(
                    c.Text("PythonNative Go", style={"font_size": 32, "font_weight": "700", "color": colors["text"]}),
                    c.Text(
                        f"Version {framework_version} · run any PythonNative project without building it",
                        style={"font_size": 14, "color": colors["muted"]},
                    ),
                    style={"gap": 6},
                ),
                c.Column(
                    c.Text("Get started", style={"font_size": 13, "color": colors["muted"], "font_weight": "600"}),
                    c.Text(
                        "On your computer, run `pn start` in your project. Then scan the QR code it prints "
                        "with your camera, or press i (iOS Simulator) or a (Android emulator) in that terminal.",
                        style={"font_size": 15, "color": colors["text"], "line_height": 21},
                    ),
                    style={"gap": 8, "padding": 16, "background_color": colors["card"], "border_radius": 14},
                ),
                (
                    c.Column(
                        c.Row(
                            c.View(
                                style={
                                    "width": 10,
                                    "height": 10,
                                    "border_radius": 5,
                                    "background_color": state_colors.get(state, colors["muted"]),
                                }
                            ),
                            c.Text(state.capitalize(), style={"color": colors["text"], "font_size": 15}),
                            style={"gap": 8, "align_items": "center"},
                        ),
                        c.Text(detail, style={"color": colors["muted"], "font_size": 13}) if detail else None,
                        (
                            c.Text(
                                f"{incompatible['reason']} {incompatible['fix']}".strip(),
                                style={"color": colors["bad"], "font_size": 14, "line_height": 20},
                                accessibility_label="Incompatible project",
                            )
                            if incompatible
                            else None
                        ),
                        style={"gap": 6, "padding": 16, "background_color": colors["card"], "border_radius": 14},
                    )
                    if state != "idle"
                    else None
                ),
                (
                    c.Column(
                        c.Text(
                            "Recently opened", style={"font_size": 13, "color": colors["muted"], "font_weight": "600"}
                        ),
                        *[recent_row(entry) for entry in recents],
                        style={"gap": 8},
                    )
                    if recents
                    else None
                ),
                c.Column(
                    c.Text("Enter a URL", style={"font_size": 13, "color": colors["muted"], "font_weight": "600"}),
                    c.TextInput(
                        value=typed,
                        on_change=set_typed,
                        placeholder="http://192.168.1.20:8765/?token=...",
                        auto_correct=False,
                        auto_capitalize="none",
                        keyboard_type="url",
                        accessibility_label="Dev server URL",
                        style={
                            "background_color": colors["card"],
                            "color": colors["text"],
                            "padding": 14,
                            "border_radius": 12,
                            "font_size": 15,
                        },
                    ),
                    c.Button(
                        "Connect",
                        on_press=lambda: connect(typed),
                        style={
                            "background_color": colors["accent"],
                            "color": "#FFFFFF",
                            "padding": 14,
                            "border_radius": 12,
                        },
                    ),
                    style={"gap": 8},
                ),
                style={"padding": 24, "padding_top": 72, "gap": 24},
            ),
            style={"flex": 1, "background_color": colors["background"]},
        )

    return GoHome


class _LazyGoHome:
    """Import-light proxy so ``from pythonnative.devclient import GoHome`` stays cheap."""

    _component: Any = None

    def _resolve(self) -> Any:
        if _LazyGoHome._component is None:
            _LazyGoHome._component = _go_home_screen()
        return _LazyGoHome._component

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)


GoHome: Any = _LazyGoHome()
"""Root component of PythonNative Go until a project arrives from a dev server."""


def go_main_source() -> str:
    """Source of the ``app/main.py`` staged into PythonNative Go."""
    return (
        '"""PythonNative Go\'s home screen.\n\n'
        "A project's own app/main.py arrives from the dev server and shadows this file.\n"
        '"""\n\n'
        "from pythonnative.devclient import GoHome as App\n\n"
        '__all__ = ["App"]\n'
    )
