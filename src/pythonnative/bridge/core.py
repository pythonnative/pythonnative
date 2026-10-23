"""The renderer core's C ABI, bound with ``ctypes`` (see RFC 0007).

Every target links the same C++ core: the iOS app binary, Android's
``libpncore.so``, the ``pythonnative._core`` extension on the development
machine, and the browser preview's WebAssembly build. Python commits to it
directly; the core validates each commit, lays it out with Yoga, flattens
layout-only views, and queues binary mount transactions for the platform's
UI thread. ``include/pn_core.h`` documents the functions and formats.

Strings the core returns are copied here and released with
``pn_core_free``. ``ctypes`` releases the GIL for the duration of each
call, so a commit's layout runs without holding it.
"""

from __future__ import annotations

import ctypes
import os
import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Sequence, Tuple

__all__ = [
    "MountOp",
    "MountTransaction",
    "Platform",
    "RendererCore",
    "decode_transaction",
    "decode_writes",
    "load_core",
]

PROTOCOL_VERSION = 7
"""The protocol ``include/pn_core.h`` defines as ``PN_CORE_PROTOCOL_VERSION``."""

MEASURE_TEXT = 1
MEASURE_INTRINSIC = 2
MEASURE_NATIVE = 3

POINTER_DOWN, POINTER_MOVE, POINTER_UP, POINTER_CANCEL = range(4)


class _Bytes(ctypes.Structure):
    _fields_ = [("data", ctypes.POINTER(ctypes.c_uint8)), ("size", ctypes.c_size_t)]


class _Size(ctypes.Structure):
    _fields_ = [("width", ctypes.c_float), ("height", ctypes.c_float)]


class _MeasureRequest(ctypes.Structure):
    _fields_ = [
        ("surface", ctypes.c_int64),
        ("tag", ctypes.c_int64),
        ("component", ctypes.c_char_p),
        ("mode", ctypes.c_int32),
        ("props", _Bytes),
        ("width", ctypes.c_float),
        ("width_mode", ctypes.c_int32),
        ("height", ctypes.c_float),
        ("height_mode", ctypes.c_int32),
    ]


class _Pointer(ctypes.Structure):
    _fields_ = [
        ("phase", ctypes.c_int32),
        ("pointer", ctypes.c_int32),
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
        ("window_x", ctypes.c_double),
        ("window_y", ctypes.c_double),
        ("time", ctypes.c_double),
    ]


_ScheduleFn = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
_MeasureFn = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(_MeasureRequest), ctypes.POINTER(_Size))
_BaselineFn = ctypes.CFUNCTYPE(
    ctypes.c_float, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_float, ctypes.c_float
)
_EmitFn = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p
)


class _PlatformStruct(ctypes.Structure):
    _fields_ = [
        ("context", ctypes.c_void_p),
        ("schedule_mount", _ScheduleFn),
        ("schedule_work", _ScheduleFn),
        ("request_frames", _ScheduleFn),
        ("measure", _MeasureFn),
        ("baseline", _BaselineFn),
        ("emit", _EmitFn),
    ]


@dataclass
class Platform:
    """Python implementations of the platform callbacks (host and tests).

    On iOS and Android the platform layer is Swift or Kotlin and registers
    itself; a Python platform exists only where Python plays the UI thread.
    """

    schedule_mount: Callable[[], None] = lambda: None
    schedule_work: Callable[[], None] = lambda: None
    request_frames: Callable[[], None] = lambda: None
    measure: Callable[[int, int, str, int, dict[str, Any], float, int, float, int], Tuple[float, float]] = (
        lambda surface, tag, component, mode, props, width, width_mode, height, height_mode: (0.0, 0.0)
    )
    baseline: Callable[[int, int, float, float], float] = lambda surface, tag, width, height: height
    emit: Callable[[str, int, int, str, str], None] = lambda kind, surface, tag, name, payload: None


@dataclass(frozen=True)
class MountOp:
    """One decoded mount transaction op (see ``include/pn_core.h``)."""

    kind: str
    tag: int = 0
    component: str = ""
    props: dict[str, Any] = field(default_factory=dict)
    removed: Tuple[str, ...] = ()
    recreate: bool = False
    parent: int = 0
    index: int = 0
    frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    name: str = ""
    arguments: Any = None
    call_id: int = 0


