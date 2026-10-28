"""Read the identifying tables of TrueType and OpenType font files.

The build tool and the dev server need to know, for every file under
``app/assets/fonts/``, which family it belongs to and which weight and
style it provides, so ``font_family="Poppins", font_weight=700`` can be
matched to ``Poppins-Bold.ttf`` on every platform without a hand-written
mapping. That information lives inside the font: the ``name`` table
carries the family and PostScript names and the ``OS/2`` table carries
the weight class and the italic flag.

This module reads exactly those tables (plus ``head`` as a fallback for
the style bits) with :mod:`struct`; it never parses glyph data. It
handles ``.ttf``, ``.otf`` (CFF outlines), and the first face of a
``.ttc`` collection.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

__all__ = ["FontFace", "FontParseError", "read_font_face", "weight_from_name"]

_WEIGHT_WORDS: Tuple[Tuple[str, int], ...] = (
    ("hairline", 100),
    ("thin", 100),
    ("extralight", 200),
    ("extra light", 200),
    ("ultralight", 200),
    ("ultra light", 200),
    ("light", 300),
    ("book", 400),
    ("normal", 400),
    ("regular", 400),
    ("medium", 500),
    ("semibold", 600),
    ("semi bold", 600),
    ("demibold", 600),
    ("demi bold", 600),
    ("extrabold", 800),
    ("extra bold", 800),
    ("ultrabold", 800),
    ("ultra bold", 800),
    ("bold", 700),
    ("black", 900),
    ("heavy", 900),
)


class FontParseError(ValueError):
    """The file isn't a TrueType or OpenType font this reader understands."""


@dataclass(frozen=True)
class FontFace:
    """One face (a family at one weight and style) provided by a font file.

    Attributes:
        family: The family name apps pass as ``font_family``.
        weight: CSS-style weight from 100 to 900.
        italic: Whether the face is italic or oblique.
        postscript_name: The PostScript name, which is what ``UIFont(name:)``
            resolves after the file is registered.
        path: The file path relative to ``app/assets/`` (forward slashes).
    """

    family: str
    weight: int
    italic: bool
    postscript_name: str
    path: str


def weight_from_name(subfamily: str) -> Optional[int]:
    """Infer a CSS weight from a style name like ``"Semi Bold Italic"``.

    Longer words are checked first so ``"extrabold"`` doesn't match
    ``"bold"``. Returns ``None`` when nothing matches.
    """
    lowered = subfamily.lower()
    for word, weight in _WEIGHT_WORDS:
        if word in lowered:
            return weight
    return None


def read_font_face(source: Union[str, Path, bytes], *, path: str = "") -> FontFace:
    """Return the [`FontFace`][pythonnative.assets.FontFace] described by a font file.

    Args:
        source: A file path or the file's bytes.
        path: The asset-relative path recorded on the result. Defaults to
            the file name when ``source`` is a path.

    Raises:
        FontParseError: If the data isn't a supported font.
    """
    if isinstance(source, (str, Path)):
        data = Path(source).read_bytes()
        if not path:
            path = Path(source).name
    else:
        data = source
    tables = _table_directory(data)
    names = _read_names(data, tables.get("name"))
    family = names.get(16) or names.get(1)
    if not family:
        raise FontParseError("font has no family name")
    subfamily = names.get(17) or names.get(2) or ""
    postscript = names.get(6) or "".join(part for part in (family + "-" + subfamily).split())
    weight, italic = _read_os2(data, tables.get("OS/2"))
    if weight is None:
        weight = weight_from_name(subfamily) or weight_from_name(names.get(4) or "") or 400
    if italic is None:
        italic = (
            "italic" in subfamily.lower() or "oblique" in subfamily.lower() or _head_italic(data, tables.get("head"))
        )
    return FontFace(
        family=family, weight=weight, italic=italic, postscript_name=postscript, path=path.replace("\\", "/")
    )


