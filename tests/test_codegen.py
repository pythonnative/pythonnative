"""Generated native contracts match a clean Python interpreter."""

import runpy
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest

from pythonnative.sdk.native_types import NativeTypes, quoted


def test_checked_native_contracts_match_python_definitions(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import pythonnative; from pythonnative.sdk.codegen import generate; " "import sys; generate(sys.argv[1])",
            str(tmp_path),
        ],
        check=True,
    )
    root = Path(__file__).parents[1] / "src/pythonnative/native"
    for extension, folder in (
        ("swift", root / "ios/Sources/PythonNativeKit/Generated"),
        ("kt", root / "android/src/main/java/com/pythonnative/generated"),
    ):
        for name in ("PNContracts", "NativeProps", "NativeModules", "NativeValues"):
            assert (tmp_path / f"{name}.{extension}").read_bytes() == (folder / f"{name}.{extension}").read_bytes()
    for name in ("components.py", "modules.py"):
        compile((tmp_path / name).read_text(), str(tmp_path / name), "exec")


def test_generated_literals_preserve_interpolation_and_control_characters() -> None:
    value = '$total "quoted" \\path\n\x00\b'
    assert quoted(value) == r'"$total \"quoted\" \\path\n\u{0}\u{8}"'
    assert quoted(value, kotlin=True) == r'"\$total \"quoted\" \\path\n\u0000\u0008"'
    types = NativeTypes()
    types.types({"enum": ["$total", "\x00"]}, "EscapedLiteral")
    assert r'"\$total"' in "\n".join(types.kotlin)
    assert r'"\u{0}"' in "\n".join(types.swift)


def test_checked_native_record_fixtures_match_python_annotations() -> None:
    fixtures = runpy.run_path("scripts/generate-native-contracts.py")["record_fixtures"]()
    for path, expected in fixtures.items():
        assert path.read_text() == expected


def test_codegen_escapes_kotlin_literals_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pythonnative.sdk.codegen import generate
    from pythonnative.sdk.schema import COMPONENTS, ComponentSchema
    from pythonnative.sdk.types import type_schema

    monkeypatch.setitem(
        COMPONENTS, "LiteralFixture", ComponentSchema("LiteralFixture", {"choice": type_schema(Literal["$total"])})
    )
    generate(tmp_path)
    kotlin = (tmp_path / "NativeValues.kt").read_text()
    assert r'"\$total"' in kotlin
    assert r'"\\$total"' not in kotlin
    assert (
        (tmp_path / "modules.py")
        .read_text()
        .startswith('"""Generated Python interfaces. Regenerate from the declarations."""\n\n')
    )
