"""Build the host Yoga binding; mobile hosts compile the vendored core."""

import os
from pathlib import Path

from setuptools import Extension, setup

root = Path("src/pythonnative/native/yoga")
setup(
    ext_modules=[
        Extension(
            "pythonnative._yoga",
            sources=[str(root / "python.cpp"), *map(str, sorted((root / "yoga").rglob("*.cpp")))],
            include_dirs=[str(root)],
            language="c++",
            extra_compile_args=["/std:c++20"] if os.name == "nt" else ["-std=c++20"],
            # ctypes loads Yoga's C API and our measurement callbacks from
            # the extension DLL, not just Python's module initializer.
            define_macros=[("_WINDLL", "1")] if os.name == "nt" else [],
            export_symbols=["pn_yoga_callback", "pn_yoga_measure"] if os.name == "nt" else [],
        )
    ]
)
