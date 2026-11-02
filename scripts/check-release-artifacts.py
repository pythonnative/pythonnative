#!/usr/bin/env python3
"""Verify a capability-free app doesn't reference privacy-sensitive APIs.

RFC 0008's promise: compile only the capabilities an app asks for. This builds a new
project's native code in the release configuration and looks for the symbols of the
frameworks and permissions that would make a store ask why:

    python scripts/check-release-artifacts.py ios
    python scripts/check-release-artifacts.py android

Exit code is 0 when the app is clean.
"""

from __future__ import annotations

import argparse
import plistlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from pythonnative.project.builder import Builder
from pythonnative.project.config import AppConfig, render_default_toml

# Linked frameworks that come with an Info.plist usage-string requirement.
SENSITIVE_IOS_FRAMEWORKS = ("AVFoundation", "Contacts", "CoreLocation", "CoreMotion", "LocalAuthentication", "Photos")
SENSITIVE_IOS_KEYS = ("NSCameraUsageDescription", "NSLocationWhenInUseUsageDescription", "NSMicrophoneUsageDescription")
SENSITIVE_ANDROID_PERMISSIONS = (
    "android.permission.CAMERA",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_CONTACTS",
)


def project(root: Path) -> AppConfig:
    """Write a one-screen project that enables nothing."""
    (root / "app").mkdir()
    (root / "app" / "__init__.py").write_text("")
    (root / "app" / "main.py").write_text(
        "import pythonnative as pn\n\n\n@pn.component\ndef App() -> pn.Node:\n    return pn.Text('Clean')\n"
    )
    (root / "pythonnative.toml").write_text(render_default_toml(name="clean", app_id="dev.pythonnative.clean"))
    return AppConfig.load(root)


def check_ios(root: Path) -> list[str]:
    """Archive the project and report sensitive usage keys and linked frameworks."""
    builder = Builder(project(root), log=print)
    prepared = builder.prepare("ios", release=True, ios_sdks=("iphoneos",), allow_unsigned=True)
    artifacts = builder.build_ios_archive(prepared, allow_unsigned=True)
    archive = artifacts.paths[0]
    app = next((archive / "Products" / "Applications").glob("*.app"))
    with open(app / "Info.plist", "rb") as handle:
        info = plistlib.load(handle)
    problems = [f"Info.plist declares {key}" for key in SENSITIVE_IOS_KEYS if key in info]
    linked = subprocess.run(["otool", "-L", str(app / app.stem)], capture_output=True, text=True, check=True).stdout
    kit = app / "Frameworks" / "PythonNativeKit.framework" / "PythonNativeKit"
    if kit.is_file():
        linked += subprocess.run(["otool", "-L", str(kit)], capture_output=True, text=True, check=True).stdout
    return problems + [f"links {name}.framework" for name in SENSITIVE_IOS_FRAMEWORKS if f"{name}.framework" in linked]


def check_android(root: Path) -> list[str]:
    """Build the APK and report sensitive permissions in its manifest."""
    builder = Builder(project(root), log=print)
    prepared = builder.prepare("android", release=True, allow_unsigned=True)
    artifacts = builder.build_android(prepared, allow_unsigned=True)
    apk = next(path for path in artifacts.paths if path.suffix == ".apk")
    with zipfile.ZipFile(apk) as archive:
        manifest = archive.read("AndroidManifest.xml")
    # The binary XML format stores strings as UTF-16.
    return [f"declares {name}" for name in SENSITIVE_ANDROID_PERMISSIONS if name.encode("utf-16-le") in manifest]


def main() -> int:
    """Build the clean project for one platform and report what it references."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("platform", choices=["ios", "android"])
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pn-clean-") as scratch:
        problems = check_ios(Path(scratch)) if args.platform == "ios" else check_android(Path(scratch))
    for problem in problems:
        print(f"ERROR: a project using no capabilities {problem}", file=sys.stderr)
    if not problems:
        print(f"{args.platform}: a project using no capabilities references no sensitive API.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
