#!/usr/bin/env python3
"""Run the actual preview renderer in headless Chrome, with local Yoga assets."""

import functools
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from pythonnative.sdk.schema import manifest

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    """Serve the checked-in renderer and the current Python contract."""

    def do_GET(self) -> None:
        """Generate the schema route used by the production preview server."""
        if self.path == "/src/pythonnative/devserver/static/schema.js":
            payload = ("export default " + json.dumps(manifest()) + ";").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            super().do_GET()

    def log_message(self, *_args: object) -> None:
        """Keep successful asset requests out of test output."""


def stop_browser(process: subprocess.Popen, port_file: Path) -> None:
    """Finish Chrome's profile writes before its temporary directory is removed."""
    try:
        if process.poll() is None:
            try:
                port, endpoint = port_file.read_text().splitlines()[:2]
                with connect(f"ws://127.0.0.1:{port}{endpoint}", open_timeout=5, close_timeout=5) as socket:
                    socket.send(json.dumps({"id": 1, "method": "Browser.close"}))
                    socket.recv(timeout=5)
            except (OSError, ValueError, TimeoutError, WebSocketException):
                # Chrome can close the socket before acknowledging shutdown.
                # Give it time to exit before the process-group fallback.
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass  # The process-group fallback below also stops its children.
    finally:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def main() -> None:
    """Execute browser tests and propagate failures to CI."""
    chrome = os.environ.get("CHROME_BIN") or shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).is_file():
        raise SystemExit("Install Chrome or set CHROME_BIN to run renderer tests")
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="pn-browser-") as profile:
            with tempfile.TemporaryFile(mode="w+") as log:
                process = subprocess.Popen(
                    [
                        chrome,
                        "--headless",
                        "--no-sandbox",
                        "--disable-gpu",
                        "--no-first-run",
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--no-default-browser-check",
                        f"--user-data-dir={profile}",
                        "--remote-debugging-port=0",
                        "about:blank",
                    ],
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
                port_file = Path(profile) / "DevToolsActivePort"
                try:
                    deadline = time.monotonic() + 45
                    while not port_file.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.1)
                    if not port_file.exists():
                        log.seek(0)
                        raise RuntimeError("Chrome didn't start: " + log.read()[-5000:])
                    port = int(port_file.read_text().splitlines()[0])
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
                        target = next(item for item in json.load(response) if item.get("type") == "page")
                    with connect(target["webSocketDebuggerUrl"], open_timeout=5) as socket:
                        request_id = 0

                        def command(method: str, params: dict) -> dict:
                            nonlocal request_id
                            request_id += 1
                            socket.send(json.dumps({"id": request_id, "method": method, "params": params}))
                            while True:
                                message = json.loads(socket.recv(timeout=10))
                                if message.get("id") == request_id:
                                    if "error" in message:
                                        raise RuntimeError(str(message["error"]))
                                    return message.get("result", {})

                        command(
                            "Page.navigate",
                            {"url": f"http://127.0.0.1:{server.server_port}/tests/browser/renderer.html"},
                        )
                        deadline = time.monotonic() + 45
                        output = ""
                        while time.monotonic() < deadline:
                            result = command(
                                "Runtime.evaluate",
                                {"expression": "document.getElementById('result')?.outerHTML", "returnByValue": True},
                            )
                            output = result.get("result", {}).get("value", "")
                            if 'data-status="passed"' in output:
                                break
                            if 'data-status="failed"' in output:
                                raise RuntimeError(output)
                            time.sleep(0.1)
                        else:
                            raise RuntimeError(
                                "Browser tests timed out: "
                                + output
                                + str(
                                    command(
                                        "Runtime.evaluate",
                                        {"expression": "document.documentElement.outerHTML", "returnByValue": True},
                                    )
                                )
                            )
                finally:
                    stop_browser(process, port_file)
        print("Browser renderer acceptance tests passed (Chrome + Yoga WASM)")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
