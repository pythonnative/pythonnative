"""Vector shapes for [`Svg`][pythonnative.Svg], plus an SVG document loader.

Shapes are plain frozen dataclasses, not elements: an ``Svg`` view draws
all of its shapes itself (one native view, one layout node), the same way
``Text`` flattens rich spans instead of nesting child views. Build them
with the constructors here and pass them to ``pn.Svg``:

```python
import pythonnative as pn
from pythonnative import svg

pn.Svg(
    svg.Circle(cx=12, cy=12, r=10, fill="#0EA5E9"),
    svg.Path(d="M8 12h8M12 8v8", stroke="white", stroke_width=2),
    view_box="0 0 24 24",
    style=pn.style(width=48, height=48),
)
```

Coordinates are in ``view_box`` units and are scaled into the view's
frame according to ``preserve_aspect_ratio``. Paint attributes left as
``None`` inherit from the enclosing [`G`][pythonnative.svg.G] and then
from the ``Svg`` root, following SVG's cascade (fill defaults to black,
stroke to none).

[`parse`][pythonnative.svg.parse] and [`load`][pythonnative.svg.load]
turn an SVG document's basic shapes into a ready-to-render ``Svg``
element, which is enough for exported icons and simple illustrations.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, fields
from pathlib import Path as _FsPath
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple, Union, cast

from .style import Color

__all__ = [
    "Circle",
    "Ellipse",
    "FillRule",
    "G",
    "Line",
    "LineCap",
    "LineJoin",
    "Path",
    "Polygon",
    "Polyline",
    "Rect",
    "Shape",
    "SvgShape",
    "flatten",
    "load",
    "parse",
    "parse_view_box",
]

FillRule = Literal["nonzero", "evenodd"]
LineCap = Literal["butt", "round", "square"]
LineJoin = Literal["miter", "round", "bevel"]


# ----------------------------------------------------------------------
# Wire record
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class SvgShape:
    """One drawable shape as it crosses the bridge.

    Geometry fields that don't apply to ``kind`` stay ``None``. Paint
    fields that are ``None`` inherit from the ``Svg`` root.
    """

    kind: Literal["path", "circle", "ellipse", "rect", "line", "polyline", "polygon"]
    d: Optional[str] = None
    cx: Optional[float] = None
    cy: Optional[float] = None
    r: Optional[float] = None
    rx: Optional[float] = None
    ry: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    x1: Optional[float] = None
    y1: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None
    points: Optional[str] = None
    fill: Optional[Color] = None
    fill_opacity: Optional[float] = None
    fill_rule: Optional[FillRule] = None
    stroke: Optional[Color] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_linecap: Optional[LineCap] = None
    stroke_linejoin: Optional[LineJoin] = None
    stroke_dasharray: Optional[List[float]] = None
    opacity: Optional[float] = None
    transform: Optional[str] = None


# ----------------------------------------------------------------------
# Python-facing shapes
# ----------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class _Paint:
    """Paint attributes shared by every shape and by ``G``."""

    fill: Optional[Color] = None
    fill_opacity: Optional[float] = None
    fill_rule: Optional[FillRule] = None
    stroke: Optional[Color] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_linecap: Optional[LineCap] = None
    stroke_linejoin: Optional[LineJoin] = None
    stroke_dasharray: Optional[Sequence[float]] = None
    opacity: Optional[float] = None
    transform: Optional[str] = None


_PAINT_KEYS = tuple(f.name for f in fields(_Paint))


@dataclass(frozen=True, kw_only=True)
class Path(_Paint):
    """A path described by SVG path data (``M L H V C S Q T A Z`` and lowercase forms).

    Attributes:
        d: The path data string.
    """

    d: str

    kind = "path"


@dataclass(frozen=True, kw_only=True)
class Circle(_Paint):
    """A circle centered at ``(cx, cy)`` with radius ``r``."""

    cx: float
    cy: float
    r: float

    kind = "circle"


@dataclass(frozen=True, kw_only=True)
class Ellipse(_Paint):
    """An ellipse centered at ``(cx, cy)`` with radii ``rx`` and ``ry``."""

    cx: float
    cy: float
    rx: float
    ry: float

    kind = "ellipse"


@dataclass(frozen=True, kw_only=True)
class Rect(_Paint):
    """A rectangle with optional rounded corners (``rx``/``ry``)."""

    x: float = 0.0
    y: float = 0.0
    width: float
    height: float
    rx: Optional[float] = None
    ry: Optional[float] = None

    kind = "rect"


@dataclass(frozen=True, kw_only=True)
class Line(_Paint):
    """A straight line from ``(x1, y1)`` to ``(x2, y2)``."""

    x1: float
    y1: float
    x2: float
    y2: float

    kind = "line"


@dataclass(frozen=True, kw_only=True)
class Polyline(_Paint):
    """An open series of connected points.

    Attributes:
        points: Either an SVG ``points`` string (``"0,0 10,5 0,10"``) or a
            sequence of ``(x, y)`` pairs.
    """

    points: Union[str, Sequence[Tuple[float, float]]]

    kind = "polyline"


@dataclass(frozen=True, kw_only=True)
class Polygon(_Paint):
    """A closed series of connected points (see [`Polyline`][pythonnative.svg.Polyline])."""

    points: Union[str, Sequence[Tuple[float, float]]]

    kind = "polygon"


class G(_Paint):
    """A group: its paint attributes cascade to children and its ``transform`` is applied first.

    Groups are flattened before crossing the bridge; they exist so a
    subtree can share a fill or a transform, exactly as ``<g>`` does.

    Example:
        ```python
        svg.G(
            svg.Rect(x=0, y=0, width=10, height=10),
            svg.Circle(cx=5, cy=5, r=3, fill="white"),
            fill="#0EA5E9",
            transform="translate(7 7)",
        )
        ```
    """

    __slots__ = ("children",)

    def __init__(self, *children: "Shape", **paint: Any) -> None:
        unknown = set(paint) - set(_PAINT_KEYS)
        if unknown:
            raise TypeError(f"G() got unexpected paint attributes: {', '.join(sorted(unknown))}")
        _Paint.__init__(self, **paint)
        object.__setattr__(self, "children", tuple(children))

    def __repr__(self) -> str:
        return f"G({', '.join(repr(child) for child in self.children)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, G):
            return NotImplemented
        return self.children == other.children and all(getattr(self, key) == getattr(other, key) for key in _PAINT_KEYS)

    def __hash__(self) -> int:
        return hash((self.children, tuple(getattr(self, key) for key in _PAINT_KEYS if key != "stroke_dasharray")))


Shape = Union[Path, Circle, Ellipse, Rect, Line, Polyline, Polygon, G]
"""Anything ``Svg`` accepts as a child."""


def _points_text(points: Union[str, Sequence[Tuple[float, float]]]) -> str:
    if isinstance(points, str):
        return re.sub(r"\s+", " ", points.strip())
    return " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in points)


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _merge_transform(parent: Optional[str], child: Optional[str]) -> Optional[str]:
    if parent and child:
        return f"{parent} {child}"
    return parent or child


def flatten(shapes: Iterable[Any], inherited: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Flatten shapes and groups into the wire list of ``SvgShape`` dicts.

    Group paint cascades to children that leave the attribute ``None``;
    group transforms are prepended to child transforms so the child is
    transformed first, as in SVG.

    Raises:
        TypeError: If an item isn't a shape or group.
    """
    inherited = dict(inherited or {})
    out: List[Dict[str, Any]] = []
    for shape in shapes:
        if shape is None:
            continue
        if isinstance(shape, G):
            child_paint = dict(inherited)
            for key in _PAINT_KEYS:
                if key == "transform":
                    continue
                value = getattr(shape, key)
                if value is not None:
                    child_paint[key] = value
            child_paint["transform"] = _merge_transform(inherited.get("transform"), shape.transform)
            out.extend(flatten(shape.children, child_paint))
            continue
        if isinstance(shape, dict):
            record = dict(shape)
        elif isinstance(shape, SvgShape):
            record = {f.name: getattr(shape, f.name) for f in fields(shape)}
        elif isinstance(shape, _Paint) and hasattr(shape, "kind"):
            record = {f.name: getattr(shape, f.name) for f in fields(shape)}
            record["kind"] = shape.kind
        else:
            raise TypeError(f"Svg children must be svg shapes or G groups, got {type(shape).__name__}")
        for key in _PAINT_KEYS:
            if record.get(key) is None and inherited.get(key) is not None and key != "transform":
                record[key] = inherited[key]
        record["transform"] = _merge_transform(inherited.get("transform"), record.get("transform"))
        if record.get("points") is not None:
            record["points"] = _points_text(record["points"])
        if record.get("stroke_dasharray") is not None:
            record["stroke_dasharray"] = [float(v) for v in record["stroke_dasharray"]]
        out.append({key: value for key, value in record.items() if value is not None})
    return out


