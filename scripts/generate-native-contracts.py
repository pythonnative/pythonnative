#!/usr/bin/env python3
"""Regenerate checked-in built-in contracts and the bundled iOS test fixtures."""

import shutil
import tempfile
from pathlib import Path

import pythonnative  # noqa: F401  # Install built-in schemas in a clean process.
from pythonnative.sdk.codegen import generate

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src/pythonnative/native"


def main() -> None:
    """Generate both native libraries from the same Python definitions."""
    with tempfile.TemporaryDirectory(prefix="pn-contracts-") as folder:
        generate(folder)
        for extension, destination in (
            ("swift", NATIVE / "ios/Sources/PythonNativeKit/Generated"),
            ("kt", NATIVE / "android/src/main/java/com/pythonnative/generated"),
        ):
            for name in ("PNContracts", "NativeProps", "NativeModules"):
                shutil.copyfile(Path(folder) / f"{name}.{extension}", destination / f"{name}.{extension}")
    shutil.copyfile(
        ROOT / "tests/contracts/validation.json", NATIVE / "ios/Tests/PythonNativeKitTests/Fixtures/validation.json"
    )


if __name__ == "__main__":
    main()
