"""Generated native contracts match a clean Python interpreter."""

import os
import re
import runpy
import shutil
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


def test_extension_manifests_keep_builtin_type_names(tmp_path: Path) -> None:
    # A plugin build loads extension manifests from JSON, which turns tuples
    # into lists. An extension component that redeclares View's props must
    # not rename the built-in types that hand-written native code spells.
    script = (
        "import json, sys; import pythonnative; from pythonnative.sdk import schema; "
        "from pythonnative.sdk.codegen import generate; "
        "badge = json.loads(json.dumps(schema.manifest()['components']['View'], default=str)); "
        "badge['name'] = 'AaaBadge'; "
        "schema.load_manifest({'protocol': 3, 'yoga': '3.2.1', 'components': {'AaaBadge': badge}}); "
        "generate(sys.argv[1])"
    )
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=True)
    root = Path(__file__).parents[1] / "src/pythonnative/native"
    declaration = re.compile(r"^(?:sealed class|data class|enum class|public enum|public struct) (PN\w+)", re.M)
    for extension, folder in (
        ("swift", root / "ios/Sources/PythonNativeKit/Generated"),
        ("kt", root / "android/src/main/java/com/pythonnative/generated"),
    ):
        checked = set(declaration.findall((folder / f"NativeValues.{extension}").read_text()))
        assert checked <= set(declaration.findall((tmp_path / f"NativeValues.{extension}").read_text()))

        def base(text: str) -> str:
            return text.split("open class PNViewProps", 1)[1].split("\n}\n", 1)[0]

        assert base((tmp_path / f"NativeProps.{extension}").read_text()) == base(
            (folder / f"NativeProps.{extension}").read_text()
        )


def test_example_extension_contracts_match_the_builtins(tmp_path: Path) -> None:
    # The inbox extension's manifest copies View's props; regenerate it in a
    # scratch copy so a built-in change can't leave it stale unnoticed.
    source = Path(__file__).parents[1] / "examples/inbox-extension"
    copy = tmp_path / "inbox-extension"
    shutil.copytree(source / "src", copy / "src")
    shutil.copy2(source / "generate_contracts.py", copy / "generate_contracts.py")
    subprocess.run(
        [sys.executable, str(copy / "generate_contracts.py")],
        check=True,
        env={**os.environ, "PYTHONPATH": str(copy / "src")},
    )
    for relative in ("inbox_extension/native/schema.json", "inbox_extension/api.py"):
        assert (copy / "src" / relative).read_text() == (source / "src" / relative).read_text(), relative


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
