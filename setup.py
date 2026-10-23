"""Build the host renderer core; mobile hosts compile the same sources."""

import os
from pathlib import Path

from setuptools import Extension, setup

root = Path("src/pythonnative/native/core")
sources = [root / "python.cpp", *sorted((root / "src").glob("*.cpp")), *sorted((root / "yoga").rglob("*.cpp"))]
setup(
    ext_modules=[
        Extension(
            "pythonnative._core",
            sources=[str(path) for path in sources],
            include_dirs=[str(root), str(root / "include")],
            language="c++",
            extra_compile_args=["/std:c++20"] if os.name == "nt" else ["-std=c++20", "-fvisibility=hidden"],
            # ctypes loads the core's C ABI (exported with PN_CORE_API) from
            # the extension library, not just Python's module initializer.
            define_macros=[("_WINDLL", "1")] if os.name == "nt" else [],
        )
    ]
)
