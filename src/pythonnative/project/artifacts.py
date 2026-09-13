"""Inspect packaged release artifacts before exporting or distributing them."""

from __future__ import annotations

import io
import plistlib
import struct
import zipfile
from pathlib import Path
from typing import Any


class ArtifactError(ValueError):
    """An artifact is missing required metadata or contains incompatible binaries."""


def elf_alignment(data: bytes, name: str) -> None:
    """Require 16 KB aligned LOAD segments in a packaged 64-bit ELF library."""
    try:
        if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] not in (1, 2):
            raise ArtifactError(f"{name}: expected a 64-bit ELF library")
        endian = "<" if data[5] == 1 else ">"
        offset = struct.unpack_from(endian + "Q", data, 32)[0]
        size, count = struct.unpack_from(endian + "HH", data, 54)
        if size < 56 or not count or offset + size * count > len(data):
            raise ArtifactError(f"{name}: invalid ELF program headers")
        loads = 0
        for index in range(count):
            kind, _, file_offset, address, _, _, _, alignment = struct.unpack_from(
                endian + "IIQQQQQQ", data, offset + index * size
            )
            if kind == 1:
                loads += 1
                if alignment < 16384 or alignment & (alignment - 1) or (address - file_offset) % 16384:
                    raise ArtifactError(
                        f"{name}: LOAD segment isn't 16 KB aligned; rebuild this dependency with NDK 28+"
                    )
        if not loads:
            raise ArtifactError(f"{name}: no ELF LOAD segments")
    except (IndexError, struct.error) as exc:
        raise ArtifactError(f"{name}: truncated ELF library") from exc


def _proto(data: bytes) -> dict[int, Any]:
    """Read the scalar/message fields needed from bundletool's config.proto."""
    offset = 0

    def varint() -> int:
        nonlocal offset
        result = 0
        for shift in range(0, 70, 7):
            if offset >= len(data):
                raise ArtifactError("Truncated BundleConfig.pb")
            value = data[offset]
            offset += 1
            result |= (value & 127) << shift
            if not value & 128:
                return result
        raise ArtifactError("Invalid BundleConfig.pb varint")

    fields: dict[int, Any] = {}
    value: Any
    while offset < len(data):
        tag = varint()
        if tag >> 3 == 0:
            raise ArtifactError("Invalid BundleConfig.pb tag")
        wire = tag & 7
        if wire == 0:
            value = varint()
        elif wire in (1, 2, 5):
            length = varint() if wire == 2 else (8 if wire == 1 else 4)
            if offset + length > len(data):
                raise ArtifactError("Truncated BundleConfig.pb field")
            value = data[offset : offset + length]
            offset += length
        else:
            raise ArtifactError("Unsupported BundleConfig.pb wire type")
        fields[tag >> 3] = value
    return fields


def android(path: Path) -> int:
    """Check every native ELF, APK zip alignment, and AAB split alignment.

    Includes native extensions inside Chaquopy's nested ZIP assets. Returns the
    number of libraries inspected; malformed or incompatible artifacts raise.
    """
    checked = 0
    try:
        with zipfile.ZipFile(path) as archive, path.open("rb") as raw:
            for entry in archive.infolist():
                if entry.filename.endswith(".so"):
                    elf_alignment(archive.read(entry), f"{path.name}:{entry.filename}")
                    checked += 1
                    if path.suffix == ".apk" and entry.compress_type == zipfile.ZIP_STORED:
                        raw.seek(entry.header_offset + 26)
                        name_length, extra_length = struct.unpack("<HH", raw.read(4))
                        start = entry.header_offset + 30 + name_length + extra_length
                        if start % 16384:
                            raise ArtifactError(f"{entry.filename}: APK library isn't 16 KB zip aligned")
                elif entry.filename.endswith((".zip", ".imy")):
                    payload = archive.read(entry)
                    if not zipfile.is_zipfile(io.BytesIO(payload)):
                        continue
                    with zipfile.ZipFile(io.BytesIO(payload)) as nested:
                        for library in nested.namelist():
                            if library.endswith(".so"):
                                elf_alignment(nested.read(library), f"{entry.filename}:{library}")
                                checked += 1
            if path.suffix == ".aab":
                # BundleConfig.optimizations.uncompress_native_libraries:
                # enabled=1; alignment=2 (16 KB) or 3 (64 KB).
                config = _proto(archive.read("BundleConfig.pb"))
                optimizations = _proto(config.get(2, b""))
                native = _proto(optimizations.get(2, b""))
                if native.get(1) and native.get(2, 0) not in (2, 3):
                    raise ArtifactError(f"{path.name}: generated APKs don't request 16 KB library alignment")
    except (OSError, zipfile.BadZipFile, KeyError, struct.error, TypeError) as exc:
        raise ArtifactError(f"Cannot inspect {path}: {exc}") from exc
    return checked


def privacy_manifest(path: Path) -> dict[str, Any]:
    """Parse and structurally validate an Apple privacy manifest without guessing app behavior."""
    try:
        value = plistlib.loads(path.read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        raise ArtifactError(f"Invalid privacy manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactError(f"{path}: privacy manifest must be a dictionary")
    if "NSPrivacyTracking" in value and type(value["NSPrivacyTracking"]) is not bool:
        raise ArtifactError(f"{path}: NSPrivacyTracking must be a boolean")
    for key in ("NSPrivacyTrackingDomains", "NSPrivacyCollectedDataTypes", "NSPrivacyAccessedAPITypes"):
        if key in value and not isinstance(value[key], list):
            raise ArtifactError(f"{path}: {key} must be an array")
    for entry in value.get("NSPrivacyAccessedAPITypes", []):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("NSPrivacyAccessedAPIType"), str)
            or not isinstance(entry.get("NSPrivacyAccessedAPITypeReasons"), list)
            or not entry["NSPrivacyAccessedAPITypeReasons"]
            or not all(isinstance(reason, str) and reason for reason in entry["NSPrivacyAccessedAPITypeReasons"])
        ):
            raise ArtifactError(f"{path}: each accessed API needs a category and nonempty reasons")
    return value


def ios_archive(path: Path) -> int:
    """Verify app and bundled privacy manifests before archive export or upload."""
    apps = list((path / "Products/Applications").glob("*.app"))
    if not apps:
        raise ArtifactError(f"{path}: archive contains no application")
    count = 0
    for app in apps:
        if not (app / "PrivacyInfo.xcprivacy").is_file():
            raise ArtifactError(f"{app.name}: app privacy manifest is missing")
        for manifest in app.rglob("PrivacyInfo.xcprivacy"):
            privacy_manifest(manifest)
            count += 1
        runtime_manifests = list(app.glob("*PythonNativeKit*.bundle/PrivacyInfo.xcprivacy"))
        if not runtime_manifests:
            raise ArtifactError(f"{app.name}: PythonNativeKit privacy resource bundle is missing")
    return count
