"""Single-key commands for ``pn start``, like Metro's terminal UI.

When stdin is a terminal, ``pn start`` reads keys without waiting for
Enter. [`KeyCommands.handle`][pythonnative.cli.keys.KeyCommands.handle]
maps each key to an action; it's separate from the terminal handling so it
can be tested without one.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["HELP", "KeyCommands", "read_keys"]

Logger = Callable[[str], None]

HELP: List[Tuple[str, str]] = [
    ("i", "open on the iOS Simulator (in PythonNative Go when the project can run there)"),
    ("a", "open on an Android emulator or device (in PythonNative Go when possible)"),
    ("I / A", "build and run the project's own development app"),
    ("w", "open the browser preview"),
    ("j", "open DevTools"),
    ("r", "reload every connected app"),
    ("m", "open the dev menu on every connected device"),
    ("d", "show how to attach a debugger"),
    ("c", "clear the terminal"),
    ("?", "show these commands"),
    ("q", "quit"),
]

LAUNCH_CONFIG = """{
  "name": "PythonNative: Attach",
  "type": "debugpy",
  "request": "attach",
  "connect": {"host": "127.0.0.1", "port": %d},
  "justMyCode": true
}"""


class KeyCommands:
    """Turn keys into dev-server actions.

    Args:
        session: The running ``PreviewSession``.
        port: The dev server's port (passed to ``pn go`` and ``pn run``).
        log: Terminal logger.
        stop: Called by ``q``.
        spawn: Runs a ``pn`` subcommand in the background (tests replace it).
    """

    def __init__(
        self,
        session: Any,
        port: int,
        log: Logger,
        stop: Callable[[], None],
        spawn: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self.session = session
        self.port = port
        self.log = log
        self.stop = stop
        self.spawn = spawn or self._spawn
        self._running: Dict[str, subprocess.Popen[bytes]] = {}

    def help_lines(self) -> List[str]:
        """The command list, aligned."""
        return [f"  {key:<6} {text}" for key, text in HELP]

    def handle(self, key: str) -> bool:
        """Run the action for ``key``; returns ``False`` once the server should stop."""
        server = self.session.server
        if key in ("i", "a", "I", "A"):
            platform = "ios" if key.lower() == "i" else "android"
            use_go = key.islower() and self._go_compatible()
            command = ["go" if use_go else "run", platform, "--port", str(self.port)]
            if not use_go:
                command.append("--no-logs")
            what = "PythonNative Go" if use_go else "the project's development app"
            self.log(f"[pn] opening {what} on {'iOS' if platform == 'ios' else 'Android'}...")
            self.spawn(command)
        elif key == "w":
            webbrowser.open(server.info.preview_url("localhost"))
        elif key == "j":
            webbrowser.open(server.info.devtools_url("localhost"))
        elif key == "r":
            self.log("[pn] reloading every connected app")
            server.broadcast_command("reload")
        elif key == "m":
            self.log("[pn] opening the dev menu on connected devices")
            server.broadcast_command("menu")
        elif key == "d":
            self._debug_help()
        elif key == "c":
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
        elif key in ("?", "h"):
            for line in ["", "  Commands:", *self.help_lines(), ""]:
                self.log(line)
        elif key in ("q", "\x03", "\x04"):
            self.stop()
            return False
        return True

    def _go_compatible(self) -> bool:
        try:
            runtime = self.session.server.project_runtime
        except Exception:
            return True
        if not runtime.go_compatible:
            reasons = runtime.plugins + runtime.native_packages
            self.log(
                f"[pn] this project needs native code PythonNative Go doesn't have ({', '.join(reasons)}); "
                "building its development app instead"
            )
            return False
        return True

    def _debug_help(self) -> None:
        server = self.session.server
        if not server.debug_port:
            self.log("[pn] the debugger proxy is off (start with --debug-port 5678)")
            return
        target = server.hub.default_target()
        where = target.label() if target is not None else "the next app that connects"
        self.log(f"[pn] debugger: attach a Debug Adapter Protocol client to 127.0.0.1:{server.debug_port}")
        self.log(f"[pn] it debugs {where}; pick another in DevTools or with the device's dev menu")
        self.log("[pn] VS Code launch configuration (pn init writes it to .vscode/launch.json):")
        for line in (LAUNCH_CONFIG % server.debug_port).split("\n"):
            self.log("    " + line)

    def _spawn(self, args: List[str]) -> None:
        """Run ``pn <args>`` in the background, outside the preview's web environment."""
        name = " ".join(args[:2])
        previous = self._running.get(name)
        if previous is not None and previous.poll() is None:
            self.log(f"[pn] `pn {name}` is still running")
            return
        env = {key: value for key, value in os.environ.items() if key != "PN_PLATFORM"}
        process = subprocess.Popen(
            [sys.executable, "-m", "pythonnative.cli.pn", *args], env=env, stdin=subprocess.DEVNULL
        )
        self._running[name] = process


def read_keys(handle: Callable[[str], bool], stopped: threading.Event) -> None:
    """Read single keys from the terminal until ``handle`` returns ``False`` or ``stopped`` is set.

    The terminal is put in cbreak mode (keys arrive without Enter, and
    Ctrl+C still interrupts) and restored on exit.
    """
    try:
        import select
        import termios
        import tty
    except ImportError:  # Windows: no key commands.
        return
    fd = sys.stdin.fileno()
    try:
        saved = termios.tcgetattr(fd)
    except termios.error:
        return
    try:
        tty.setcbreak(fd)
        while not stopped.is_set():
            ready, _, _ = select.select([fd], [], [], 0.25)
            if not ready:
                continue
            key = os.read(fd, 1).decode("utf-8", errors="ignore")
            if key and not handle(key):
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
