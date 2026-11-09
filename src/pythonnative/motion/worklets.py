"""The ``@worklet`` marker, compiled programs, and capture encoding (RFC 0009).

A worklet is compiled once per code object, from its source in development
or from the table ``pn build`` precompiles for release builds, which ship
without source. Each install resolves the worklet's captures against the
function object (its closure cells, then its globals, then builtins) and
encodes them for the core: constants, shared values, other worklets as
closures, supported builtins as intrinsics, and ``run_on_python`` targets
as Python callbacks.
"""

from __future__ import annotations

import builtins
import contextvars
import enum
import itertools
import json
import math
import sys
import types
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from .compiler import WorkletError, code_positions, compile_function
from .program import Capture, Program

__all__ = ["Encoder", "closure_wire", "is_worklet", "program_for", "require_worklet", "worklet"]

F = TypeVar("F", bound=Callable[..., Any])

_MARK = "__pn_worklet__"


def worklet(fn: F) -> F:
    """Mark ``fn`` as a worklet, so callbacks that accept one run it on the UI thread.

    The function is unchanged: calling it from Python runs it as Python.
    Event props and gesture callbacks run a worklet in the renderer core,
    on the UI thread, instead of in Python. It's compiled the first time
    it's installed, and a construct the UI thread can't run raises
    [`WorkletError`][pythonnative.motion.WorkletError] with its location.

    Example:
        ```python
        @pn.worklet
        def drag(event: gestures.GestureEvent) -> None:
            offset.value = event.translation_x
        ```
    """
    try:
        setattr(fn, _MARK, True)
    except (AttributeError, TypeError) as exc:
        raise TypeError(f"@worklet decorates Python functions, not {type(fn).__name__}") from exc
    return fn


def is_worklet(value: Any) -> bool:
    """Whether ``value`` was marked with ``@worklet`` (or passed as an inline lambda to a worklet API)."""
    return callable(value) and getattr(value, _MARK, False) is True


def require_worklet(fn: Any, api: str) -> Callable[..., Any]:
    """Accept a decorated worklet or an inline lambda for a worklet-only API.

    Raises:
        TypeError: For anything else. Requiring the marker keeps code that
            works in development (where any source compiles) from failing in
            a release build, which only precompiles marked worklets and
            lambdas passed inline.
    """
    if is_worklet(fn):
        return fn
    code = getattr(fn, "__code__", None)
    if isinstance(code, types.CodeType) and code.co_name == "<lambda>":
        return worklet(fn)
    raise TypeError(f"{api}() needs a @pn.worklet function or an inline lambda, not {fn!r}")


# ======================================================================
# Programs
# ======================================================================

_programs: Dict[types.CodeType, Tuple[int, Program]] = {}
_program_ids = itertools.count(1)
_precompiled: Optional[Dict[str, Any]] = None


