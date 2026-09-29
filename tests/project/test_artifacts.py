"""Release validation inspects actual packaged bytes, including vendored wheels."""

import io
import plistlib
import struct
import zipfile
from pathlib import Path

import pytest

from pythonnative.project.artifacts import ArtifactError, android, elf_alignment, ios_archive, privacy_manifest


def elf(alignment: int = 16384) -> bytes:
    data = bytearray(120)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, 120, 120, alignment)
    return bytes(data)


def test_elf_checks_every_load_and_rejects_corruption() -> None:
    elf_alignment(elf(), "python.so")
    for payload in (elf(4096), elf(24576), elf()[:100], b"not ELF"):
        with pytest.raises(ArtifactError):
            elf_alignment(payload, "vendor.so")


def test_apk_compression_and_alignment_are_distinct_checks(tmp_path: Path) -> None:
    path = tmp_path / "app.apk"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("lib/arm64-v8a/libpython.so", elf())
    assert android(path) == 1
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("lib/arm64-v8a/libpython.so", elf())
    with pytest.raises(ArtifactError, match="zip aligned"):
        android(path)


def test_aab_alignment_and_nested_python_extensions(tmp_path: Path) -> None:
    path = tmp_path / "app.aab"
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as archive:
        archive.writestr("native/extension.so", elf())
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("base/assets/chaquopy/requirements.imy", nested.getvalue())
        archive.writestr("BundleConfig.pb", b"\x12\x06\x12\x04\x08\x01\x10\x02")
    assert android(path) == 1
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("BundleConfig.pb", b"\x12\x06\x12\x04\x08\x01\x10\x01")
    with pytest.raises(ArtifactError, match="don't request"):
        android(path)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("base/lib/arm64-v8a/vendor.so", elf(4096))
    with pytest.raises(ArtifactError, match="vendor.so"):
        android(path)


def test_ios_archive_validates_app_and_dependency_privacy_manifests(tmp_path: Path) -> None:
    app = tmp_path / "Products/Applications/Example.app"
    resource = app / "PythonNativeKit_PythonNativeKit.bundle"
    resource.mkdir(parents=True)
    with pytest.raises(ArtifactError, match="app privacy"):
        ios_archive(tmp_path)
    (app / "PrivacyInfo.xcprivacy").write_bytes(plistlib.dumps({}))
    with pytest.raises(ArtifactError, match="resource bundle"):
        ios_archive(tmp_path)
    (resource / "PrivacyInfo.xcprivacy").write_bytes(plistlib.dumps({"NSPrivacyTracking": False}))
    assert ios_archive(tmp_path) == 2
    invalid = resource / "PrivacyInfo.xcprivacy"
    invalid.write_bytes(plistlib.dumps({"NSPrivacyAccessedAPITypes": [{"NSPrivacyAccessedAPIType": "UserDefaults"}]}))
    with pytest.raises(ArtifactError, match="nonempty reasons"):
        privacy_manifest(invalid)
