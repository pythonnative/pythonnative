"""A small, dependency-free QR code encoder for the dev server.

``pn start`` prints a QR code for the dev-client connect link
(``pn-com.pythonnative.go://connect?url=...``) so a phone running the
dev client can join the server by pointing its camera at the terminal,
and the DevTools page shows the same link as an SVG. Both renderings come
from this module, which is standard library only so it also runs inside
the embedded interpreter on device.

The encoder implements QR Code Model 2 as specified in ISO/IEC 18004:

- numeric, alphanumeric, and byte (UTF-8) modes, picked automatically
  as the most compact single mode that holds the whole input,
- error correction levels ``L``, ``M``, ``Q``, and ``H``,
- versions 1 through 40, choosing the smallest version that fits,
- Reed-Solomon error correction with the standard block interleaving,
  BCH-protected format and version information, and
- all eight data masks, keeping the one with the lowest penalty score.

Example:
    ```python
    from pythonnative.devserver import qr

    code = qr.encode("pn-com.pythonnative.go://connect?url=ws%3A%2F%2F10.0.0.2%3A8081")
    print(qr.to_terminal(code))
    svg = qr.to_svg(code, scale=4)
    ```
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from typing import Callable, List, Optional, Tuple

__all__ = ["QRCode", "encode", "to_svg", "to_terminal"]

# fmt: off
# Error-correction codewords per block and number of blocks, indexed by
# [level][version] (ISO/IEC 18004 Table 9). Index 0 is unused.
_ECC_PER_BLOCK = {
    "L": (0, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28,
          28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "M": (0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26,
          26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    "Q": (0, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30,
          28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "H": (0, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28,
          30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
}
_NUM_BLOCKS = {
    "L": (0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8,
          8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
    "M": (0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16,
          17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    "Q": (0, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20,
          23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    "H": (0, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25,
          25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
}
# fmt: on
# The two-bit level indicator stored in the format information.
_LEVEL_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}

_ALPHANUMERIC = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
# Mode indicator and character-count bit widths for versions 1-9, 10-26, and 27-40.
_MODES = {
    "numeric": (0b0001, (10, 12, 14)),
    "alphanumeric": (0b0010, (9, 11, 13)),
    "byte": (0b0100, (8, 16, 16)),
}

# A 1:1:3:1:1 finder-like run, scored by penalty rule N3.
_FINDER_LIKE = b"\x01\x00\x01\x01\x01\x00\x01"
_LONG_RUNS = re.compile(rb"\x00{5,}|\x01{5,}")
_BIT_DIGITS = bytes.maketrans(b"\x00\x01", b"01")

Grid = List[bytearray]


@dataclass(frozen=True)
class QRCode:
    """An encoded QR code symbol.

    Attributes:
        version: The symbol version, from 1 (21 x 21 modules) to 40
            (177 x 177 modules).
        size: The number of modules along each side, ``4 * version + 17``.
        modules: The module grid as rows from top to bottom, each row
            listing modules from left to right. ``True`` is a dark module.
            The grid doesn't include a quiet zone.
        error: The error correction level, one of ``"L"``, ``"M"``,
            ``"Q"``, or ``"H"``.
        mask: The data mask pattern applied to the symbol, from 0 to 7.
    """

    version: int
    size: int
    modules: Tuple[Tuple[bool, ...], ...]
    error: str = "M"
    mask: int = 0

    def __getitem__(self, xy: Tuple[int, int]) -> bool:
        """Return whether the module at column ``x`` and row ``y`` is dark."""
        x, y = xy
        return self.modules[y][x]


def encode(text: str, *, error: str = "M", version: Optional[int] = None, mask: Optional[int] = None) -> QRCode:
    """Encode ``text`` as a QR code.

    The encoder uses numeric mode when ``text`` is all digits,
    alphanumeric mode when it only uses the 45-character QR alphabet
    (digits, uppercase letters, space, and ``$%*+-./:``), and byte mode
    with UTF-8 otherwise. No ECI header is written; scanners detect UTF-8
    on their own.

    Args:
        text: The text to encode.
        error: The error correction level: ``"L"`` (about 7% recovery),
            ``"M"`` (15%), ``"Q"`` (25%), or ``"H"`` (30%).
        version: Force a specific version from 1 to 40 instead of the
            smallest one that fits.
        mask: Force a data mask pattern from 0 to 7 instead of the one
            with the lowest penalty score.

    Returns:
        The encoded symbol.

    Raises:
        ValueError: If an argument is out of range or ``text`` doesn't fit
            in the requested (or the largest) version.
    """
    return _encode(text, _pick_mode(text), error, version, mask)


def to_terminal(code: QRCode, *, border: int = 2, invert: bool = False) -> str:
    """Render a QR code as Unicode half blocks for a terminal.

    Each text line holds two module rows, drawn with ``"▀"``, ``"▄"``,
    ``"█"``, and spaces, so the symbol stays roughly square in typical
    monospace fonts.

    Most terminals draw light text on a dark background, so by default the
    *light* modules (including the quiet zone) are drawn as filled blocks
    and the dark modules are left as background. That scans correctly on a
    dark terminal. Pass ``invert=True`` for a dark-on-light terminal, where
    the filled blocks become the dark modules.

    Args:
        code: The symbol to render.
        border: The width of the quiet zone in modules. The standard asks
            for 4, but 2 scans reliably and saves terminal space.
        invert: Draw dark modules as filled blocks instead of light ones.

    Returns:
        The rendering, one string with a line per pair of module rows and
        no trailing newline.

    Raises:
        ValueError: If ``border`` is negative.
    """
    if border < 0:
        raise ValueError("border must not be negative")
    span = range(-border, code.size + border)

    def filled(x: int, y: int) -> bool:
        if y >= code.size + border:
            return False  # Padding below the last row is plain background.
        dark = 0 <= x < code.size and 0 <= y < code.size and code.modules[y][x]
        return dark == invert

    glyphs = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}
    lines = []
    for y in range(-border, code.size + border, 2):
        lines.append("".join(glyphs[filled(x, y), filled(x, y + 1)] for x in span))
    return "\n".join(lines)


def to_svg(code: QRCode, *, border: int = 4, scale: int = 1, dark: str = "#000", light: str = "#fff") -> str:
    """Render a QR code as a compact SVG document.

    The light background is a single ``<rect>`` and every dark module is
    part of a single ``<path>``. The ``viewBox`` is measured in modules and
    ``shape-rendering="crispEdges"`` keeps the module edges sharp at any
    size.

    Args:
        code: The symbol to render.
        border: The width of the quiet zone in modules.
        scale: The ``width`` and ``height`` of one module in CSS pixels.
        dark: The CSS color of dark modules.
        light: The CSS color of light modules and the quiet zone.

    Returns:
        The SVG markup.

    Raises:
        ValueError: If ``border`` is negative or ``scale`` isn't positive.
    """
    if border < 0:
        raise ValueError("border must not be negative")
    if scale < 1:
        raise ValueError("scale must be at least 1")
    width = code.size + 2 * border
    runs = []
    for y, row in enumerate(code.modules):
        x = 0
        for is_dark, group in itertools.groupby(row):
            length = len(list(group))
            if is_dark:
                runs.append(f"M{x + border} {y + border}h{length}v1h-{length}z")
            x += length
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {width}" '
        f'width="{width * scale}" height="{width * scale}" shape-rendering="crispEdges">'
        f'<rect width="{width}" height="{width}" fill="{escape(light)}"/>'
        f'<path fill="{escape(dark)}" d="{"".join(runs)}"/></svg>'
    )


# ── Data encoding ───────────────────────────────────────────────────────


def _pick_mode(text: str) -> str:
    if text and text.isascii() and text.isdigit():
        return "numeric"
    if text and all(ch in _ALPHANUMERIC for ch in text):
        return "alphanumeric"
    return "byte"


def _payload_bits(text: str, mode: str) -> Tuple[int, str]:
    """Return the character count and the encoded data bits for ``text``."""
    if mode == "numeric":
        chunks = (text[i : i + 3] for i in range(0, len(text), 3))
        return len(text), "".join(format(int(c), f"0{len(c) * 3 + 1}b") for c in chunks)
    if mode == "alphanumeric":
        values = [_ALPHANUMERIC.index(ch) for ch in text]
        bits = []
        for i in range(0, len(values), 2):
            pair = values[i : i + 2]
            bits.append(format(pair[0] * 45 + pair[1], "011b") if len(pair) == 2 else format(pair[0], "06b"))
        return len(text), "".join(bits)
    data = text.encode("utf-8")
    return len(data), "".join(format(b, "08b") for b in data)


def _raw_modules(version: int) -> int:
    """Return the number of modules available for data and ECC codewords."""
    result = (16 * version + 128) * version + 64
    if version >= 2:
        count = version // 7 + 2
        result -= (25 * count - 10) * count - 55
        if version >= 7:
            result -= 36
    return result


def _data_capacity(version: int, error: str) -> int:
    """Return the number of data codewords for ``version`` at ``error``."""
    return _raw_modules(version) // 8 - _ECC_PER_BLOCK[error][version] * _NUM_BLOCKS[error][version]


def _encode(text: str, mode: str, error: str, version: Optional[int], mask: Optional[int]) -> QRCode:
    if error not in _ECC_PER_BLOCK:
        raise ValueError(f"error must be one of 'L', 'M', 'Q', or 'H', not {error!r}")
    if version is not None and not 1 <= version <= 40:
        raise ValueError(f"version must be between 1 and 40, not {version}")
    if mask is not None and not 0 <= mask <= 7:
        raise ValueError(f"mask must be between 0 and 7, not {mask}")
    count, payload = _payload_bits(text, mode)
    indicator, count_widths = _MODES[mode]
    candidates = [version] if version is not None else range(1, 41)
    for ver in candidates:
        width = count_widths[0 if ver <= 9 else 1 if ver <= 26 else 2]
        capacity = _data_capacity(ver, error) * 8
        if count < 1 << width and 4 + width + len(payload) <= capacity:
            break
    else:
        where = f"version {version}" if version is not None else "any version"
        raise ValueError(f"{count} characters in {mode} mode don't fit in {where} at level {error}")
    bits = format(indicator, "04b") + format(count, f"0{width}b") + payload
    bits += "0" * min(4, capacity - len(bits))
    bits += "0" * (-len(bits) % 8)
    data = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))
    data += bytes(itertools.islice(itertools.cycle(b"\xec\x11"), capacity // 8 - len(data)))
    return _build(ver, error, _interleave(data, ver, error), mask)


# ── Reed-Solomon error correction ──────────────────────────────────────

_EXP = bytearray(512)
_LOG = bytearray(256)
_value = 1
for _i in range(255):
    _EXP[_i] = _EXP[_i + 255] = _value
    _LOG[_value] = _i
    _value <<= 1
    if _value & 0x100:
        _value ^= 0x11D
del _i, _value


@lru_cache(maxsize=None)
def _generator(degree: int) -> Tuple[int, ...]:
    """Return the RS generator polynomial of ``degree``, highest power first."""
    poly = [1]
    for i in range(degree):
        poly = [a ^ (_EXP[_LOG[b] + i] if b else 0) for a, b in zip(poly + [0], [0] + poly)]
    return tuple(poly)


def _ecc(data: bytes, degree: int) -> bytes:
    """Return the ``degree`` RS error-correction codewords for ``data``."""
    gen = _generator(degree)
    rem = bytearray(data) + bytearray(degree)
    for i in range(len(data)):
        coef = rem[i]
        if coef:
            log = _LOG[coef]
            for j in range(1, degree + 1):
                if gen[j]:
                    rem[i + j] ^= _EXP[_LOG[gen[j]] + log]
    return bytes(rem[len(data) :])


def _interleave(data: bytes, version: int, error: str) -> bytes:
    """Split ``data`` into blocks, add ECC, and interleave the codewords."""
    blocks = _NUM_BLOCKS[error][version]
    degree = _ECC_PER_BLOCK[error][version]
    short_len = len(data) // blocks
    num_short = blocks - len(data) % blocks
    pieces = []
    offset = 0
    for i in range(blocks):
        length = short_len + (i >= num_short)
        pieces.append(data[offset : offset + length])
        offset += length
    eccs = [_ecc(piece, degree) for piece in pieces]
    out = bytearray()
    for i in range(short_len + 1):
        out.extend(piece[i] for piece in pieces if i < len(piece))
    for i in range(degree):
        out.extend(ecc[i] for ecc in eccs)
    return bytes(out)


# ── Symbol construction ────────────────────────────────────────────────


def _alignment_positions(version: int) -> List[int]:
    if version == 1:
        return []
    count = version // 7 + 2
    step = 26 if version == 32 else (version * 4 + count * 2 + 1) // (count * 2 - 2) * 2
    last = version * 4 + 10
    return [6] + [last - i * step for i in reversed(range(count - 1))]


def _bch(value: int, poly: int, degree: int) -> int:
    """Append the ``degree``-bit BCH remainder of ``value`` over ``poly``."""
    rem = value << degree
    for shift in reversed(range(poly.bit_length() - 1, rem.bit_length())):
        if rem >> shift & 1:
            rem ^= poly << (shift - poly.bit_length() + 1)
    return value << degree | rem


# The eight data mask conditions; a module at row ``y``, column ``x`` is
# inverted when its condition holds.
_MASKS: Tuple[Callable[[int, int], bool], ...] = (
    lambda y, x: (y + x) % 2 == 0,
    lambda y, x: y % 2 == 0,
    lambda y, x: x % 3 == 0,
    lambda y, x: (y + x) % 3 == 0,
    lambda y, x: (y // 2 + x // 3) % 2 == 0,
    lambda y, x: (y * x) % 2 + (y * x) % 3 == 0,
    lambda y, x: ((y * x) % 2 + (y * x) % 3) % 2 == 0,
    lambda y, x: ((y + x) % 2 + (y * x) % 3) % 2 == 0,
)


def _function_patterns(version: int) -> Tuple[Grid, Grid]:
    """Return the grid with function patterns drawn and the reserved-module map.

    Format and version information areas are reserved but left light; they
    are drawn after the mask has been chosen.
    """
    size = version * 4 + 17
    grid = [bytearray(size) for _ in range(size)]
    reserved = [bytearray(size) for _ in range(size)]

    def put(x: int, y: int, dark: bool) -> None:
        grid[y][x] = dark
        reserved[y][x] = 1

    for i in range(size):
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                if 0 <= cx + dx < size and 0 <= cy + dy < size:
                    put(cx + dx, cy + dy, max(abs(dx), abs(dy)) not in (2, 4))
    positions = _alignment_positions(version)
    corners = {(6, 6), (6, size - 7), (size - 7, 6)}
    for cx, cy in itertools.product(positions, repeat=2):
        if (cx, cy) not in corners:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    put(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
    for i in range(9):
        reserved[8][i] = reserved[i][8] = 1
    for i in range(8):
        reserved[8][size - 1 - i] = reserved[size - 1 - i][8] = 1
    if version >= 7:
        for i in range(18):
            a, b = size - 11 + i % 3, i // 3
            reserved[b][a] = reserved[a][b] = 1
    return grid, reserved


def _place_data(grid: Grid, reserved: Grid, codewords: bytes) -> None:
    """Draw ``codewords`` in the zigzag order; leftover modules stay light."""
    size = len(grid)
    total = len(codewords) * 8
    i = 0
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        upward = (right + 1) & 2 == 0
        for vert in range(size):
            y = size - 1 - vert if upward else vert
            for x in (right, right - 1):
                if not reserved[y][x] and i < total:
                    grid[y][x] = codewords[i >> 3] >> (7 - (i & 7)) & 1
                    i += 1
        right -= 2


def _apply_mask(grid: Grid, reserved: Grid, mask: int) -> Grid:
    condition = _MASKS[mask]
    out = [bytearray(row) for row in grid]
    for y, (row, fixed) in enumerate(zip(out, reserved)):
        for x, is_fixed in enumerate(fixed):
            if not is_fixed and condition(y, x):
                row[x] ^= 1
    return out


def _draw_format_and_version(grid: Grid, version: int, error: str, mask: int) -> None:
    size = len(grid)
    bits = _bch(_LEVEL_BITS[error] << 3 | mask, 0x537, 10) ^ 0x5412
    for i in range(15):
        bit = bits >> i & 1
        # Around the top-left finder: up column 8, then left along row 8.
        if i < 6:
            grid[i][8] = bit
        elif i < 8:
            grid[i + 1][8] = bit
        elif i == 8:
            grid[8][7] = bit
        else:
            grid[8][14 - i] = bit
        # Split between the top-right and bottom-left finders.
        if i < 8:
            grid[8][size - 1 - i] = bit
        else:
            grid[size - 15 + i][8] = bit
    grid[size - 8][8] = 1  # The dark module.
    if version >= 7:
        bits = _bch(version, 0x1F25, 12)
        for i in range(18):
            a, b = size - 11 + i % 3, i // 3
            grid[b][a] = grid[a][b] = bits >> i & 1


def _penalty(grid: Grid) -> int:
    """Score a masked symbol with the four penalty rules of ISO/IEC 18004."""
    size = len(grid)
    rows = [bytes(row) for row in grid]
    score = 0
    for line in itertools.chain(rows, (bytes(col) for col in zip(*rows))):
        # N1: runs of five or more same-colored modules.
        score += sum(len(run) - 2 for run in _LONG_RUNS.findall(line))
        # N3: 1:1:3:1:1 patterns with four light modules on either side.
        idx = line.find(_FINDER_LIKE)
        while idx != -1:
            end = idx + 7
            if 1 not in line[max(idx - 4, 0) : idx] or 1 not in line[end : end + 4]:
                score += 40
                idx = line.find(_FINDER_LIKE, end)
            else:
                idx = line.find(_FINDER_LIKE, idx + 4)
    # N2: 2 x 2 blocks of one color, found with bitwise row comparisons.
    full = (1 << size) - 1
    ints = [int(row.translate(_BIT_DIGITS), 2) for row in rows]
    for upper, lower in zip(ints, ints[1:]):
        same_vertical = ~(upper ^ lower) & full
        same_horizontal = ~(upper ^ (upper >> 1))
        score += 3 * (same_vertical & (same_vertical >> 1) & same_horizontal & (full >> 1)).bit_count()
    # N4: deviation of the dark proportion from 50%, in 5% steps.
    total = size * size
    dark = sum(row.count(1) for row in rows)
    return score + 10 * (abs(dark * 100 - total * 50) // (total * 5))


def _build(version: int, error: str, codewords: bytes, mask: Optional[int]) -> QRCode:
    grid, reserved = _function_patterns(version)
    _place_data(grid, reserved, codewords)
    if mask is None:
        # Masks are scored before format and version information is drawn
        # (those areas count as light), as ISO/IEC 18004:2015 section 7.8
        # describes and segno implements.
        candidates = [(m, _apply_mask(grid, reserved, m)) for m in range(8)]
        mask, masked = min(candidates, key=lambda item: _penalty(item[1]))
    else:
        masked = _apply_mask(grid, reserved, mask)
    _draw_format_and_version(masked, version, error, mask)
    modules = tuple(tuple(bool(v) for v in row) for row in masked)
    return QRCode(version=version, size=len(modules), modules=modules, error=error, mask=mask)
