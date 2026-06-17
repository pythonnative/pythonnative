"""App icon and splash image generation.

Given a single high-resolution source image per asset (a 1024x1024 icon
and an optional splash image), this module renders the per-platform,
per-density variants each toolchain expects:

- iOS: a single-size ``AppIcon.appiconset`` (Xcode resizes at build time)
  and a ``Splash`` image set referenced by the generated launch screen.
- Android: ``mipmap-*`` launcher PNGs at every density (mdpi…xxxhdpi),
  a circular round-icon variant, and a centered splash icon used by the
  Android 12+ splash screen.

Image resizing uses [Pillow](https://python-pillow.org/), declared as the
``[build]`` optional dependency. When Pillow isn't installed every
function degrades gracefully: it returns ``False`` (and the caller keeps
the template's default assets) so a missing optional dependency never
breaks a build. ``pn doctor`` reports whether Pillow is available.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Android launcher icon sizes (px) per density bucket.
ANDROID_LAUNCHER_DENSITIES: Dict[str, int] = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}


def pillow_available() -> bool:
    """Return whether Pillow can be imported.

    Returns:
        ``True`` if ``PIL.Image`` imports, else ``False``.
    """
    try:
        import PIL.Image  # noqa: F401
    except Exception:
        return False
    return True


def _open_rgba(source: Path) -> "object":
    from PIL import Image

    img = Image.open(source).convert("RGBA")
    return img


def _resized(img: "object", size: int) -> "object":
    from PIL import Image

    return img.resize((size, size), Image.LANCZOS)


def _circular(img: "object") -> "object":
    """Return a copy of a square image masked to a circle."""
    from PIL import Image, ImageDraw

    size = img.size[0]
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)  # type: ignore[arg-type]
    return out


def generate_ios_icons(source: Path, appiconset_dir: Path) -> bool:
    """Generate a single-size iOS ``AppIcon.appiconset``.

    Writes ``icon-1024.png`` (a flattened, opaque 1024x1024 image; the
    App Store rejects icons with alpha) and a ``Contents.json`` that
    declares it as the universal iOS app icon. Xcode derives every other
    size at build time.

    Args:
        source: Path to the source icon image.
        appiconset_dir: The ``AppIcon.appiconset`` directory to populate.

    Returns:
        ``True`` if icons were written, ``False`` if Pillow is missing.
    """
    if not pillow_available():
        return False
    from PIL import Image

    appiconset_dir.mkdir(parents=True, exist_ok=True)
    img = _open_rgba(source)
    icon = _resized(img, 1024)
    flattened = Image.new("RGB", (1024, 1024), (255, 255, 255))
    flattened.paste(icon, (0, 0), icon)  # type: ignore[arg-type]
    flattened.save(appiconset_dir / "icon-1024.png", format="PNG")

    contents = {
        "images": [
            {
                "idiom": "universal",
                "platform": "ios",
                "size": "1024x1024",
                "filename": "icon-1024.png",
            }
        ],
        "info": {"author": "pythonnative", "version": 1},
    }
    (appiconset_dir / "Contents.json").write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    return True


def generate_android_icons(source: Path, res_dir: Path) -> bool:
    """Generate Android launcher icons at every density.

    Writes ``mipmap-<density>/ic_launcher.png`` and a circular
    ``ic_launcher_round.png`` for each density bucket, and removes the
    adaptive ``mipmap-anydpi-v26`` definitions so the generated PNGs are
    used directly (otherwise the template's vector adaptive icon would
    win on API 26+).

    Args:
        source: Path to the source icon image.
        res_dir: The Android ``res`` directory.

    Returns:
        ``True`` if icons were written, ``False`` if Pillow is missing.
    """
    if not pillow_available():
        return False

    img = _open_rgba(source)
    for density, size in ANDROID_LAUNCHER_DENSITIES.items():
        mip_dir = res_dir / f"mipmap-{density}"
        mip_dir.mkdir(parents=True, exist_ok=True)
        square = _resized(img, size)
        square.save(mip_dir / "ic_launcher.png", format="PNG")
        round_icon = _circular(square)
        round_icon.save(mip_dir / "ic_launcher_round.png", format="PNG")

    # Drop adaptive XML icons so the raster mipmaps above are authoritative.
    anydpi = res_dir / "mipmap-anydpi-v26"
    if anydpi.is_dir():
        shutil.rmtree(anydpi, ignore_errors=True)
    return True


def generate_ios_splash(source: Path, imageset_dir: Path) -> bool:
    """Generate an iOS ``Splash`` image set from a source image.

    Args:
        source: Path to the splash image.
        imageset_dir: The ``Splash.imageset`` directory to populate.

    Returns:
        ``True`` if the image set was written, ``False`` if Pillow is
        missing.
    """
    if not pillow_available():
        return False

    imageset_dir.mkdir(parents=True, exist_ok=True)
    img = _open_rgba(source)
    img.save(imageset_dir / "splash.png", format="PNG")
    contents = {
        "images": [{"idiom": "universal", "filename": "splash.png"}],
        "info": {"author": "pythonnative", "version": 1},
    }
    (imageset_dir / "Contents.json").write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    return True


def generate_android_splash_icon(source: Path, dest: Path, size: int = 288) -> bool:
    """Render the centered icon used by the Android 12+ splash screen.

    The Android splash screen draws this image centered on the splash
    background color. A transparent square is recommended; the default
    size (288 dp at xxxhdpi → ~864 px) matches Google's guidance.

    Args:
        source: Path to the source splash (or icon) image.
        dest: Destination PNG path.
        size: Output edge length in pixels.

    Returns:
        ``True`` if the image was written, ``False`` if Pillow is missing.
    """
    if not pillow_available():
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    img = _open_rgba(source)
    _resized(img, size).save(dest, format="PNG")
    return True


def dominant_background_color(source: Path) -> Optional[str]:
    """Best-effort estimate of a splash background color from an image.

    Samples the image's corner pixels and returns the most common one as
    a ``#RRGGBB`` hex string. Used as a default splash background when the
    config doesn't specify one.

    Args:
        source: Path to the splash image.

    Returns:
        A hex color string, or ``None`` if Pillow is missing or the
        sampling fails.
    """
    if not pillow_available():
        return None
    try:
        img = _open_rgba(source)
        width, height = img.size
        corners: List[Tuple[int, int]] = [
            (0, 0),
            (width - 1, 0),
            (0, height - 1),
            (width - 1, height - 1),
        ]
        counts: Dict[Tuple[int, int, int], int] = {}
        for x, y in corners:
            r, g, b, _a = img.getpixel((x, y))
            key = (r, g, b)
            counts[key] = counts.get(key, 0) + 1
        r, g, b = max(counts, key=lambda k: counts[k])
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return None


def has_source(path: Optional[Path]) -> bool:
    """Return whether ``path`` is a readable existing file.

    Args:
        path: A candidate asset path, or ``None``.

    Returns:
        ``True`` when the path is a file that exists on disk.
    """
    return bool(path and os.path.isfile(path))
