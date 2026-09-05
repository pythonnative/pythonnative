"""Generated native contracts match a clean Python interpreter."""

import subprocess
import sys
from pathlib import Path


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
        for name in ("PNContracts", "NativeProps", "NativeModules"):
            assert (tmp_path / f"{name}.{extension}").read_bytes() == (folder / f"{name}.{extension}").read_bytes()
    for name in ("components.py", "modules.py"):
        compile((tmp_path / name).read_text(), str(tmp_path / name), "exec")
