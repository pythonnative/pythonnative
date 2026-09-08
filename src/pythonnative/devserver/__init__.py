"""The PythonNative dev server: one process that serves every dev client.

``pn start`` (and ``pn preview``, which is ``pn start`` plus a browser
tab) runs a [`DevServer`][pythonnative.devserver.DevServer]. It watches
the project's ``app/`` directory, keeps a content-addressed manifest of
the sources, and speaks a small JSON protocol over WebSocket to two
kinds of peers:

- **Dev clients**: debug builds of the app running on a simulator,
  emulator, or physical device. They sync sources into an on-device
  overlay, Fast Refresh when files change, and stream their logs and
  errors back to the terminal. See ``pythonnative.devclient``.
- **The browser preview**: a page served by this server that renders
  the app through the bridge protocol, exactly as the Swift and Kotlin
  runtimes do. See ``pythonnative.bridge.web``.

Everything here is standard library only (``asyncio`` streams plus a
hand-rolled RFC 6455 implementation in ``pythonnative.devserver.ws``)
so the same
code also runs inside the embedded interpreter on device.
"""

from .server import DEFAULT_PORT, DevServer, ServerInfo, lan_addresses
from .watcher import FileWatcher, SourceSnapshot, snapshot_sources

__all__ = [
    "DEFAULT_PORT",
    "DevServer",
    "FileWatcher",
    "ServerInfo",
    "SourceSnapshot",
    "lan_addresses",
    "snapshot_sources",
]
