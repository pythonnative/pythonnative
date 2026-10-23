#!/usr/bin/env python3
"""Build the renderer core as WebAssembly for the browser preview (RFC 0007).

Run ``python scripts/build-core-wasm.py`` with the pinned Emscripten on
``PATH`` (``emsdk install 4.0.10 && emsdk activate 4.0.10``). It compiles
the same core and Yoga sources the host extension, iOS, and Android
build, and writes ``devserver/static/core/pn_core.js`` (an ES module
factory) and ``pn_core.wasm``. Both are checked in, so the preview needs
no toolchain; ``--check`` rebuilds into a temporary directory and fails
if the checked-in files have drifted from the sources.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EMSCRIPTEN_VERSION = "4.0.10"
ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src/pythonnative/native/core"
OUTPUT = ROOT / "src/pythonnative/devserver/static/core"
ARTIFACTS = ("pn_core.js", "pn_core.wasm")

# Helpers the page needs besides the C ABI: allocation for strings and
# buffers, and the function table for the platform callbacks.
RUNTIME_METHODS = ("addFunction", "UTF8ToString", "stringToUTF8", "lengthBytesUTF8", "HEAPU8", "HEAPF64")


def exported_functions() -> list[str]:
    """Every ``pn_core_*`` function the C ABI declares, plus the allocator."""
    header = (CORE / "include/pn_core.h").read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"PN_CORE_API\s[^;(]*?\b(pn_core_\w+)\s*\(", header)))
    return ["_malloc", "_free", *(f"_{name}" for name in names)]


def emscripten_version(compiler: str) -> str:
    """The version ``em++ --version`` reports."""
    output = subprocess.run([compiler, "--version"], capture_output=True, text=True, check=True).stdout
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", output)
    return match[1] if match else "unknown"


def build(destination: Path, compiler: str) -> None:
    """Compile and link the core into ``destination``."""
    sources = [*sorted((CORE / "src").glob("*.cpp")), *sorted((CORE / "yoga").rglob("*.cpp"))]
    command = [
        compiler,
        "-std=c++20",
        "-O3",
        "-flto",
        f"-I{CORE}",
        f"-I{CORE / 'include'}",
        *map(str, sources),
        "-o",
        str(destination / "pn_core.js"),
        "-sMODULARIZE=1",
        "-sEXPORT_ES6=1",
        "-sEXPORT_NAME=createCore",
        "-sENVIRONMENT=web,worker",
        "-sALLOW_MEMORY_GROWTH=1",
        "-sALLOW_TABLE_GROWTH=1",
        "-sFILESYSTEM=0",
        "-sDISABLE_EXCEPTION_CATCHING=0",
        "-sEXPORTED_FUNCTIONS=" + ",".join(exported_functions()),
        "-sEXPORTED_RUNTIME_METHODS=" + ",".join(RUNTIME_METHODS),
        # Paths in the output would make it differ between checkouts.
        f"-ffile-prefix-map={ROOT}=.",
    ]
    subprocess.run(command, check=True, cwd=ROOT, env=os.environ | {"SOURCE_DATE_EPOCH": "0"})


def main() -> int:
    """Build or drift-check the WebAssembly core."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in build differs from the sources")
    parser.add_argument("--compiler", default=shutil.which("em++"), help="The em++ to use (default: from PATH)")
    args = parser.parse_args()

    if args.compiler is None:
        print(f"em++ isn't on PATH. Install Emscripten {EMSCRIPTEN_VERSION} with emsdk and activate it.")
        return 1
    version = emscripten_version(args.compiler)
    if version != EMSCRIPTEN_VERSION:
        print(f"This build needs Emscripten {EMSCRIPTEN_VERSION}; {args.compiler} is {version}.")
        return 1

    with tempfile.TemporaryDirectory() as temporary:
        built = Path(temporary)
        build(built, args.compiler)
        if args.check:
            stale = [name for name in ARTIFACTS if (OUTPUT / name).read_bytes() != (built / name).read_bytes()]
            if stale:
                print(f"The WebAssembly core is out of date ({', '.join(stale)}). Run scripts/build-core-wasm.py.")
                return 1
            print("The WebAssembly core matches its sources.")
            return 0
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for name in ARTIFACTS:
            shutil.copyfile(built / name, OUTPUT / name)
    for name in ARTIFACTS:
        print(f"Wrote {(OUTPUT / name).relative_to(ROOT)} ({(OUTPUT / name).stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
