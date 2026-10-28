"""Structured error reports for the development error screen and DevTools.

A traceback says where Python was; it doesn't say which component was
rendering, and it buries the application's frames among the
reconciler's. [`ErrorReport`][pythonnative.errors.ErrorReport] adds both:

- **A component stack.** In development mode the reconciler records the
  component path while rendering, running effects, and updating, and
  attaches it to an exception the first time the exception crosses a
  component (see [`add_component_frame`][pythonnative.errors.add_component_frame]).
  PythonNative's own components (navigators, host roots) are left out.
  The path also appears in the printed traceback as a note (PEP 678):

  ```text
  ZeroDivisionError: division by zero
  The above error occurred in <Counter> (app/main.py:14)
    in <HomeScreen> (app/main.py:30)
    in <App> (app/main.py:52)
  ```

- **Classified frames with source excerpts.** Frames from PythonNative,
  the standard library, and installed packages are marked as framework
  frames, which the error screens collapse; application frames carry a
  few lines of source around the failing line.

The development error screen on iOS, Android, and in the browser preview
renders [`ErrorReport.to_dict`][pythonnative.errors.ErrorReport.to_dict],
and DevTools lists the same reports under Problems. Release builds never
build reports: the error screen is development-only.
"""

from __future__ import annotations

import linecache
import os
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ComponentFrame",
    "ErrorReport",
    "StackFrame",
    "add_component_frame",
    "component_stack",
    "project_path",
    "report",
    "warning_report",
]

_STACK_ATTR = "__pn_component_stack__"
_NOTE_ATTR = "__pn_component_note__"
_DONE_ATTR = "__pn_component_stack_done__"
_EXCERPT_CONTEXT = 2
_MAX_FRAMES = 60

_PACKAGE_ROOT = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class ComponentFrame:
    """One component in a component stack.

    Attributes:
        name: The component's display name.
        file: The file that defines it, relative to the project when
            possible (``app/main.py``); empty for built-ins.
        line: The first line of its definition (``0`` when unknown).
    """

    name: str
    file: str = ""
    line: int = 0

    def describe(self) -> str:
        """``<Name> (app/main.py:14)``, or ``<Name>`` without a location."""
        where = f" ({self.file}:{self.line})" if self.file and self.line else ""
        return f"<{self.name}>{where}"

    def to_dict(self) -> Dict[str, Any]:
        """The JSON shape native error screens and DevTools read."""
        return {"name": self.name, "file": self.file, "line": self.line}


@dataclass(frozen=True)
class StackFrame:
    """One traceback frame, classified and with a source excerpt.

    Attributes:
        file: The frame's file, relative to the project for application
            code (``app/main.py``) and absolute otherwise.
        line: The line number.
        function: The function name.
        code: The failing line's source, stripped.
        excerpt: ``(line number, text)`` pairs around the failing line.
        framework: Whether the frame belongs to PythonNative, the
            standard library, or an installed package.
    """

    file: str
    line: int
    function: str
    code: str = ""
    excerpt: Tuple[Tuple[int, str], ...] = ()
    framework: bool = False

    @property
    def title(self) -> str:
        """``app/main.py:14 in Counter``."""
        return f"{self.file}:{self.line} in {self.function}"

    def excerpt_text(self) -> str:
        """The excerpt as text, with ``>`` marking the failing line."""
        width = len(str(self.excerpt[-1][0])) if self.excerpt else 1
        return "\n".join(
            f"{'>' if number == self.line else ' '} {number:>{width}} | {text}" for number, text in self.excerpt
        )

    def to_dict(self) -> Dict[str, Any]:
        """The JSON shape native error screens and DevTools read."""
        return {
            "file": self.file,
            "line": self.line,
            "function": self.function,
            "code": self.code,
            "title": self.title,
            "excerpt": self.excerpt_text(),
            "framework": self.framework,
        }


