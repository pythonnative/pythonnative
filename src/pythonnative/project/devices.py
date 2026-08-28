"""Device and simulator discovery for ``pn devices`` / ``pn run --device``.

Enumerates the three kinds of targets a PythonNative app can run on:

- **Android devices and emulators** via ``adb devices -l``.
- **iOS Simulators** via ``xcrun simctl list devices --json``.
- **Physical iOS devices** via ``xcrun devicectl list devices`` (Xcode
  15+; earlier Xcodes simply report no physical devices).

The shell-outs are isolated in ``list_*`` functions; the parsers are
pure functions over captured text/JSON so they can be unit tested
without any toolchain installed.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "Device",
    "list_devices",
    "list_android_devices",
    "list_ios_simulators",
    "list_ios_physical_devices",
    "find_device",
    "parse_adb_devices",
    "parse_simctl_devices",
    "parse_devicectl_devices",
]


@dataclass
class Device:
    """One runnable target.

    Attributes:
        platform: ``"android"`` or ``"ios"``.
        kind: ``"device"``, ``"emulator"``, or ``"simulator"``.
        identifier: The stable id used to target the device (adb
            serial, simulator UDID, or devicectl identifier).
        name: Human-readable model or simulator name.
        os_version: OS version string when known.
        state: ``"booted"``, ``"connected"``, ``"shutdown"``, or
            ``"offline"``.
    """

    platform: str
    kind: str
    identifier: str
    name: str
    os_version: str = ""
    state: str = ""

    @property
    def is_ready(self) -> bool:
        """Whether the target can be used right now (or booted on demand)."""
        if self.kind == "simulator":
            return self.state in ("booted", "shutdown")
        return self.state in ("booted", "connected")

    def format(self) -> str:
        """Return one aligned listing row for the CLI."""
        os_part = f" ({self.os_version})" if self.os_version else ""
        return f"  {self.identifier:<40} {self.kind:<10} {self.state:<10} {self.name}{os_part}"


# ======================================================================
# Android (adb)
# ======================================================================


def parse_adb_devices(output: str) -> List[Device]:
    """Parse ``adb devices -l`` output into devices.

    Args:
        output: Raw stdout from ``adb devices -l``.

    Returns:
        Android devices and emulators (offline entries included, with
        ``state="offline"``).
    """
    devices: List[Device] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if state == "unauthorized":
            state = "offline"
        elif state == "device":
            state = "connected"
        model = ""
        for token in parts[2:]:
            if token.startswith("model:"):
                model = token[len("model:") :].replace("_", " ")
        kind = "emulator" if serial.startswith("emulator-") else "device"
        devices.append(
            Device(
                platform="android",
                kind=kind,
                identifier=serial,
                name=model or serial,
                state=state if state in ("connected", "offline") else "offline",
            )
        )
    return devices


def list_android_devices() -> List[Device]:
    """Return connected Android devices/emulators (empty without adb)."""
    try:
        result = subprocess.run(["adb", "devices", "-l"], check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return []
    return parse_adb_devices(result.stdout or "")


# ======================================================================
# iOS Simulators (simctl)
# ======================================================================

_RUNTIME_RE = re.compile(r"iOS[.-](\d+)[.-](\d+)")


def parse_simctl_devices(data: Dict[str, Any]) -> List[Device]:
    """Parse ``simctl list devices --json`` payload into devices.

    Args:
        data: The decoded JSON payload.

    Returns:
        Available iOS Simulators (unavailable ones are skipped).
    """
    devices: List[Device] = []
    for runtime, entries in (data.get("devices") or {}).items():
        match = _RUNTIME_RE.search(runtime)
        os_version = f"iOS {match.group(1)}.{match.group(2)}" if match else ""
        if "iOS" not in runtime:
            continue
        for entry in entries or []:
            if not entry.get("isAvailable") or not entry.get("udid"):
                continue
            devices.append(
                Device(
                    platform="ios",
                    kind="simulator",
                    identifier=str(entry["udid"]),
                    name=str(entry.get("name") or entry["udid"]),
                    os_version=os_version,
                    state="booted" if entry.get("state") == "Booted" else "shutdown",
                )
            )
    return devices


def list_ios_simulators() -> List[Device]:
    """Return available iOS Simulators (empty without Xcode)."""
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "available", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return []
    return parse_simctl_devices(data)


# ======================================================================
# Physical iOS devices (devicectl)
# ======================================================================


def parse_devicectl_devices(data: Dict[str, Any]) -> List[Device]:
    """Parse ``devicectl list devices --json-output`` payload into devices.

    Args:
        data: The decoded JSON payload.

    Returns:
        Physical iOS devices.
    """
    devices: List[Device] = []
    for entry in (data.get("result") or {}).get("devices") or []:
        props = entry.get("deviceProperties") or {}
        hardware = entry.get("hardwareProperties") or {}
        connection = entry.get("connectionProperties") or {}
        identifier = str(entry.get("identifier") or "")
        if not identifier:
            continue
        state = "connected" if connection.get("tunnelState") in ("connected", "available") else "offline"
        os_version = props.get("osVersionNumber") or ""
        devices.append(
            Device(
                platform="ios",
                kind="device",
                identifier=identifier,
                name=str(props.get("name") or hardware.get("marketingName") or identifier),
                os_version=f"iOS {os_version}" if os_version else "",
                state=state,
            )
        )
    return devices


def list_ios_physical_devices() -> List[Device]:
    """Return physical iOS devices (empty without Xcode 15+)."""
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "devices.json"
        try:
            subprocess.run(
                ["xcrun", "devicectl", "list", "devices", "--json-output", str(out_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if not out_path.is_file():
            return []
        try:
            data = json.loads(out_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return parse_devicectl_devices(data)


# ======================================================================
# Aggregation / selection
# ======================================================================


def list_devices(platform: Optional[str] = None) -> List[Device]:
    """Return all known targets, optionally restricted to one platform.

    Args:
        platform: ``"android"``, ``"ios"``, or ``None`` for both.

    Returns:
        Devices ordered: Android first, then physical iOS devices, then
        simulators (booted simulators before shutdown ones).
    """
    devices: List[Device] = []
    if platform in (None, "android"):
        devices.extend(list_android_devices())
    if platform in (None, "ios"):
        devices.extend(list_ios_physical_devices())
        simulators = list_ios_simulators()
        simulators.sort(key=lambda dev: (dev.state != "booted", dev.name))
        devices.extend(simulators)
    return devices


def find_device(devices: List[Device], query: str) -> Optional[Device]:
    """Resolve ``query`` against ``devices`` (exact id, then name match).

    Args:
        devices: Candidate devices.
        query: An identifier, exact name, or case-insensitive name
            substring.

    Returns:
        The best match, or ``None``. Ready devices win ties.
    """
    ready_first = sorted(devices, key=lambda dev: not dev.is_ready)
    for device in ready_first:
        if device.identifier == query:
            return device
    lowered = query.lower()
    for device in ready_first:
        if device.name.lower() == lowered:
            return device
    for device in ready_first:
        if lowered in device.name.lower():
            return device
    return None
