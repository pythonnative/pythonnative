"""Yoga 3.2.1 layout for headless tests and the Python preview host.

Mobile hosts run this same pinned core beside their native widgets. This
module contains style translation and ownership, not a second flex algorithm.
"""

from __future__ import annotations

import ctypes as C
import math
import weakref
from typing import Any, Callable

LAYOUT_STYLE_KEYS = frozenset(
    {
        "width",
        "height",
        "min_width",
        "max_width",
        "min_height",
        "max_height",
        "flex",
        "flex_grow",
        "flex_shrink",
        "flex_basis",
        "flex_wrap",
        "align_self",
        "align_content",
        "position",
        "top",
        "right",
        "bottom",
        "left",
        "start",
        "end",
        "margin",
        "margin_top",
        "margin_bottom",
        "margin_left",
        "margin_right",
        "margin_start",
        "margin_end",
        "margin_horizontal",
        "margin_vertical",
        "padding",
        "padding_top",
        "padding_bottom",
        "padding_left",
        "padding_right",
        "padding_start",
        "padding_end",
        "padding_horizontal",
        "padding_vertical",
        "border_width",
        "border_top_width",
        "border_right_width",
        "border_bottom_width",
        "border_left_width",
        "flex_direction",
        "justify_content",
        "align_items",
        "spacing",
        "gap",
        "row_gap",
        "column_gap",
        "aspect_ratio",
        "direction",
        "display",
    }
)
"""Style keys that affect layout (and are consumed by the layout engine)."""


_lib: Any = None
_nodes: weakref.WeakValueDictionary[int, LayoutNode] = weakref.WeakValueDictionary()
_Measure = C.CFUNCTYPE(
    None, C.c_void_p, C.c_float, C.c_int, C.c_float, C.c_int, C.POINTER(C.c_float), C.POINTER(C.c_float)
)


@_Measure
def _measure(ptr: int, width: float, wm: int, height: float, hm: int, outw: Any, outh: Any) -> None:
    node = _nodes.get(ptr)
    try:
        w, h = node.measure(width if wm else math.inf, height if hm else math.inf)
        outw[0], outh[0] = max(0, w), max(0, h)
    except BaseException as exc:
        if node is not None:
            node._error = exc
        outw[0] = outh[0] = 0


def _api() -> Any:
    global _lib
    if _lib is not None:
        return _lib
    from . import _yoga

    lib = C.CDLL(_yoga.__file__)
    signatures: dict[str, Any] = {
        "YGNodeNew": (C.c_void_p, []),
        "YGNodeFree": (None, [C.c_void_p]),
        "YGNodeRemoveAllChildren": (None, [C.c_void_p]),
        "YGNodeInsertChild": (None, [C.c_void_p, C.c_void_p, C.c_size_t]),
        "YGNodeCopyStyle": (None, [C.c_void_p, C.c_void_p]),
        "YGNodeMarkDirty": (None, [C.c_void_p]),
        "YGNodeCalculateLayout": (None, [C.c_void_p, C.c_float, C.c_float, C.c_int]),
        "pn_yoga_callback": (None, [_Measure]),
        "pn_yoga_measure": (None, [C.c_void_p, C.c_int]),
    }
    for axis in ("Left", "Top", "Width", "Height"):
        signatures["YGNodeLayoutGet" + axis] = (C.c_float, [C.c_void_p])
    for name, (result, args) in signatures.items():
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
    lib.pn_yoga_callback(_measure)
    _lib = lib
    return lib


# Enum order follows Yoga's public C ABI in the pinned vendored headers.
ENUMS = {
    "direction": ("Direction", ["inherit", "ltr", "rtl"]),
    "flex_direction": ("FlexDirection", ["column", "column_reverse", "row", "row_reverse"]),
    "justify_content": (
        "JustifyContent",
        ["flex_start", "center", "flex_end", "space_between", "space_around", "space_evenly"],
    ),
    "align_items": (
        "AlignItems",
        [
            "auto",
            "flex_start",
            "center",
            "flex_end",
            "stretch",
            "baseline",
            "space_between",
            "space_around",
            "space_evenly",
        ],
    ),
    "align_self": (
        "AlignSelf",
        [
            "auto",
            "flex_start",
            "center",
            "flex_end",
            "stretch",
            "baseline",
            "space_between",
            "space_around",
            "space_evenly",
        ],
    ),
    "align_content": (
        "AlignContent",
        [
            "auto",
            "flex_start",
            "center",
            "flex_end",
            "stretch",
            "baseline",
            "space_between",
            "space_around",
            "space_evenly",
        ],
    ),
    "position": ("PositionType", ["static", "relative", "absolute"]),
    "flex_wrap": ("FlexWrap", ["nowrap", "wrap", "wrap_reverse"]),
    "display": ("Display", ["flex", "none", "contents"]),
}
EDGES = {
    name: i
    for i, name in enumerate(["left", "top", "right", "bottom", "start", "end", "horizontal", "vertical", "all"])
}
ALIASES = {
    "start": "flex_start",
    "leading": "flex_start",
    "top": "flex_start",
    "end": "flex_end",
    "trailing": "flex_end",
    "bottom": "flex_end",
    "fill": "stretch",
}