def _precompiled_table() -> Dict[str, Any]:
    """Every ``pn_worklets.json`` on ``sys.path`` (release builds), merged; empty in development."""
    global _precompiled
    if _precompiled is None:
        _precompiled = {}
        for entry in sys.path:
            candidate = Path(entry or ".") / "pn_worklets.json"
            try:
                if candidate.is_file():
                    _precompiled.update(json.loads(candidate.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return _precompiled


def _from_table(code: types.CodeType) -> Optional[Program]:
    table = _precompiled_table()
    if not table:
        return None
    # The device may record an absolute or a bundle-relative file name; the
    # table keys are relative, so match the longest suffix.
    parts = Path(code.co_filename).parts
    module = None
    for start in range(len(parts)):
        module = table.get("/".join(parts[start:]))
        if module is not None:
            break
    if module is None:
        return None
    entry = module.get(f"{code.co_firstlineno}:{code.co_name}")
    if entry is None:
        return None
    if code.co_name == "<lambda>":
        positions = code_positions(code)
        for candidate in entry:
            if tuple(candidate["body"]) in positions:
                return Program.from_json(candidate["program"])
        return None
    return Program.from_json(entry)


def program_for(fn: Callable[..., Any]) -> Tuple[int, Program]:
    """The program id and compiled program for a worklet function.

    Raises:
        WorkletError: When it doesn't compile.
    """
    code = getattr(fn, "__code__", None)
    if not isinstance(code, types.CodeType):
        raise WorkletError(f"{fn!r} isn't a Python function, so it can't be a worklet")
    found = _programs.get(code)
    if found is None:
        program = _from_table(code) or compile_function(fn)
        found = (next(_program_ids), program)
        _programs[code] = found
    return found


def forget_programs() -> None:
    """Drop compiled programs (Fast Refresh and tests)."""
    _programs.clear()


# ======================================================================
# Intrinsics
# ======================================================================

_MATH = (
    "sin cos tan asin acos atan atan2 sqrt exp log log10 log2 pow floor ceil fabs hypot degrees radians "
    "copysign fmod isfinite isnan isinf trunc"
).split()


def _intrinsic_table() -> Dict[int, Tuple[Any, str]]:
    from . import animations

    table: Dict[int, Tuple[Any, str]] = {}
    for value, name in [
        (builtins.abs, "abs"),
        (builtins.min, "min"),
        (builtins.max, "max"),
        (builtins.round, "round"),
        (builtins.int, "int"),
        (builtins.float, "float"),
        (builtins.bool, "bool"),
        (builtins.len, "len"),
        *((getattr(math, fn), f"math.{fn}") for fn in _MATH),
        (animations.with_timing, "with_timing"),
        (animations.with_spring, "with_spring"),
        (animations.with_decay, "with_decay"),
        (animations.with_delay, "with_delay"),
        (animations.with_sequence, "with_sequence"),
        (animations.with_repeat, "with_repeat"),
        (animations.interpolate, "interpolate"),
        (animations.interpolate_color, "interpolate_color"),
        (animations.clamp, "clamp"),
        (animations.snap_point, "snap_point"),
        (animations.run_on_python, "run_on_python"),
    ]:
        table[id(value)] = (value, name)
    return table


_intrinsics: Optional[Dict[int, Tuple[Any, str]]] = None


def intrinsic_name(value: Any) -> Optional[str]:
    """The core's name for a builtin or motion helper a worklet may call, or ``None``."""
    global _intrinsics
    if _intrinsics is None:
        _intrinsics = _intrinsic_table()
    entry = _intrinsics.get(id(value))
    return entry[1] if entry is not None and entry[0] is value else None


# ======================================================================
# Encoding captures
# ======================================================================


class Encoder:
    """Collects what an install needs on the target: programs, shared values, and Python callbacks."""

    def __init__(self, register_callback: Optional[Callable[[Callable[..., Any]], int]] = None) -> None:
        self.programs: Dict[int, Program] = {}
        self.shared: List[Any] = []
        self.callbacks: List[int] = []
        self._register = register_callback
        self._depth = 0

    def callback(self, fn: Callable[..., Any]) -> int:
        """Register a ``run_on_python`` target and return its id."""
        if self._register is None:
            raise WorkletError("run_on_python() callbacks need a mounted app")
        ident = self._register(fn)
        self.callbacks.append(ident)
        return ident


_encoder: contextvars.ContextVar[Optional[Encoder]] = contextvars.ContextVar("pn_motion_encoder", default=None)


def current_encoder() -> Encoder:
    """The encoder of the install in progress (a fresh one outside any install)."""
    encoder = _encoder.get()
    return encoder if encoder is not None else Encoder()


def encoding(encoder: Encoder) -> contextvars.Token[Optional[Encoder]]:
    """Make ``encoder`` current; reset with the returned token."""
    return _encoder.set(encoder)


def end_encoding(token: contextvars.Token[Optional[Encoder]]) -> None:
    _encoder.reset(token)


def _resolve(fn: Callable[..., Any], capture: Capture) -> Any:
    code = fn.__code__
    root = capture.root
    if root in code.co_freevars:
        cell = fn.__closure__[code.co_freevars.index(root)]  # type: ignore[index]
        try:
            value = cell.cell_contents
        except ValueError as exc:
            raise WorkletError(
                f"{root!r} is used by worklet {code.co_qualname} before it's assigned",
                code.co_filename,
                code.co_firstlineno,
            ) from exc
    elif root in fn.__globals__:
        value = fn.__globals__[root]
    elif hasattr(builtins, root):
        value = getattr(builtins, root)
    else:
        raise WorkletError(f"name {root!r} isn't defined", code.co_filename, code.co_firstlineno)
    for kind, key in capture.steps:
        try:
            value = getattr(value, key) if kind == "attr" else value[key]
        except (AttributeError, KeyError, IndexError, TypeError) as exc:
            raise WorkletError(
                f"can't read {capture.describe()} for worklet {code.co_qualname}: {exc}",
                code.co_filename,
                code.co_firstlineno,
            ) from exc
    return value


def encode_value(value: Any, mode: str = "value", *, owner: str = "", encoder: Optional[Encoder] = None) -> Any:
    """Encode one captured value for the core.

    Raises:
        WorkletError: For a value a worklet can't use.
    """
    from .shared import SharedValue

    encoder = encoder or current_encoder()
    if mode == "callback":
        if not callable(value):
            raise WorkletError(f"run_on_python() needs a callable, not {type(value).__name__}")
        return {"__python__": encoder.callback(value)}
    if isinstance(value, SharedValue):
        encoder.shared.append(value)
        return {"__shared__": value.id}
    name = intrinsic_name(value)
    if name is not None:
        return {"__intrinsic__": name}
    if is_worklet(value):
        return closure_wire(value, encoder=encoder)
    if mode == "call":
        label = getattr(value, "__qualname__", type(value).__name__)
        raise WorkletError(
            f"{owner or 'a worklet'} can't call {label} on the UI thread; mark it @pn.worklet, "
            "or call it with run_on_python()"
        )
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorkletError(f"{owner or 'a worklet'} captured {value}, which the core can't represent")
        return value
    if isinstance(value, enum.Enum):
        return encode_value(value.value, owner=owner, encoder=encoder)
    if isinstance(value, (tuple, list)):
        return [encode_value(item, owner=owner, encoder=encoder) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise WorkletError(f"{owner or 'a worklet'} captured a dict with non-string keys")
        return {key: encode_value(item, owner=owner, encoder=encoder) for key, item in value.items()}
    wire = getattr(value, "__pn_wire__", None)
    if callable(wire):
        token = encoding(encoder)
        try:
            return wire()
        finally:
            end_encoding(token)
    if callable(value):
        label = getattr(value, "__qualname__", type(value).__name__)
        raise WorkletError(
            f"{owner or 'a worklet'} captured the function {label}; mark it @pn.worklet to call it on the UI thread, "
            "or pass it to run_on_python()"
        )
    raise WorkletError(f"{owner or 'a worklet'} can't capture a {type(value).__name__}")


def closure_wire(fn: Callable[..., Any], *, encoder: Optional[Encoder] = None) -> Dict[str, Any]:
    """Encode a worklet and its captures as ``{"__closure__": {"program", "captures"}}``.

    Raises:
        WorkletError: When it doesn't compile or captures something a worklet can't use.
    """
    encoder = encoder or current_encoder()
    ident, program = program_for(fn)
    encoder.programs[ident] = program
    encoder._depth += 1
    try:
        if encoder._depth > 16:
            raise WorkletError(f"worklet {program.name} refers to itself; recursive worklets aren't supported")
        captures = []
        for capture in program.captures:
            try:
                captures.append(
                    encode_value(_resolve(fn, capture), capture.mode, owner=f"worklet {program.name}", encoder=encoder)
                )
            except WorkletError as error:
                if error.filename:
                    raise
                # Point at the worklet that captured the value.
                raise WorkletError(error.message, program.file, program.line) from error
    finally:
        encoder._depth -= 1
    return {"__closure__": {"program": ident, "captures": captures}}
