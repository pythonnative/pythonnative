"""Compile staged Python to bytecode for the embedded interpreter.

An app bundle is immutable, so the device can't cache what it compiles:
every module an app imports would be compiled from source on every
launch. Builds compile ahead of time instead, with an interpreter whose
``major.minor`` matches ``app.python_version`` (bytecode is
version-specific).

Two layouts are produced:

- **Debug** keeps each ``.py`` source and writes ``__pycache__`` entries in
  ``unchecked-hash`` mode, which the interpreter trusts without checking
  source timestamps. Tracebacks still show source lines, and Fast Refresh
  still reads source.
- **Release** writes sourceless ``module.pyc`` files where the sources
  were (``compileall -b``) and deletes the sources: smaller bundles and no
  plain-text source in the store artifact.

Compiled code records a bundle-relative filename (``app/main.py``,
``app_packages/pythonnative/...``) rather than a path on the build
machine.
"""

from __future__ import annotations

import compileall
import py_compile
import subprocess
import sys
from pathlib import Path
from typing import Optional

__all__ = ["compile_tree", "compiler_for"]


def compiler_for(python_version: str) -> Optional[str]:
    """Return an interpreter that can compile bytecode for ``python_version``, if one is installed."""
    from .doctor import build_python_for

    return build_python_for(python_version)


def compile_tree(root: Path, compiler: str, *, sourceless: bool, label: str) -> bool:
    """Compile every module under ``root``; return whether all of them compiled.

    Args:
        root: Directory to compile.
        compiler: Interpreter matching the app's Python version.
        sourceless: Replace sources with ``module.pyc`` files (release).
        label: Bundle-relative directory recorded in the bytecode, so
            tracebacks name ``app/main.py`` rather than a build path.
    """
    if not root.is_dir():
        return True
    if compiler == sys.executable:
        ok = bool(
            compileall.compile_dir(
                str(root),
                quiet=1,
                legacy=sourceless,
                optimize=1 if sourceless else 0,
                invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
                stripdir=str(root),
                prependdir=label,
                workers=1,
            )
        )
    else:
        command = [compiler, "-m", "compileall", "-q", "-j", "0", "--invalidation-mode", "unchecked-hash"]
        command += ["-b", "-o", "1"] if sourceless else ["-o", "0"]
        command += ["-s", str(root), "-p", label, str(root)]
        ok = subprocess.run(command, check=False).returncode == 0
    if sourceless:
        for source in root.rglob("*.py"):
            if source.with_suffix(".pyc").exists():
                source.unlink()
        for cache in sorted(root.rglob("__pycache__"), reverse=True):
            for stale in cache.iterdir():
                stale.unlink()
            cache.rmdir()
    return ok
