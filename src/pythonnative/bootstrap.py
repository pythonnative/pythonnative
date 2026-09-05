"""Entry point the native app templates run right after Python starts.

Both templates execute one line of Python once the interpreter is up:

```python
import pythonnative.bootstrap; pythonnative.bootstrap.start()
```

[`start`][pythonnative.bootstrap.start] connects the two halves of the
bridge (installing the native -> Python callback on iOS), verifies the
protocol version, routes ``print()`` to the console on iOS, warms the
asyncio runtime, and, in debug builds, starts the dev client that syncs
sources from ``pn start``. From then on the native runtime drives
everything through ``callback("host", ...)``; see ``docs/concepts/bridge.md``.
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Any, Dict

__all__ = ["start", "status"]

_started: Dict[str, Any] = {}


def start(dev: bool = False, strict: bool = False) -> Dict[str, Any]:
    """Connect the bridge and prepare the runtime.

    Args:
        dev: Enable dev mode (RedBox, validation warnings, the dev
            client). Debug templates pass ``True``.
        strict: Re-raise the failure after recording it. The templates
            pass ``True`` so a broken bridge surfaces as a bootstrap
            error screen with the full traceback.

    Returns:
        A status dict (``{"protocol": 1, "platform": "ios"}``) that the
        template logs. Unless ``strict`` is set this never raises:
        failures are printed and reported in the dict under
        ``"error"``.
    """
    global _started
    if _started and "error" not in _started:
        return dict(_started)
    status_: Dict[str, Any] = {"platform": None, "protocol": None}
    try:
        from .utils import IS_ANDROID, IS_IOS

        status_["platform"] = "ios" if IS_IOS else "android" if IS_ANDROID else "off-device"
        if IS_IOS:
            try:
                from . import _ios_log

                _ios_log.install()
            except Exception:
                pass
        from . import bridge

        status_["protocol"] = bridge.handshake()
        dev_mode = bool(dev or os.environ.get("PN_DEV") in ("1", "true"))
        if dev_mode:
            from . import diagnostics

            diagnostics.set_dev_mode(True)
        # Create the guest loop now so the first pump request has a
        # loop to drive and effects can schedule work during mount.
        from .runtime import get_loop

        get_loop()
        # Import the view backend eagerly: on a slow device the first
        # commit shouldn't also pay for importing the reconciler.
        from .native_views import get_registry

        get_registry()
        if dev_mode:
            # Debug builds are dev clients: connect to `pn start` when
            # the build (or a remembered connection) names a server.
            from . import devclient

            client = devclient.start_if_configured()
            status_["dev_server"] = client.url if client is not None else None
    except Exception as exc:
        status_["error"] = f"{type(exc).__name__}: {exc}"
        print(f"[pn.bootstrap] start failed: {exc!r}", file=sys.stderr)
        traceback.print_exc()
        _started = status_
        if strict:
            raise
        return dict(status_)
    _started = status_
    return dict(status_)


def status() -> Dict[str, Any]:
    """Return the result of the last [`start`][pythonnative.bootstrap.start] (empty before it ran)."""
    return dict(_started)
