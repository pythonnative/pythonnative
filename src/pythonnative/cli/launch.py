"""Device-facing steps shared by ``pn run``, ``pn go``, and ``pn start``'s keys.

These shell out to ``xcrun simctl``, ``xcrun devicectl``, ``adb``, and the
Android emulator, so they're exercised on real toolchains rather than in
unit tests (which cover the pure helpers: links and URLs).
"""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..project import devices as devices_mod

Logger = Callable[[str], None]

__all__ = [
    "boot_android_emulator",
    "booted_ios_udid",
    "ensure_android_device",
    "install_android",
    "install_ios_simulator",
    "open_link_android",
    "launch_ios_device",
    "launch_ios_simulator",
    "select_ios_simulator",
    "server_connect_url",
]


# ======================================================================
# URLs
# ======================================================================


def server_connect_url(platform: str, device: Optional[devices_mod.Device], port: int, token: str) -> str:
    """The server URL a launched dev client should use to reach ``pn start``.

    Simulators share the host's loopback. Android emulators and USB
    devices reach it through ``adb reverse`` (set up by the caller), so
    ``localhost`` works for every Android target. A physical iOS device is
    on the LAN, so it gets the first LAN address. The URL carries the dev
    ``token`` the server requires.
    """
    from ..devserver.auth import with_token

    host = "localhost"
    if platform == "ios" and device is not None and device.kind == "device":
        from ..devserver import lan_addresses

        host = next(iter(lan_addresses()), host)
    return with_token(f"http://{host}:{port}/", token)


# ======================================================================
# iOS
# ======================================================================


def booted_ios_udid() -> Optional[str]:
    """A booted iOS Simulator's UDID, or ``None``."""
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "booted", "--json"], check=False, capture_output=True, text=True
        )
    except FileNotFoundError:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    for devices in (data.get("devices") or {}).values():
        for device in devices or []:
            if device.get("state") == "Booted" and device.get("udid"):
                return str(device["udid"])
    return None


def select_ios_simulator() -> Optional[str]:
    """A simulator UDID to target: the booted one, else the newest available iPhone."""
    booted = booted_ios_udid()
    if booted:
        return booted
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "available", "--json"], check=False, capture_output=True, text=True
        )
    except FileNotFoundError:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    runtimes: List[tuple] = []
    for runtime, entries in (data.get("devices") or {}).items():
        version = tuple(int(part) for part in runtime.rsplit("iOS-", 1)[-1].split("-") if part.isdigit())
        for entry in entries or []:
            if entry.get("isAvailable") and str(entry.get("name") or "").lower().startswith("iphone"):
                runtimes.append((version, str(entry.get("name")), str(entry.get("udid"))))
    if not runtimes:
        return None
    runtimes.sort(reverse=True)
    return runtimes[0][2]


def boot_ios_simulator(udid: str) -> None:
    """Boot ``udid`` (a no-op when it's booted) and bring Simulator.app forward."""
    subprocess.run(["xcrun", "simctl", "boot", udid], check=False, capture_output=True)
    subprocess.run(["open", "-a", "Simulator"], check=False, capture_output=True)
    subprocess.run(["xcrun", "simctl", "bootstatus", udid, "-b"], check=False, capture_output=True)


def install_ios_simulator(udid: str, app: Path) -> bool:
    """Install an ``.app`` on a simulator."""
    return subprocess.run(["xcrun", "simctl", "install", udid, str(app)], check=False).returncode == 0


def launch_ios_simulator(
    udid: str, bundle_id: str, link: Optional[str], *, console: bool = False
) -> "subprocess.Popen[bytes]":
    """Relaunch an app on a simulator, handing it a connect link.

    The link travels in the launch environment (``PN_CONNECT_LINK``)
    rather than through ``simctl openurl``, which makes iOS ask the user to
    confirm opening the app. With ``console``, the app's stdout and stderr
    stream to this terminal and the returned process runs until the app
    exits.
    """
    import os

    from ..devclient import LINK_ENV

    env = {**os.environ, "SIMCTL_CHILD_PYTHONUNBUFFERED": "1"}
    if link:
        env["SIMCTL_CHILD_" + LINK_ENV] = link
    command = ["xcrun", "simctl", "launch", "--terminate-running-process"]
    if console:
        command.append("--console-pty")
    return subprocess.Popen([*command, udid, bundle_id], env=env)