def _set(ptr: int, name: str, value: Any, edge: int | None = None, *, enum: bool = False) -> None:
    if value is None or isinstance(value, bool):
        return
    suffix = ""
    args: list[Any] = [ptr]
    types: list[Any] = [C.c_void_p]
    if edge is not None:
        args.append(edge)
        types.append(C.c_int)
    if value == "auto":
        suffix = "Auto"
    else:
        if isinstance(value, str) and value.endswith("%"):
            suffix, value = "Percent", float(value[:-1])
        args.append(int(value) if enum else float(value))
        types.append(C.c_int if enum else C.c_float)
    fn = getattr(_api(), "YGNodeStyleSet" + name + suffix)
    fn.restype, fn.argtypes = None, types
    fn(*args)


def apply_style(ptr: int, style: dict[str, Any]) -> None:
    """Translate Pythonic style keys to Yoga's native style API."""
    for key, value in style.items():
        if value is None:
            continue
        if key in ENUMS:
            name, values = ENUMS[key]
            value = ALIASES.get(value, value) if key.startswith(("align_", "justify_")) else value
            if value not in values:
                raise ValueError(f"Invalid {key}: {value!r}")
            _set(ptr, name, values.index(value), enum=True)
        elif key in {
            "width",
            "height",
            "min_width",
            "min_height",
            "max_width",
            "max_height",
            "flex",
            "flex_grow",
            "flex_shrink",
            "flex_basis",
            "aspect_ratio",
        }:
            _set(ptr, "".join(part.title() for part in key.split("_")), value)
        elif key in {"spacing", "gap", "row_gap", "column_gap"}:
            _set(ptr, "Gap", value, {"column_gap": 0, "row_gap": 1}.get(key, 2))
        elif key in EDGES and key not in {"all", "horizontal", "vertical"}:
            _set(ptr, "Position", value, EDGES[key])
        elif key.startswith(("padding", "margin")):
            group, _, edge = key.partition("_")
            if isinstance(value, dict):
                for side, amount in value.items():
                    _set(ptr, group.title(), amount, EDGES[side])
            else:
                _set(ptr, group.title(), value, EDGES[edge or "all"])
        elif key.startswith("border_") and key.endswith("width"):
            _set(ptr, "Border", value, EDGES[key[7:-6] or "all"])


class LayoutNode:
    """An owned Yoga node, with Python measurement for headless backends."""

    def __init__(
        self,
        style: dict[str, Any] | None = None,
        children: list[LayoutNode] | None = None,
        measure: Callable[[float, float], tuple[float, float]] | None = None,
        user_data: Any = None,
    ) -> None:
        self.style = dict(style or {})
        self.children = list(children or [])
        self.measure = measure
        self.user_data = user_data
        self.x = self.y = self.width = self.height = 0.0
        self.dirty = True
        self._pn_scroll_axis: str | None = None
        self._ptr: int | None = None
        self._last_style: Any = None
        self._last_children: tuple[int, ...] = ()
        self._error: BaseException | None = None

    def _sync(self) -> int:
        lib = _api()
        if self._ptr is None:
            self._ptr = lib.YGNodeNew()
            _nodes[self._ptr] = self
            weakref.finalize(self, lib.YGNodeFree, self._ptr)
        ptr = self._ptr
        style = dict(self.style)
        if self._pn_scroll_axis:
            style.setdefault("flex_shrink", 1)
        if style != self._last_style:
            fresh = lib.YGNodeNew()
            apply_style(fresh, style)
            if self._pn_scroll_axis:
                _set(fresh, "Overflow", 1, enum=True)
            lib.YGNodeCopyStyle(ptr, fresh)
            lib.YGNodeFree(fresh)
            self._last_style = style
        measured = self.measure is not None and not self.children
        lib.pn_yoga_measure(ptr, measured)
        if measured and self.dirty:
            lib.YGNodeMarkDirty(ptr)
        children = tuple(child._sync() for child in self.children)
        if children != self._last_children:
            lib.YGNodeRemoveAllChildren(ptr)
            for i, child in enumerate(children):
                lib.YGNodeInsertChild(ptr, child, i)
            self._last_children = children
        return ptr

    def _read(self) -> None:
        lib = _api()
        self.x = lib.YGNodeLayoutGetLeft(self._ptr)
        self.y = lib.YGNodeLayoutGetTop(self._ptr)
        self.width = lib.YGNodeLayoutGetWidth(self._ptr)
        self.height = lib.YGNodeLayoutGetHeight(self._ptr)
        self.dirty = False
        if self._error is not None:
            error, self._error = self._error, None
            raise error
        for child in self.children:
            child._read()


def calculate_layout(node: LayoutNode, width: float, height: float) -> None:
    """Calculate a tree's layout with the pinned Yoga core."""
    ptr = node._sync()
    _api().YGNodeCalculateLayout(
        ptr, width if math.isfinite(width) else math.nan, height if math.isfinite(height) else math.nan, 1
    )
    node._read()


def extract_layout_style(props: dict[str, Any]) -> dict[str, Any]:
    """Select properties owned by layout."""
    return {key: value for key, value in props.items() if key in LAYOUT_STYLE_KEYS}