# ----------------------------------------------------------------------
# Parsing SVG documents
# ----------------------------------------------------------------------

_SVG_NS = "{http://www.w3.org/2000/svg}"
_UNIT = re.compile(r"^\s*(-?\d*\.?\d+(?:e[-+]?\d+)?)\s*(px|pt|mm|cm|in|em|rem|%)?\s*$", re.IGNORECASE)
_ATTR_TO_FIELD = {
    "fill": "fill",
    "fill-opacity": "fill_opacity",
    "fill-rule": "fill_rule",
    "stroke": "stroke",
    "stroke-width": "stroke_width",
    "stroke-opacity": "stroke_opacity",
    "stroke-linecap": "stroke_linecap",
    "stroke-linejoin": "stroke_linejoin",
    "stroke-dasharray": "stroke_dasharray",
    "opacity": "opacity",
    "transform": "transform",
}
_NUMERIC_PAINT = {"fill_opacity", "stroke_width", "stroke_opacity", "opacity"}


def parse_view_box(text: Optional[str]) -> Optional[Tuple[float, float, float, float]]:
    """Parse ``"minx miny width height"`` (commas allowed); ``None`` when malformed."""
    if not text:
        return None
    parts = re.split(r"[\s,]+", text.strip())
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (float(p) for p in parts)
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def _length(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    match = _UNIT.match(text)
    if match is None:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit == "pt":
        value *= 4 / 3
    elif unit == "mm":
        value *= 96 / 25.4
    elif unit == "cm":
        value *= 96 / 2.54
    elif unit == "in":
        value *= 96
    elif unit == "%":
        return None
    return value


def _paint_attrs(element: ET.Element) -> Dict[str, Any]:
    raw: Dict[str, str] = {}
    for key, value in element.attrib.items():
        if key in _ATTR_TO_FIELD:
            raw[key] = value
    style = element.attrib.get("style")
    if style:
        for declaration in style.split(";"):
            name, sep, value = declaration.partition(":")
            if sep and name.strip() in _ATTR_TO_FIELD:
                raw[name.strip()] = value.strip()
    paint: Dict[str, Any] = {}
    for attr, value in raw.items():
        field = _ATTR_TO_FIELD[attr]
        text = value.strip()
        if not text or text in ("inherit",):
            continue
        if field in ("fill", "stroke"):
            if text == "currentColor" or text.startswith("url("):
                continue  # inherit from the root; gradients aren't supported
            paint[field] = text
        elif field in _NUMERIC_PAINT:
            number = _length(text)
            if number is not None:
                paint[field] = number
        elif field == "stroke_dasharray":
            if text != "none":
                numbers = [_length(part) for part in re.split(r"[\s,]+", text) if part]
                if numbers and all(n is not None for n in numbers):
                    paint[field] = numbers
        elif field == "fill_rule":
            if text in ("nonzero", "evenodd"):
                paint[field] = text
        elif field == "stroke_linecap":
            if text in ("butt", "round", "square"):
                paint[field] = text
        elif field == "stroke_linejoin":
            if text in ("miter", "round", "bevel"):
                paint[field] = text
            elif text in ("miter-clip", "arcs"):
                paint[field] = "miter"
        else:
            paint[field] = text
    return paint


def _num(element: ET.Element, name: str, default: float = 0.0) -> float:
    value = _length(element.attrib.get(name))
    return default if value is None else value


def _shapes_from(element: ET.Element) -> List[Shape]:
    shapes: List[Shape] = []
    for child in element:
        tag = child.tag.replace(_SVG_NS, "")
        paint = _paint_attrs(child)
        if tag == "g":
            shapes.append(G(*_shapes_from(child), **paint))
        elif tag == "path":
            d = child.attrib.get("d", "").strip()
            if d:
                shapes.append(Path(d=re.sub(r"\s+", " ", d), **paint))
        elif tag == "circle":
            shapes.append(Circle(cx=_num(child, "cx"), cy=_num(child, "cy"), r=_num(child, "r"), **paint))
        elif tag == "ellipse":
            shapes.append(
                Ellipse(cx=_num(child, "cx"), cy=_num(child, "cy"), rx=_num(child, "rx"), ry=_num(child, "ry"), **paint)
            )
        elif tag == "rect":
            rx = _length(child.attrib.get("rx"))
            ry = _length(child.attrib.get("ry"))
            shapes.append(
                Rect(
                    x=_num(child, "x"),
                    y=_num(child, "y"),
                    width=_num(child, "width"),
                    height=_num(child, "height"),
                    rx=rx if rx is not None else ry,
                    ry=ry if ry is not None else rx,
                    **paint,
                )
            )
        elif tag == "line":
            shapes.append(
                Line(x1=_num(child, "x1"), y1=_num(child, "y1"), x2=_num(child, "x2"), y2=_num(child, "y2"), **paint)
            )
        elif tag == "polyline":
            shapes.append(Polyline(points=child.attrib.get("points", ""), **paint))
        elif tag == "polygon":
            shapes.append(Polygon(points=child.attrib.get("points", ""), **paint))
        # <defs>, <title>, <desc>, <text>, <use>, <style>, gradients, filters,
        # masks, and clip paths are skipped; see the RFC's non-goals.
    return shapes


def parse(markup: str, **svg_props: Any) -> Any:
    """Turn an SVG document into an [`Svg`][pythonnative.Svg] element.

    Supported: ``<path>``, ``<circle>``, ``<ellipse>``, ``<rect>``,
    ``<line>``, ``<polyline>``, ``<polygon>``, and ``<g>`` (with paint
    and ``transform``), the presentation attributes listed on
    [`Path`][pythonnative.svg.Path], inline ``style="..."`` declarations,
    and the root ``viewBox``, ``width``, ``height``, ``fill``, ``stroke``
    and ``stroke-*`` attributes. Everything else is ignored.

    Args:
        markup: The SVG source text.
        **svg_props: Extra keyword arguments for ``Svg`` (``style``,
            ``fill``, ``stroke``, ``key``, ...). These override values
            read from the document.

    Raises:
        ValueError: If ``markup`` isn't well-formed XML with an ``<svg>``
            root.
    """
    shapes, props = _parse_document(markup)
    return _build(shapes, props, svg_props)


def _parse_document(markup: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return the flattened shapes and root ``Svg`` props of a document."""
    try:
        root = ET.fromstring(markup)
    except ET.ParseError as exc:
        raise ValueError(f"invalid SVG: {exc}") from exc
    if root.tag.replace(_SVG_NS, "") != "svg":
        raise ValueError("invalid SVG: root element must be <svg>")
    view_box = root.attrib.get("viewBox")
    if not parse_view_box(view_box):
        width = _length(root.attrib.get("width"))
        height = _length(root.attrib.get("height"))
        view_box = f"0 0 {_fmt(width)} {_fmt(height)}" if width and height else "0 0 24 24"
    root_paint = _paint_attrs(root)
    props: Dict[str, Any] = {"view_box": re.sub(r"[\s,]+", " ", str(view_box).strip())}
    for key in ("fill", "stroke", "stroke_width", "stroke_linecap", "stroke_linejoin", "fill_rule"):
        if key in root_paint:
            props[key] = root_paint[key]
    if root_paint.get("opacity") is not None:
        # Root opacity is a style prop on the element rather than a paint.
        props["style"] = {"opacity": root_paint["opacity"]}
    return flatten(_shapes_from(root)), props


def _build(shapes: List[Dict[str, Any]], props: Dict[str, Any], overrides: Dict[str, Any]) -> Any:
    from .components.graphics import Svg

    merged = dict(props)
    merged.update(overrides)
    # Flattened records are already in wire form; ``flatten`` passes dicts through.
    return Svg(shapes=cast("List[SvgShape]", shapes), **merged)


_LOAD_CACHE: Dict[Tuple[str, int], Tuple[List[Dict[str, Any]], Dict[str, Any]]] = {}


def load(source: Any, **svg_props: Any) -> Any:
    """Load an SVG file and return an [`Svg`][pythonnative.Svg] element.

    Args:
        source: An [`Asset`][pythonnative.Asset] (``pn.asset("icons/x.svg")``),
            a filesystem path, or SVG markup starting with ``<``.
        **svg_props: Extra keyword arguments for ``Svg``, typically
            ``style=pn.style(width=..., height=...)``. They override the
            document's root attributes.

    Assets are parsed once per asset generation and cached, so calling
    ``load`` on every render is cheap. Files given by path are re-read
    each call.

    Raises:
        FileNotFoundError: If the asset or file can't be read.
        ValueError: If the content isn't a valid SVG document.
    """
    from .assets import Asset, generation

    if isinstance(source, Asset):
        key = (source.path, generation())
        cached = _LOAD_CACHE.get(key)
        if cached is None:
            cached = _parse_document(source.read_text())
            if len(_LOAD_CACHE) > 256:
                _LOAD_CACHE.clear()
            _LOAD_CACHE[key] = cached
        shapes, props = cached
        return _build(shapes, props, svg_props)
    if isinstance(source, str) and source.lstrip().startswith("<"):
        return parse(source, **svg_props)
    return parse(_FsPath(str(source)).read_text(encoding="utf-8"), **svg_props)