@dataclass(frozen=True)
class MountTransaction:
    """A decoded transaction: its surface, revision, id, and ops."""

    surface: int
    revision: int
    id: int
    ops: Tuple[MountOp, ...]


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, fmt: str) -> Any:
        value = struct.unpack_from("<" + fmt, self.data, self.offset)
        self.offset += struct.calcsize("<" + fmt)
        return value[0]

    def string(self) -> str:
        length = self.take("I")
        text = self.data[self.offset : self.offset + length].decode("utf-8")
        self.offset += length
        return text

    def value(self) -> Any:
        kind = self.take("B")
        if kind == 0:
            return None
        if kind in (1, 2):
            return kind == 2
        if kind == 3:
            return self.take("q")
        if kind == 4:
            return self.take("d")
        if kind == 5:
            return self.string()
        if kind == 6:
            return [self.value() for _ in range(self.take("I"))]
        if kind == 7:
            out: dict[str, Any] = {}
            for _ in range(self.take("I")):
                key = self.string()
                out[key] = self.value()
            return out
        raise ValueError(f"Unknown value kind {kind} in a mount transaction")


def decode_transaction(data: bytes) -> MountTransaction:
    """Decode a mount transaction (the platform layer's job, done in Python for tests)."""
    reader = _Reader(data)
    if reader.take("I") != 0x544D4E50:
        raise ValueError("Not a mount transaction")
    reader.take("H")
    reader.take("H")
    surface, revision, ident, count = reader.take("q"), reader.take("q"), reader.take("q"), reader.take("I")
    ops: List[MountOp] = []
    for _ in range(count):
        code = reader.take("B")
        if code == 0:
            ops.append(MountOp("reset"))
        elif code == 1:
            tag = reader.take("q")
            ops.append(MountOp("create", tag, component=reader.string(), props=reader.value()))
        elif code == 2:
            tag = reader.take("q")
            flags = reader.take("B")
            changed = reader.value()
            removed = tuple(reader.string() for _ in range(reader.take("I")))
            ops.append(MountOp("update", tag, props=changed, removed=removed, recreate=bool(flags & 1)))
        elif code == 3:
            parent, child, index = reader.take("q"), reader.take("q"), reader.take("I")
            ops.append(MountOp("insert", child, parent=parent, index=index))
        elif code == 5:
            ops.append(MountOp("delete", reader.take("q")))
        elif code == 6:
            tag = reader.take("q")
            frame = (reader.take("d"), reader.take("d"), reader.take("d"), reader.take("d"))
            ops.append(MountOp("frame", tag, frame=frame))
        elif code == 7:
            tag = reader.take("q")
            name = reader.string()
            arguments = reader.value()
            ops.append(MountOp("command", tag, name=name, arguments=arguments, call_id=reader.take("q")))
        else:
            raise ValueError(f"Unknown mount op {code}")
    return MountTransaction(surface, revision, ident, tuple(ops))


def decode_writes(data: bytes) -> List[Tuple[int, str, Any]]:
    """Decode animated prop writes into ``(tag, prop, value)`` tuples."""
    reader = _Reader(data)
    return [(reader.take("q"), reader.string(), reader.value()) for _ in range(reader.take("I"))]


def decode_value(data: bytes) -> Any:
    """Decode one encoded value (measurement requests carry props this way)."""
    return _Reader(data).value()