@dataclass(frozen=True)
class ErrorReport:
    """An error or warning, ready for an error screen or DevTools.

    Attributes:
        phase: Where it happened: ``"render"``, ``"effect"``,
            ``"event"``, ``"hot reload"``, or ``"warning"``.
        type: The exception's class name (``"warning"`` for warnings).
        message: ``str(exception)`` or the warning text.
        component_stack: Innermost component first.
        frames: Innermost frame last, like a traceback.
        text: The formatted traceback, notes included.
        level: ``"error"`` or ``"warning"``.
    """

    phase: str
    type: str
    message: str
    component_stack: Tuple[ComponentFrame, ...] = ()
    frames: Tuple[StackFrame, ...] = ()
    text: str = ""
    level: str = "error"
    timestamp: float = field(default=0.0, compare=False)

    @property
    def title(self) -> str:
        """``ZeroDivisionError in render: division by zero``."""
        if self.level == "warning":
            return f"Warning: {self.message}"
        return f"{self.type} in {self.phase}: {self.message}" if self.message else f"{self.type} in {self.phase}"

    def to_dict(self) -> Dict[str, Any]:
        """The JSON shape native error screens and DevTools read."""
        return {
            "level": self.level,
            "phase": self.phase,
            "type": self.type,
            "message": self.message,
            "title": self.title,
            "component_stack": [frame.to_dict() for frame in self.component_stack],
            "frames": [frame.to_dict() for frame in self.frames],
            "text": self.text,
            "timestamp": self.timestamp,
        }


# ======================================================================
# Component stacks
# ======================================================================


def _is_framework_component(component: Any) -> bool:
    """Navigators, providers, and host roots defined inside PythonNative."""
    code = getattr(getattr(component, "fn", None), "__code__", None)
    return code is not None and os.path.abspath(code.co_filename).startswith(_PACKAGE_ROOT + os.sep)


def _component_frame(component: Any) -> ComponentFrame:
    name = str(getattr(component, "display_name", None) or getattr(component, "__name__", None) or component)
    fn = getattr(component, "fn", None)
    code = getattr(fn, "__code__", None)
    if code is None or _is_framework_file(code.co_filename):
        return ComponentFrame(name)
    return ComponentFrame(name, project_path(code.co_filename), int(code.co_firstlineno))


def add_component_frame(exc: BaseException, component: Any) -> None:
    """Record that ``exc`` passed through ``component`` while unwinding.

    The reconciler calls this, innermost component first, as an exception
    leaves each component it was rendering. The stack is kept on the
    exception and mirrored into one PEP 678 note, which is rewritten as
    frames are added so the printed traceback always shows the full path.
    Built-in containers (``Column``, ``Text``) aren't components and don't
    appear.

    Args:
        exc: The propagating exception.
        component: A [`Component`][pythonnative.component.Component].
    """
    if getattr(exc, _DONE_ATTR, False) or _is_framework_component(component):
        return
    stack: List[ComponentFrame] = list(getattr(exc, _STACK_ATTR, ()) or ())
    stack.append(_component_frame(component))
    _set_stack(exc, stack)


def complete_component_stack(exc: BaseException, components: Sequence[Any]) -> None:
    """Append ``components`` (innermost first) and stop collecting.

    Used when an update or effect fails in the middle of the tree: the
    reconciler knows the remaining ancestors from the mounted nodes, so
    the stack is completed at once and later frames are ignored.
    """
    if getattr(exc, _DONE_ATTR, False):
        return
    stack: List[ComponentFrame] = list(getattr(exc, _STACK_ATTR, ()) or ())
    for component in components:
        if _is_framework_component(component):
            continue
        frame = _component_frame(component)
        if not stack or stack[-1] != frame:
            stack.append(frame)
    _set_stack(exc, stack)
    try:
        setattr(exc, _DONE_ATTR, True)
    except (AttributeError, TypeError):
        pass


def _set_stack(exc: BaseException, stack: List[ComponentFrame]) -> None:
    if not stack:
        return
    try:
        setattr(exc, _STACK_ATTR, tuple(stack))
    except (AttributeError, TypeError):
        return
    note = "The above error occurred in " + stack[0].describe()
    if len(stack) > 1:
        note += "\n" + "\n".join(f"  in {frame.describe()}" for frame in stack[1:])
    notes = getattr(exc, "__notes__", None)
    previous = getattr(exc, _NOTE_ATTR, None)
    if isinstance(notes, list) and previous is not None and previous in notes:
        notes[notes.index(previous)] = note
    else:
        exc.add_note(note)
    setattr(exc, _NOTE_ATTR, note)


def component_stack(exc: BaseException) -> Tuple[ComponentFrame, ...]:
    """The component stack recorded on ``exc`` (innermost first), or ``()``."""
    stack = getattr(exc, _STACK_ATTR, ())
    return tuple(stack) if isinstance(stack, tuple) else ()


# ======================================================================
# Frames
# ======================================================================