# ----------------------------------------------------------------------
# Table access
# ----------------------------------------------------------------------


def _table_directory(data: bytes) -> Dict[str, Tuple[int, int]]:
    if len(data) < 12:
        raise FontParseError("file is too small to be a font")
    tag = data[:4]
    offset = 0
    if tag == b"ttcf":
        if len(data) < 16:
            raise FontParseError("truncated font collection")
        offset = struct.unpack(">I", data[12:16])[0]
        if offset + 12 > len(data):
            raise FontParseError("truncated font collection")
        tag = data[offset : offset + 4]
    if tag not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        raise FontParseError("not a TrueType or OpenType font")
    (count,) = struct.unpack(">H", data[offset + 4 : offset + 6])
    tables: Dict[str, Tuple[int, int]] = {}
    record = offset + 12
    for _ in range(count):
        if record + 16 > len(data):
            raise FontParseError("truncated table directory")
        name = data[record : record + 4].decode("latin-1")
        table_offset, length = struct.unpack(">II", data[record + 8 : record + 16])
        if table_offset + length <= len(data):
            tables[name] = (table_offset, length)
        record += 16
    return tables


def _read_names(data: bytes, table: Optional[Tuple[int, int]]) -> Dict[int, str]:
    if table is None:
        raise FontParseError("font has no name table")
    start, length = table
    if length < 6:
        raise FontParseError("truncated name table")
    _fmt, count, strings = struct.unpack(">HHH", data[start : start + 6])
    # Prefer Windows Unicode English, then Macintosh Roman, then Unicode.
    best: Dict[int, Tuple[int, str]] = {}
    record = start + 6
    for _ in range(count):
        if record + 12 > start + length:
            break
        platform, encoding, language, name_id, size, offset = struct.unpack(">HHHHHH", data[record : record + 12])
        record += 12
        chunk = data[start + strings + offset : start + strings + offset + size]
        if len(chunk) != size:
            continue
        rank: Optional[int]
        if platform == 3 and encoding in (1, 10):
            rank = 0 if language == 0x409 else 1
            text = _decode(chunk, "utf-16-be")
        elif platform == 1 and encoding == 0:
            rank = 2
            text = _decode(chunk, "mac-roman")
        elif platform == 0:
            rank = 3
            text = _decode(chunk, "utf-16-be")
        else:
            rank = None
            text = ""
        if rank is None or not text:
            continue
        if name_id not in best or rank < best[name_id][0]:
            best[name_id] = (rank, text)
    return {name_id: text for name_id, (_, text) in best.items()}


def _decode(chunk: bytes, encoding: str) -> str:
    try:
        return chunk.decode(encoding).strip("\x00").strip()
    except (UnicodeDecodeError, LookupError):
        return chunk.decode("latin-1", errors="replace").strip("\x00").strip()


def _read_os2(data: bytes, table: Optional[Tuple[int, int]]) -> Tuple[Optional[int], Optional[bool]]:
    if table is None:
        return None, None
    start, length = table
    weight: Optional[int] = None
    italic: Optional[bool] = None
    if length >= 6:
        (weight_class,) = struct.unpack(">H", data[start + 4 : start + 6])
        if 1 <= weight_class <= 1000:
            # Some fonts store the legacy 1 to 9 scale; expand it.
            weight = weight_class * 100 if weight_class < 10 else weight_class
            weight = max(100, min(900, int(round(weight / 100.0)) * 100))
    if length >= 64:
        (selection,) = struct.unpack(">H", data[start + 62 : start + 64])
        italic = bool(selection & 0x0001) or bool(selection & 0x0200)
    return weight, italic


def _head_italic(data: bytes, table: Optional[Tuple[int, int]]) -> bool:
    if table is None:
        return False
    start, length = table
    if length < 46:
        return False
    (mac_style,) = struct.unpack(">H", data[start + 44 : start + 46])
    return bool(mac_style & 0x0002)