_SIGNATURES: dict[str, Tuple[Any, List[Any]]] = {
    "pn_core_shared": (ctypes.c_void_p, []),
    "pn_core_protocol_version": (ctypes.c_int32, []),
    "pn_core_set_platform": (None, [ctypes.c_void_p, ctypes.POINTER(_PlatformStruct)]),
    "pn_core_load_contracts": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]),
    "pn_core_contract_fingerprint": (ctypes.c_void_p, [ctypes.c_void_p]),
    "pn_core_set_flattening": (None, [ctypes.c_void_p, ctypes.c_int32]),
    "pn_core_reset": (None, [ctypes.c_void_p]),
    "pn_core_free": (None, [ctypes.c_void_p]),
    "pn_core_commit": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_char_p]),
    "pn_core_layout": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_char_p]),
    "pn_core_command": (
        ctypes.c_void_p,
        [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int64],
    ),
    "pn_core_animate": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p]),
    "pn_core_measure": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_inspect": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_double, ctypes.c_double]),
    "pn_core_validate_module": (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]),
    "pn_core_work": (None, [ctypes.c_void_p]),
    "pn_core_check_value": (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_char_p]),
    "pn_core_mount_next": (
        ctypes.c_int32,
        [ctypes.c_void_p, ctypes.POINTER(_Bytes), ctypes.POINTER(ctypes.c_uint64)],
    ),
    "pn_core_mount_finished": (None, [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p]),
    "pn_core_is_mounted": (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_report_container": (
        None,
        [
            ctypes.c_void_p,
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,
        ],
    ),
    "pn_core_report_intrinsic": (
        None,
        [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_float, ctypes.c_float],
    ),
    "pn_core_invalidate": (None, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_invalidate_measurements": (None, [ctypes.c_void_p]),
    "pn_core_event": (
        None,
        [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int64],
    ),
    "pn_core_animation_frame": (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_double]),
    "pn_core_take_writes": (ctypes.c_int32, [ctypes.c_void_p, ctypes.POINTER(_Bytes)]),
    "pn_core_set_reduce_motion": (None, [ctypes.c_void_p, ctypes.c_int32]),
    "pn_core_pointer": (
        ctypes.c_int32,
        [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.POINTER(_Pointer), ctypes.c_size_t],
    ),
    "pn_core_gesture_deadline": (ctypes.c_double, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_gesture_poll": (None, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_double]),
    "pn_core_has_gestures": (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_list_apply": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_list_count": (ctypes.c_int64, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_list_revision": (ctypes.c_int64, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_list_key": (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_list_extent": (ctypes.c_double, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_list_sticky": (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64]),
    "pn_core_list_row_revision": (ctypes.c_int64, [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64]),
}


class RendererCore:
    """The bound C ABI of one loaded core library.

    Python only uses the process-wide core (``pn_core_shared``), so every
    method passes that handle implicitly.
    """

    if TYPE_CHECKING:
        # The ``_<name>`` foreign functions are bound from ``_SIGNATURES``.
        def __getattr__(self, name: str) -> Any: ...

    def __init__(self, library: Any) -> None:
        self._library = library
        for name, (restype, argtypes) in _SIGNATURES.items():
            try:
                function = getattr(library, name)
            except AttributeError as exc:
                raise RuntimeError(
                    f"The renderer core symbol {name!r} is missing. Rebuild the app (or reinstall pythonnative) so "
                    "the core matches this package."
                ) from exc
            function.restype = restype
            function.argtypes = argtypes
            setattr(self, "_" + name.removeprefix("pn_core_"), function)
        self._handle = self._shared()
        self._platform: Optional[_PlatformStruct] = None
        self._callbacks: Tuple[Any, ...] = ()

    # -- helpers ----------------------------------------------------------

    def _take(self, pointer: Optional[int]) -> Optional[str]:
        if not pointer:
            return None
        try:
            return ctypes.string_at(pointer).decode("utf-8")
        finally:
            self._free(pointer)

    @staticmethod
    def _bytes(value: str) -> bytes:
        return value.encode("utf-8")

    # -- setup ------------------------------------------------------------

    def protocol_version(self) -> int:
        """The protocol compiled into the loaded library."""
        return int(self._protocol_version())

    def load_contracts(self, document: str, platform: str) -> None:
        """Compile the merged contract document for ``platform``.

        Raises:
            RuntimeError: When the document is malformed or conflicts.
        """
        error = self._take(self._load_contracts(self._handle, self._bytes(document), platform.encode()))
        if error is not None:
            raise RuntimeError(f"The renderer core rejected the component contracts: {error}")

    def fingerprint(self) -> str:
        """The fingerprint of the loaded contracts."""
        return self._take(self._contract_fingerprint(self._handle)) or ""

    def set_flattening(self, enabled: bool) -> None:
        """Turn view flattening on or off (``PN_FLATTEN=0`` turns it off)."""
        self._set_flattening(self._handle, int(enabled))

    def reset(self) -> None:
        """Forget every surface, transaction, and contract (tests and reloads)."""
        self._reset(self._handle)

    def set_platform(self, platform: Platform) -> None:
        """Install Python platform callbacks (host and test cores only)."""

        def measure(_context: Any, request: Any, size: Any) -> None:
            r = request.contents
            props = decode_value(ctypes.string_at(r.props.data, r.props.size)) if r.props.size else {}
            try:
                width, height = platform.measure(
                    int(r.surface),
                    int(r.tag),
                    (r.component or b"").decode(),
                    int(r.mode),
                    props or {},
                    float(r.width),
                    int(r.width_mode),
                    float(r.height),
                    int(r.height_mode),
                )
            except Exception:  # pragma: no cover - a measurer must never raise into Yoga
                width, height = 0.0, 0.0
            size.contents.width = float(width)
            size.contents.height = float(height)

        def baseline(_context: Any, surface: int, tag: int, width: float, height: float) -> float:
            return float(platform.baseline(int(surface), int(tag), float(width), float(height)))

        def emit(_context: Any, kind: bytes, surface: int, tag: int, name: bytes, payload: bytes) -> None:
            platform.emit(kind.decode(), int(surface), int(tag), (name or b"").decode(), (payload or b"").decode())

        callbacks = (
            _ScheduleFn(lambda _context: platform.schedule_mount()),
            _ScheduleFn(lambda _context: platform.schedule_work()),
            _ScheduleFn(lambda _context: platform.request_frames()),
            _MeasureFn(measure),
            _BaselineFn(baseline),
            _EmitFn(emit),
        )
        self._callbacks = callbacks
        self._platform = _PlatformStruct(None, *callbacks)
        self._set_platform(self._handle, ctypes.byref(self._platform))

    # -- Python side --------------------------------------------------------

    def commit(self, envelope: str) -> str:
        """Validate and apply one commit envelope; returns the acknowledgement JSON."""
        return self._take(self._commit(self._handle, self._bytes(envelope))) or ""

    def layout(self, request: str) -> str:
        """Lay out without a commit; returns ``{"ok", "value": layout}`` JSON."""
        return self._take(self._layout(self._handle, self._bytes(request))) or ""

    def command(self, surface: int, tag: int, name: str, arguments: str, call_id: int) -> str:
        """Queue a view command; the result arrives later as a ``command`` message."""
        return (
            self._take(self._command(self._handle, surface, tag, name.encode(), self._bytes(arguments), call_id)) or ""
        )

    def animate(self, surface: int, tag: int, request: str) -> str:
        """Queue an animation request behind pending mounts."""
        return self._take(self._animate(self._handle, surface, tag, self._bytes(request))) or ""

    def measure(self, surface: int, tag: int) -> str:
        """The shadow frame and window frame of ``tag`` as JSON (``"null"`` when unknown)."""
        return self._take(self._measure(self._handle, surface, tag)) or "null"

    def inspect(self, surface: int, x: float, y: float) -> str:
        """The deepest view at a point, as JSON."""
        return self._take(self._inspect(self._handle, surface, x, y)) or "null"

    def validate_module(self, module: str, method: str, arguments: str) -> bool:
        """Whether a native module call's arguments satisfy its contract."""
        return bool(self._validate_module(self._handle, module.encode(), method.encode(), self._bytes(arguments)))

    def work(self) -> None:
        """Run deferred native-initiated work (relayout after a container resize)."""
        self._work(self._handle)

    def check_value(self, schema: str, value: str) -> bool:
        """Whether a JSON value satisfies a JSON-schema contract, as the core checks props."""
        return bool(self._check_value(self._bytes(schema), self._bytes(value)))

    # -- UI thread (host and tests) -----------------------------------------

    def mount_next(self) -> Optional[Tuple[bytes, int]]:
        """Take the next transaction's bytes and id, or ``None``."""
        buffer = _Bytes()
        ident = ctypes.c_uint64()
        if not self._mount_next(self._handle, ctypes.byref(buffer), ctypes.byref(ident)):
            return None
        return ctypes.string_at(buffer.data, buffer.size), int(ident.value)

    def mount_finished(self, ident: int, error: Optional[str] = None) -> None:
        """Report a transaction applied (or failed)."""
        self._mount_finished(self._handle, ident, None if error is None else error.encode())

    def is_mounted(self, surface: int, tag: int) -> bool:
        """Whether the UI side holds a view for ``tag``."""
        return bool(self._is_mounted(self._handle, surface, tag))

    def report_container(self, surface: int, tag: int, x: float, y: float, width: float, height: float) -> None:
        """Report the size and window origin of a detached root's container."""
        self._report_container(self._handle, surface, tag, x, y, width, height)

    def report_intrinsic(self, surface: int, tag: int, width: float, height: float) -> None:
        """Report a leaf's loaded content size (an image)."""
        self._report_intrinsic(self._handle, surface, tag, width, height)

    def invalidate(self, surface: int, tag: int) -> None:
        """Re-measure one leaf."""
        self._invalidate(self._handle, surface, tag)

    def invalidate_measurements(self) -> None:
        """Re-measure every leaf."""
        self._invalidate_measurements(self._handle)

    def event(self, surface: int, tag: int, name: str, arguments: str, edit_revision: int = 0) -> None:
        """Stamp and deliver a view event, as the platform layer does."""
        self._event(self._handle, surface, tag, name.encode(), self._bytes(arguments), edit_revision)

    def animation_frame(self, timestamp_ms: float) -> bool:
        """Advance animations; returns whether more frames are needed."""
        return bool(self._animation_frame(self._handle, timestamp_ms))

    def take_writes(self) -> List[Tuple[int, str, Any]]:
        """Animated prop writes produced since the last call."""
        buffer = _Bytes()
        if not self._take_writes(self._handle, ctypes.byref(buffer)):
            return []
        return decode_writes(ctypes.string_at(buffer.data, buffer.size))

    def set_reduce_motion(self, enabled: bool) -> None:
        """Finish every animation at its target, as the platform's setting asks."""
        self._set_reduce_motion(self._handle, int(enabled))

    def pointer(
        self, surface: int, tag: int, events: Sequence[Tuple[int, int, float, float, float, float, float]]
    ) -> bool:
        """Feed ``(phase, pointer, x, y, window_x, window_y, time)`` events to a view's gestures."""
        array = (_Pointer * len(events))(*[_Pointer(*event) for event in events])
        return bool(self._pointer(self._handle, surface, tag, array, len(events)))

    def gesture_deadline(self, surface: int, tag: int) -> Optional[float]:
        """When a view's gestures next need polling, or ``None``."""
        value = float(self._gesture_deadline(self._handle, surface, tag))
        return None if value < 0 else value

    def gesture_poll(self, surface: int, tag: int, time: float) -> None:
        """Advance a view's time-based gestures (long press, multi-tap windows)."""
        self._gesture_poll(self._handle, surface, tag, time)

    def has_gestures(self, surface: int, tag: int) -> bool:
        """Whether the core recognizes gestures for a view."""
        return bool(self._has_gestures(self._handle, surface, tag))

    def list_apply(self, surface: int, tag: int) -> Optional[str]:
        """Publish a list's next dataset patch on the UI side; returns its edits."""
        return self._take(self._list_apply(self._handle, surface, tag))

    def list_revision(self, surface: int, tag: int) -> int:
        """The UI side's published dataset revision for a list (0 before the first)."""
        return int(self._list_revision(self._handle, surface, tag))

    def list_keys(self, surface: int, tag: int) -> List[str]:
        """The UI side's keys for a list."""
        count = int(self._list_count(self._handle, surface, tag))
        return [self._take(self._list_key(self._handle, surface, tag, i)) or "" for i in range(count)]

    def list_rows(self, surface: int, tag: int) -> List[Tuple[str, int, float, bool]]:
        """The UI side's ``(key, revision, extent, sticky)`` rows for a list."""
        rows = []
        for index, key in enumerate(self.list_keys(surface, tag)):
            rows.append(
                (
                    key,
                    int(self._list_row_revision(self._handle, surface, tag, index)),
                    float(self._list_extent(self._handle, surface, tag, index)),
                    bool(self._list_sticky(self._handle, surface, tag, index)),
                )
            )
        return rows


_core: Optional[RendererCore] = None


def _library_path() -> Optional[str]:
    from ..utils import IS_ANDROID, IS_IOS

    if IS_IOS:
        return None  # the core is linked into the app binary
    if IS_ANDROID:
        path = os.environ.get("PN_CORE_LIBRARY")
        if not path:
            raise RuntimeError("PN_CORE_LIBRARY is unset; the Android host loads libpncore.so before Python starts.")
        return path
    import importlib.util

    spec = importlib.util.find_spec("pythonnative._core")
    if spec is None or spec.origin is None:
        raise RuntimeError(
            "The pythonnative._core extension is missing. Reinstall pythonnative, or run "
            "'python setup.py build_ext --inplace' in a source checkout."
        )
    return spec.origin


def load_core() -> RendererCore:
    """Return the process's renderer core, loading the library on first use.

    Setting ``PN_FLATTEN=0`` in the environment mounts every view, which
    helps when a native view debugger should show the whole tree.
    """
    global _core
    if _core is None:
        path = _library_path()
        _core = RendererCore(ctypes.CDLL(path))
        if os.environ.get("PN_FLATTEN") == "0":
            _core.set_flattening(False)
    return _core