def _framework_roots() -> Tuple[str, ...]:
    import sysconfig

    roots = {_PACKAGE_ROOT + os.sep}
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        try:
            path = sysconfig.get_paths().get(key)
        except Exception:
            path = None
        if path:
            roots.add(os.path.abspath(path) + os.sep)
    for prefix in {sys.prefix, sys.base_prefix, sys.exec_prefix}:
        roots.add(os.path.join(os.path.abspath(prefix), "lib") + os.sep)
    return tuple(sorted(roots))


_FRAMEWORK_ROOTS: Optional[Tuple[str, ...]] = None


def _is_framework_file(filename: str) -> bool:
    global _FRAMEWORK_ROOTS
    if not filename or filename.startswith("<"):
        return True
    path = os.path.abspath(filename)
    if _app_relative(path) is not None:
        return False
    if _FRAMEWORK_ROOTS is None:
        _FRAMEWORK_ROOTS = _framework_roots()
    parts = path.replace("\\", "/").split("/")
    if "site-packages" in parts or "app_packages" in parts or "dist-packages" in parts:
        return True
    return path.startswith(_FRAMEWORK_ROOTS)


def _app_relative(path: str) -> Optional[str]:
    """``app/...`` for a file inside an ``app`` package on ``sys.path``."""
    normalized = path.replace("\\", "/")
    for root in _source_roots():
        prefix = root.rstrip("/") + "/app/"
        if normalized.startswith(prefix):
            return "app/" + normalized[len(prefix) :]
    return None


def _source_roots() -> List[str]:
    roots: List[str] = []
    from .utils import overlay_root

    overlay = overlay_root()
    if overlay:
        roots.append(os.path.abspath(overlay).replace("\\", "/"))
    for entry in sys.path:
        if not entry or os.path.basename(entry.rstrip("/\\")) in ("app_packages", "site-packages"):
            continue
        try:
            if os.path.isdir(os.path.join(entry, "app")):
                roots.append(os.path.abspath(entry).replace("\\", "/"))
        except OSError:
            continue
    return roots


def project_path(filename: str) -> str:
    """``filename`` relative to the project (``app/main.py``) when it's app code.

    Device builds load the app from their bundle or the dev client's
    overlay; both hold an ``app/`` package, so the project-relative path is
    the same everywhere and the dev server can map it back to a file on
    the developer's machine. Anything else is returned unchanged.
    """
    relative = _app_relative(os.path.abspath(filename))
    return relative if relative is not None else filename


def _frames(tb: Any) -> Tuple[StackFrame, ...]:
    frames: List[StackFrame] = []
    for summary in traceback.extract_tb(tb)[-_MAX_FRAMES:]:
        filename = summary.filename
        lineno = int(summary.lineno or 0)
        framework = _is_framework_file(filename)
        excerpt: Tuple[Tuple[int, str], ...] = ()
        if not framework and lineno:
            lines = []
            for number in range(max(1, lineno - _EXCERPT_CONTEXT), lineno + _EXCERPT_CONTEXT + 1):
                text = linecache.getline(filename, number)
                if not text and number > lineno:
                    break
                lines.append((number, text.rstrip("\n")))
            excerpt = tuple(lines)
        frames.append(
            StackFrame(
                file=project_path(filename),
                line=lineno,
                function=summary.name,
                code=(summary.line or "").strip(),
                excerpt=excerpt,
                framework=framework,
            )
        )
    return tuple(frames)


# ======================================================================
# Reports
# ======================================================================


def report(exc: BaseException, phase: str = "runtime") -> ErrorReport:
    """Build an [`ErrorReport`][pythonnative.errors.ErrorReport] for ``exc``.

    Args:
        exc: The exception, with its traceback.
        phase: Where it happened (``"render"``, ``"effect"``, ...).
    """
    import time

    return ErrorReport(
        phase=phase,
        type=type(exc).__name__,
        message=str(exc),
        component_stack=component_stack(exc),
        frames=_frames(exc.__traceback__),
        text="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip(),
        timestamp=time.time(),
    )


def warning_report(message: str, component: Any = None) -> ErrorReport:
    """Build a warning report, attributed to the component rendering now, if any.

    Args:
        message: The warning text.
        component: The rendering component, or its name.
    """
    import time

    stack: Tuple[ComponentFrame, ...] = ()
    if isinstance(component, str):
        stack = (ComponentFrame(component),)
    elif component is not None:
        stack = (_component_frame(component),)
    return ErrorReport(
        phase="warning",
        type="warning",
        message=message,
        component_stack=stack,
        text=message,
        level="warning",
        timestamp=time.time(),
    )
