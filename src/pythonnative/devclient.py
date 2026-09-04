"""The on-device dev client: sync sources from ``pn start`` and Fast Refresh.

A debug build of a PythonNative app is a *dev client*. On launch it
connects to the dev server (``pn start`` / ``pn preview`` / ``pn run``)
over WebSocket, reports the sources it already holds, receives whatever
is missing, and from then on applies every save as a Fast Refresh. Its
``print`` output and errors stream back to the terminal running the
server, so the device log viewer is optional.

How the pieces fit:

- The native template configures a writable **overlay** directory
  (``pythonnative.hot_reload.configure_dev_environment``) ahead of the
  bundled sources on ``sys.path`` and exposes the server URL the CLI
  baked in as ``PN_DEV_SERVER``. ``pythonnative.bootstrap.start(dev=True)``
  calls [`start_if_configured`][pythonnative.devclient.start_if_configured].
- A build made with ``pn run <platform> --dev-client`` has no app of
  its own: its bundled ``app/main.py`` renders
  [`ConnectScreen`][pythonnative.devclient.ConnectScreen], where the
  developer types (or picks) a server URL. Once the first sync lands,
  the real ``app.main`` from the overlay shadows the placeholder and
  the screen remounts into the developer's app. The URL is remembered
  for the next launch.

All network I/O runs on a daemon thread; file writes happen there too,
and only the reload itself hops to the main thread through
``call_on_main_thread``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import sys
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from .devserver import ws
from .devserver.watcher import is_synced_file, modules_for_paths

__all__ = [
    "ConnectScreen",
    "DevClient",
    "current",
    "normalize_server_url",
    "saved_server_url",
    "start",
    "start_if_configured",
    "stop",
]

SERVER_URL_ENV = "PN_DEV_SERVER"
"""Environment variable carrying the dev server URL baked in by ``pn run``."""

DEV_CLIENT_ENV = "PN_DEV_CLIENT"
"""Set to ``1`` in ``--dev-client`` builds (the connect screen remembers URLs)."""

_SAVED_URL_FILE = "server.json"
_RECONNECT_DELAYS = (0.5, 1.0, 2.0, 3.0, 5.0)

Logger = Callable[[str], None]

_current: Optional["DevClient"] = None
_lock = threading.Lock()


# ======================================================================
# URLs
# ======================================================================


def normalize_server_url(text: str) -> str:
    """Turn whatever the developer typed into a dev-client WebSocket URL.

    Accepts ``192.168.1.20``, ``192.168.1.20:8765``, ``http://host:port``,
    ``ws://host:port``, and full URLs with a path; the result always
    ends in ``/ws?role=client``.
    """
    value = (text or "").strip()
    if not value:
        raise ValueError("empty server address")
    if "://" not in value:
        value = "ws://" + value
    value = value.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    scheme, _, rest = value.partition("://")
    hostport, _, path = rest.partition("/")
    if ":" not in hostport:
        from .devserver.server import DEFAULT_PORT

        hostport = f"{hostport}:{DEFAULT_PORT}"
    if not path or path.startswith("?"):
        path = "ws?role=client"
    elif "role=" not in path:
        path = path.rstrip("/")
        path = (path + ("&" if "?" in path else "?") + "role=client") if path.startswith("ws") else "ws?role=client"
    return f"{scheme}://{hostport}/{path}"


def _saved_url_path(overlay: str) -> str:
    return os.path.join(overlay, _SAVED_URL_FILE)


def saved_server_url(overlay: Optional[str] = None) -> Optional[str]:
    """The URL remembered by a previous connection (``--dev-client`` builds)."""
    from .hot_reload import overlay_root

    root = overlay or overlay_root()
    if not root:
        return None
    try:
        with open(_saved_url_path(root), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    url = data.get("url") if isinstance(data, dict) else None
    return str(url) if url else None


def _save_server_url(overlay: str, url: str) -> None:
    try:
        os.makedirs(overlay, exist_ok=True)
        with open(_saved_url_path(overlay), "w", encoding="utf-8") as handle:
            json.dump({"url": url, "saved_at": time.time()}, handle)
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
        return self._inner.fileno()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# ======================================================================
# The client
# ======================================================================


class DevClient:
    """Keep this process in sync with a dev server.

    Args:
        url: Server URL (any form accepted by
            [`normalize_server_url`][pythonnative.devclient.normalize_server_url]).
        overlay: Writable directory that shadows the bundled sources.
        entry_module: The app's entry module, for the ``hello`` message.
        forward_logs: Mirror ``print`` output to the server.
        log: Local logger for the client's own status lines.
    """

    def __init__(
        self,
        url: str,
        overlay: str,
        *,
        entry_module: str = "app.main",
        forward_logs: bool = True,
        log: Optional[Logger] = None,
    ) -> None:
        self.url = normalize_server_url(url)
        self.overlay = os.path.abspath(overlay)
        self.entry_module = entry_module
        self._forward_logs = forward_logs
        self._log: Logger = log or self._default_log
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._socket: Optional[ws.WebSocketClient] = None
        self._state = "idle"
        self._state_lock = threading.Lock()
        self._listeners: List[Callable[[str, str], None]] = []
        self._outbox: List[str] = []
        self._outbox_lock = threading.Lock()
        self._tee_installed = False
        self._orig_stdout: Any = None
        self._orig_stderr: Any = None
        self._device = ""
        self.synced_version: Optional[str] = None
        self.synced_once = threading.Event()

    # -- state -----------------------------------------------------------

    @property
    def state(self) -> str:
        """``"idle"``, ``"connecting"``, ``"connected"``, ``"syncing"``, or ``"disconnected"``."""
        with self._state_lock:
            return self._state

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
        # Native modules expect the main thread; ``start`` runs there (the
        # bootstrap or a tap handler), the client thread never does.
        self._device = _device_name()
        self._install_tee()
        self._thread = threading.Thread(target=self._run, name="pn-dev-client", daemon=True)
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
        self._remove_tee()
        self._set_state("idle")

    def _run(self) -> None:
        attempt = 0
        while not self._stop.is_set():
            self._set_state("connecting", self.url)
            try:
                self._session()
                attempt = 0
            except (OSError, ws.WebSocketError) as exc:
                detail = f"{type(exc).__name__}: {exc}"
                self._set_state("disconnected", detail)
                if attempt == 0:
                    self._log(f"[pn dev] cannot reach {self.url} ({detail}); retrying")
            except Exception as exc:
                self._set_state("disconnected", repr(exc))
                self._log(f"[pn dev] client error: {exc!r}")
                traceback.print_exc(file=self._local_stderr())
            if self._stop.is_set():
                break
            delay = _RECONNECT_DELAYS[min(attempt, len(_RECONNECT_DELAYS) - 1)]
            attempt += 1
            self._stop.wait(delay)

    def _session(self) -> None:
        client = ws.WebSocketClient(self.url, timeout=1.0)
        client.connect()
        self._socket = client
        try:
            client.send_text(json.dumps(self._hello()))
            self._set_state("connected", self.url)
            self._flush_outbox()
            while not self._stop.is_set():
                try:
                    text = client.recv()
                except socket.timeout:
                    self._flush_outbox()
                    continue
                if text is None:
                    break
                self._flush_outbox()
                try:
                    message = json.loads(text)
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self._handle(message)
        finally:
            self._socket = None
            try:
                client.close()
            except Exception:
                pass
            if not self._stop.is_set():
                self._set_state("disconnected", "connection closed")

    # -- protocol --------------------------------------------------------

    def _hello(self) -> Dict[str, Any]:
        from .platform import Platform

        self._seed_overlay_from_bundle()
        return {
            "type": "hello",
            "platform": Platform.OS,
            "device": self._device,
            "app": self.entry_module,
            "files": self._overlay_manifest(),
        }

    def _seed_overlay_from_bundle(self) -> None:
        """Copy the bundled sources into an empty overlay before the first ``hello``.

        The overlay must be a complete tree (a partial ``app/`` without
        ``__init__.py`` would lose to the bundled package on ``sys.path``),
        so the first sync used to download every file and reload every
        module even when the build was made from the very sources the
        server holds. Seeding from the bundle lets the manifest report
        what the app already runs; the server then sends only real
        differences, and an up-to-date build connects without a reload.
        """
        top = self.entry_module.split(".")[0]
        if not top or self._overlay_has_files(top):
            return
        root = _bundled_package_root(top, exclude=self.overlay)
        if root is None:
            self._log(f"[pn dev] bundled sources for '{top}' not found; the server will send everything")
            return
        seeded = 0

        def copy_tree(node: Any, rel: str) -> None:
            nonlocal seeded
            try:
                children = list(node.iterdir())
            except Exception as exc:
                self._log(f"[pn dev] could not list bundled {rel}: {exc}")
                return
            for child in children:
                child_rel = f"{rel}/{child.name}"
                if child.is_dir():
                    if child.name != "__pycache__":
                        copy_tree(child, child_rel)
                    continue
                if not is_synced_file(child_rel):
                    continue
                target = os.path.join(self.overlay, *child_rel.split("/"))
                try:
                    data = child.read_bytes()
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as handle:
                        handle.write(data)
                    seeded += 1
                except Exception as exc:
                    self._log(f"[pn dev] could not seed {child_rel}: {exc}")

        copy_tree(root, top)
        self._log(f"[pn dev] seeded the overlay with {seeded} bundled file(s) from {root}")

    def _overlay_has_files(self, top: str) -> bool:
        """Whether the overlay already holds sources for ``top``.

        ``configure_dev_environment`` pre-creates the (empty) package
        directory, so the directory's existence says nothing; byte-code
        caches don't count either.
        """
        for dirpath, dirnames, filenames in os.walk(os.path.join(self.overlay, top)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if filenames:
                return True
        return False

    def _overlay_manifest(self) -> Dict[str, str]:
        files: Dict[str, str] = {}
        base = self.overlay
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, base).replace(os.sep, "/")
                if rel == _SAVED_URL_FILE or not is_synced_file(rel):
                    continue
                try:
                    with open(full, "rb") as handle:
                        files[rel] = hashlib.sha256(handle.read()).hexdigest()
                except OSError:
                    continue
        return files

    def _handle(self, message: Dict[str, Any]) -> None:
        kind = message.get("type")
        if kind not in ("sync", "update"):
            return
        self._set_state("syncing", str(message.get("version") or ""))
        files = message.get("files") or []
        removed = message.get("removed") or []
        written: List[str] = []
        for entry in files:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "")
            if not path or not self._safe_relpath(path):
                continue
            data = _decode_content(entry)
            if data is None:
                continue
            target = os.path.join(self.overlay, *path.split("/"))
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as handle:
                    handle.write(data)
                written.append(path)
            except OSError as exc:
                self._log(f"[pn dev] could not write {path}: {exc}")
        for path in removed:
            rel = str(path)
            if not self._safe_relpath(rel):
                continue
            try:
                os.remove(os.path.join(self.overlay, *rel.split("/")))
            except OSError:
                pass
            written.append(rel)
        version = str(message.get("version") or "")
        self.synced_version = version
        self.synced_once.set()
        _save_server_url(self.overlay, self.url)
        self._set_state("connected", version)
        if not written:
            # The app already runs these exact sources (a fresh build, or an
            # overlay from the last session): nothing to reload.
            return
        self._log(f"[pn dev] synced {len(written)} file(s) from {self.url}")
        modules = modules_for_paths(written)
        if modules:
            self._schedule_reload(modules, version)

    def _schedule_reload(self, modules: List[str], version: str) -> None:
        from .runtime import call_on_main_thread

        def _apply() -> None:
            from .hot_reload import apply_reload

            result = apply_reload(modules)
            if result.mode == "error":
                self.send({"type": "error", "phase": "hot reload", "text": result.error or "unknown error"})
            elif result.mode != "none":
                self.send(
                    {"type": "reloaded", "version": version, "mode": result.mode, "modules": result.reloaded or modules}
                )

        call_on_main_thread(_apply)

    def _safe_relpath(self, rel: str) -> bool:
        parts = rel.split("/")
        return bool(parts) and all(part and part not in (".", "..") for part in parts)

    # -- outbound --------------------------------------------------------

    def send(self, message: Dict[str, Any]) -> None:
        """Queue a message to the server (dropped when the outbox overflows offline)."""
        text = json.dumps(message)
        with self._outbox_lock:
            if len(self._outbox) > 500:
                del self._outbox[:100]
            self._outbox.append(text)
        sock = self._socket
        if sock is not None and threading.current_thread() is self._thread:
            self._flush_outbox()

    def _flush_outbox(self) -> None:
        sock = self._socket
        if sock is None:
            return
        while True:
            with self._outbox_lock:
                if not self._outbox:
                    return
                text = self._outbox.pop(0)
            try:
                sock.send_text(text)
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
    search = [p for p in sys.path if p and os.path.abspath(p) != excluded]
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
    from .hot_reload import configure_dev_environment, overlay_root

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
    return client


def stop() -> None:
    """Stop the process-wide dev client."""
    global _current
    with _lock:
        client, _current = _current, None
    if client is not None:
        client.stop()


def start_if_configured(entry_module: Optional[str] = None) -> Optional[DevClient]:
    """Start the dev client when the build points at a server.

    Called by ``bootstrap.start(dev=True)``. The URL comes from
    ``PN_DEV_SERVER`` (baked in by ``pn run``) or, for ``--dev-client``
    builds, from the URL saved by a previous connection. Returns the
    client, or ``None`` when nothing is configured.
    """
    from .hot_reload import overlay_root

    root = overlay_root()
    if root is None:
        return None
    url = os.environ.get(SERVER_URL_ENV) or saved_server_url(root)
    if not url:
        return None
    entry = entry_module or os.environ.get("PN_ENTRY_MODULE") or "app.main"
    try:
        return start(url, root, entry_module=entry)
    except Exception as exc:
        print(f"[pn dev] could not start the dev client: {exc!r}", file=sys.stderr)
        return None


# ======================================================================
# Connect screen (dev-client builds)
# ======================================================================


def _connect_screen() -> Any:
    from . import components as c
    from .component import component
    from .hooks import use_effect, use_state

    @component
    def ConnectScreen() -> Any:
        client = current()
        initial = client.url if client is not None else (saved_server_url() or "")
        url, set_url = use_state(initial.replace("/ws?role=client", "") if initial else "")
        status, set_status = use_state(client.state if client is not None else "idle")
        detail, set_detail = use_state("")

        def _subscribe() -> Optional[Callable[[], None]]:
            live = current()
            if live is None:
                return None

            def _on_state(state: str, info: str) -> None:
                from .runtime import call_on_main_thread

                def _update() -> None:
                    set_status(state)
                    set_detail(info)

                call_on_main_thread(_update)

            return live.add_listener(_on_state)

        use_effect(_subscribe, [client])

        def _connect() -> None:
            try:
                normalized = normalize_server_url(url)
            except ValueError as exc:
                set_status("error")
                set_detail(str(exc))
                return
            start(normalized)
            set_status("connecting")
            set_detail(normalized)

        lan_hint = "Run `pn start` on your computer and enter its address (for example 192.168.1.20:8765)."
        colors = {
            "idle": "#8E8E93",
            "connecting": "#FF9F0A",
            "connected": "#30D158",
            "syncing": "#0A84FF",
            "disconnected": "#FF453A",
            "error": "#FF453A",
        }
        return c.Column(
            c.Column(
                c.Text("PythonNative", style={"font_size": 30, "bold": True, "color": "#FFFFFF"}),
                c.Text("Dev client", style={"font_size": 17, "color": "#8E8E93"}),
                style={"spacing": 4, "padding_top": 72},
            ),
            c.Column(
                c.Text("Dev server address", style={"font_size": 13, "color": "#8E8E93"}),
                c.TextInput(
                    value=url,
                    on_change=set_url,
                    placeholder="192.168.1.20:8765",
                    auto_correct=False,
                    auto_capitalize="none",
                    keyboard_type="url",
                    style={
                        "background_color": "#1C1C1E",
                        "color": "#FFFFFF",
                        "padding": 12,
                        "border_radius": 10,
                        "font_size": 16,
                    },
                ),
                c.Button(
                    "Connect",
                    on_press=_connect,
                    style={"background_color": "#0A84FF", "color": "#FFFFFF", "padding": 12, "border_radius": 10},
                ),
                style={"spacing": 8, "align_items": "stretch"},
            ),
            c.Column(
                c.Row(
                    c.View(
                        style={"width": 10, "height": 10, "border_radius": 5, "background_color": colors.get(status)}
                    ),
                    c.Text(status, style={"color": "#FFFFFF", "font_size": 15}),
                    style={"spacing": 8, "align_items": "center"},
                ),
                c.Text(detail, style={"color": "#8E8E93", "font_size": 12}),
                style={"spacing": 4},
            ),
            c.Text(lan_hint, style={"color": "#636366", "font_size": 12}),
            style={"flex": 1, "padding": 24, "spacing": 28, "background_color": "#000000"},
        )

    return ConnectScreen


class _LazyConnectScreen:
    """Import-light proxy so ``from pythonnative.devclient import ConnectScreen`` stays cheap."""

    _component: Any = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if _LazyConnectScreen._component is None:
            _LazyConnectScreen._component = _connect_screen()
        return _LazyConnectScreen._component(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if _LazyConnectScreen._component is None:
            _LazyConnectScreen._component = _connect_screen()
        return getattr(_LazyConnectScreen._component, name)


ConnectScreen: Any = _LazyConnectScreen()
"""Root component of ``--dev-client`` builds until the first sync arrives."""


def placeholder_main_source() -> str:
    """Source of the ``app/main.py`` staged into ``--dev-client`` builds."""
    return (
        '"""Placeholder entry module for a PythonNative dev-client build.\n\n'
        "The real app arrives from the dev server and shadows this file.\n"
        '"""\n\n'
        "from pythonnative.devclient import ConnectScreen as App\n\n"
        '__all__ = ["App"]\n'
    )