def launch_ios_device(identifier: str, bundle_id: str, link: Optional[str]) -> bool:
    """Relaunch an app on a physical device, handing it a connect link."""
    from ..devclient import LINK_ENV

    command = ["xcrun", "devicectl", "device", "process", "launch", "--terminate-existing"]
    if link:
        command += ["--environment-variables", json.dumps({LINK_ENV: link})]
    command += ["--device", identifier, bundle_id]
    return subprocess.run(command, check=False).returncode == 0


# ======================================================================
# Android
# ======================================================================


def _emulator_binary() -> Optional[Path]:
    from ..project.android import sdk_dir

    candidate = sdk_dir() / "emulator" / "emulator"
    return candidate if candidate.exists() else None


def list_avds() -> List[str]:
    """The Android Virtual Devices this machine has."""
    emulator = _emulator_binary()
    if emulator is None:
        return []
    result = subprocess.run([str(emulator), "-list-avds"], check=False, capture_output=True, text=True)
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip() and " " not in line.strip()]


def boot_android_emulator(log: Logger, avd: Optional[str] = None, timeout: float = 240.0) -> Optional[str]:
    """Boot an emulator and wait until Android finished booting; returns its serial."""
    emulator = _emulator_binary()
    avds = list_avds()
    name = avd or (avds[0] if avds else None)
    if emulator is None or name is None:
        log("No Android emulator to boot: create one in Android Studio's Device Manager.")
        return None
    log(f"Booting the Android emulator {name}...")
    subprocess.Popen(
        [str(emulator), "-avd", name, "-netdelay", "none", "-netspeed", "full"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for device in devices_mod.list_android_devices():
            if device.kind == "emulator" and device.is_ready:
                booted = subprocess.run(
                    ["adb", "-s", device.identifier, "shell", "getprop", "sys.boot_completed"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if booted.stdout.strip() == "1":
                    return device.identifier
        time.sleep(2.0)
    log("The emulator didn't finish booting in time.")
    return None


def ensure_android_device(device: Optional[devices_mod.Device], log: Logger) -> Optional[str]:
    """A ready Android serial: ``device``'s, the first connected one, or a freshly booted emulator."""
    if device is not None:
        return device.identifier
    ready = [d for d in devices_mod.list_android_devices() if d.is_ready]
    if ready:
        return ready[0].identifier
    return boot_android_emulator(log)


def _adb(serial: Optional[str], *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["adb", *(["-s", serial] if serial else []), *args]
    return subprocess.run(command, check=False, capture_output=capture, text=True)


def install_android(serial: Optional[str], apk: Path, package: str, log: Logger) -> bool:
    """Install an APK, replacing an installed copy signed with a different key."""
    result = _adb(serial, "install", "-r", str(apk), capture=True)
    if result.returncode == 0:
        return True
    output = (result.stdout or "") + (result.stderr or "")
    if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in output or "signatures do not match" in output:
        log(f"Replacing the installed {package}, which was signed with a different key.")
        _adb(serial, "uninstall", package, capture=True)
        return _adb(serial, "install", str(apk)).returncode == 0
    log(output.strip())
    return False


def reverse_port(serial: Optional[str], port: int) -> None:
    """Let the device reach ``localhost:port`` on this machine (``adb reverse``)."""
    _adb(serial, "reverse", f"tcp:{port}", f"tcp:{port}", capture=True)


def open_link_android(serial: Optional[str], link: str, package: str) -> bool:
    """Open a deep link in ``package`` (launching it when needed)."""
    # `adb shell` runs its arguments through the device's shell.
    command = f"am start -a android.intent.action.VIEW -d {shlex.quote(link)} {shlex.quote(package)}"
    return _adb(serial, "shell", command).returncode == 0


def stop_android_app(serial: Optional[str], package: str) -> None:
    """Force-stop ``package`` so the next link cold-starts it."""
    _adb(serial, "shell", "am", "force-stop", package, capture=True)


def describe(device: Optional[devices_mod.Device]) -> Dict[str, Any]:
    """A loggable description of a target device."""
    return device.to_dict() if device is not None else {}
