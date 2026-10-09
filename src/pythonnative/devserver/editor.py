"""Open a source location from DevTools or an error screen in the developer's editor.

Frames reported by dev clients use project-relative paths (``app/main.py``)
for application code, because the device runs a copy of it. The dev
server resolves them against the project root, and synced packages
against the environment it runs in, then opens the file with:

1. ``$PN_EDITOR``, a command template where ``{file}`` and ``{line}`` are
   substituted (``"code --goto {file}:{line}"``, ``"subl {file}:{line}"``);
   without placeholders, ``{file}:{line}`` is appended;
2. VS Code's ``code --goto`` when it's on ``PATH``;
3. the system's default handler for the file.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

__all__ = ["editor_command", "open_in_editor", "resolve_source"]


def resolve_source(file: str, project_root: str, search: Sequence[str] = ()) -> Optional[Path]:
    """Map a reported frame path to a file on this machine, or ``None``.

    Only files inside the project or one of ``search`` (site-packages
    directories) resolve, so DevTools can't be used to open arbitrary
    paths.
    """
    if not file:
        return None
    roots = [Path(project_root).resolve(), *(Path(entry).resolve() for entry in search)]
    candidate = Path(file)
    candidates: List[Path] = []
    if candidate.is_absolute():
        candidates.append(candidate)
        # A device path: keep everything from the ``app/`` segment on.
        parts = candidate.parts
        if "app" in parts:
            index = len(parts) - 1 - list(reversed(parts)).index("app")
            candidates.append(Path(project_root) / Path(*parts[index:]))
        if "site-packages" in parts:
            index = len(parts) - 1 - list(reversed(parts)).index("site-packages")
            tail = parts[index + 1 :]
            candidates.extend(Path(entry) / Path(*tail) for entry in search if tail)
    else:
        candidates.append(Path(project_root) / candidate)
        candidates.extend(Path(entry) / candidate for entry in search)
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_file() and any(resolved == root or root in resolved.parents for root in roots):
            return resolved
    return None


def editor_command(path: Path, line: int) -> List[str]:
    """The command that opens ``path`` at ``line``."""
    template = os.environ.get("PN_EDITOR", "").strip()
    if template:
        if "{file}" in template:
            return shlex.split(template.replace("{file}", shlex.quote(str(path))).replace("{line}", str(line)))
        return [*shlex.split(template), f"{path}:{line}"]
    code = shutil.which("code")
    if code:
        return [code, "--goto", f"{path}:{line}"]
    if sys.platform == "darwin":
        return ["open", str(path)]
    if os.name == "nt":
        return ["cmd", "/c", "start", "", str(path)]
    return ["xdg-open", str(path)]


def open_in_editor(file: str, line: int, project_root: str, search: Sequence[str] = ()) -> Optional[str]:
    """Open ``file:line`` and return the resolved path, or ``None`` when it doesn't resolve."""
    path = resolve_source(file, project_root, search)
    if path is None:
        return None
    try:
        subprocess.Popen(
            editor_command(path, max(1, int(line or 1))),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None
    return str(path)
