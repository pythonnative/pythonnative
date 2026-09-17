"""Bundled assets: images, fonts, and other files shipped inside the app.

Everything under ``app/assets/`` is copied into the native application
by ``pn build`` and synced to connected devices by ``pn start``. Code
refers to those files with [`asset`][pythonnative.asset]:

```python
import pythonnative as pn

logo = pn.asset("images/logo.png")
pn.Image(source=logo, style=pn.style(width=120, height=40))
```

An [`Asset`][pythonnative.Asset] is a small frozen value. On the wire it
becomes the URI ``asset://images/logo.png``; the native runtimes resolve
that against the dev overlay (when connected to ``pn start``) and then
the bundle, and pick the density variant (``logo@2x.png``, ``logo@3x.png``)
closest to the device scale. Python never needs to know the device's
pixel ratio or where the bundle lives.

Fonts work the same way: drop ``.ttf`` or ``.otf`` files into
``app/assets/fonts/`` and reference them by family name with
``font_family``. The family, weight, and style are read from the font
files themselves (see [`read_font_face`][pythonnative.assets.read_font_face]),
so no mapping file is needed.

The build tool and the dev server describe an asset directory with an
[`AssetManifest`][pythonnative.assets.AssetManifest]
(see [`scan`][pythonnative.assets.scan]), which lists every file, groups
density variants by base name, and carries the parsed font faces. The
native runtimes read the manifest that ships in the bundle and receive a
fresh one over the bridge whenever the dev overlay changes.
"""

from __future__ import annotations

import base64
import json
import os
import posixpath
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .fonts import FontFace, FontParseError, read_font_face, weight_from_name

__all__ = [
    "ASSETS_DIR",
    "ASSET_SCHEME",
    "Asset",
    "AssetManifest",
    "FontFace",
    "FontParseError",
    "MANIFEST_NAME",
    "asset",
    "assets_roots",
    "bump_generation",
    "choose_variant",
    "configure_native",
    "font_faces",
    "generation",
    "is_asset_uri",
    "normalize_path",
    "read_font_face",
    "scan",
    "split_variant",
    "weight_from_name",
    "write_manifest",
]

ASSETS_DIR = "assets"
"""Directory under ``app/`` that holds runtime assets."""

ASSET_SCHEME = "asset://"
"""URI scheme the native runtimes resolve against the bundled assets."""

MANIFEST_NAME = "pn_assets.json"
"""File name of the manifest the builder writes next to staged assets."""

FONT_SUFFIXES = (".ttf", ".otf", ".ttc")
"""File suffixes scanned for font faces."""

_VARIANT = re.compile(r"^(?P<stem>.+?)@(?P<scale>\d+(?:\.\d+)?)x$")


# ----------------------------------------------------------------------
# Paths and URIs
# ----------------------------------------------------------------------


def normalize_path(path: str) -> str:
    """Return ``path`` as a clean, asset-relative POSIX path.

    Accepts ``"images/logo.png"``, ``"./images/logo.png"``, an
    ``asset://`` URI, or Windows separators; rejects absolute paths,
    ``..`` segments, and empty input.

    Raises:
        ValueError: If the path can't name a file under ``app/assets/``.
    """
    if not isinstance(path, str):
        raise ValueError(f"asset path must be a string, got {type(path).__name__}")
    text = path.strip().replace("\\", "/")
    if text.startswith(ASSET_SCHEME):
        text = text[len(ASSET_SCHEME) :]
    if not text:
        raise ValueError("asset path is empty")
    if text.startswith("/"):
        raise ValueError(f"asset path must be relative to app/assets/: {path!r}")
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts:
        raise ValueError("asset path is empty")
    if any(part == ".." for part in parts):
        raise ValueError(f"asset path may not contain '..': {path!r}")
    return "/".join(parts)


def is_asset_uri(value: Any) -> bool:
    """Whether ``value`` is an ``asset://`` URI string."""
    return isinstance(value, str) and value.startswith(ASSET_SCHEME)


def split_variant(path: str) -> Tuple[str, float]:
    """Split ``"images/logo@2x.png"`` into ``("images/logo.png", 2.0)``.

    Paths without a density suffix return scale ``1.0`` and themselves.
    """
    directory, name = posixpath.split(path)
    stem, ext = posixpath.splitext(name)
    match = _VARIANT.match(stem)
    if match is None:
        return path, 1.0
    base = match.group("stem") + ext
    return (posixpath.join(directory, base) if directory else base), float(match.group("scale"))


def choose_variant(variants: Mapping[float, str], scale: float) -> Optional[str]:
    """Pick the variant path best suited to a device ``scale``.

    Preference order: an exact match, the nearest variant above ``scale``
    (so images are downsampled rather than upsampled), then the largest
    available. Returns ``None`` when ``variants`` is empty.
    """
    if not variants:
        return None
    if scale in variants:
        return variants[scale]
    above = sorted(key for key in variants if key > scale)
    if above:
        return variants[above[0]]
    return variants[max(variants)]


# ----------------------------------------------------------------------
# Asset values
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Asset:
    """A file under ``app/assets/``, addressed by its relative path.

    Build one with [`asset`][pythonnative.asset]. Assets compare and hash
    by path, so they're safe as dict keys, in ``StyleSheet`` values, and
    as ``use_effect`` dependencies.

    Attributes:
        path: The normalized path relative to ``app/assets/``, using
            forward slashes (``"images/logo.png"``).
    """

    path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", normalize_path(self.path))

    @property
    def uri(self) -> str:
        """The ``asset://`` URI the native runtimes resolve."""
        return ASSET_SCHEME + self.path

    @property
    def name(self) -> str:
        """The file name without directories."""
        return posixpath.basename(self.path)

    @property
    def suffix(self) -> str:
        """The file extension, including the dot (``".png"``)."""
        return posixpath.splitext(self.path)[1]

    def __str__(self) -> str:
        return self.uri

    def read_bytes(self) -> bytes:
        """Return the file's contents.

        Looks in the dev overlay and the bundled ``app/assets/`` directory
        first; on Android, where bundled assets live inside the APK, the
        native ``Assets`` module reads them.

        Raises:
            FileNotFoundError: If no copy of the asset can be found.
        """
        for root in assets_roots():
            candidate = root / self.path
            if candidate.is_file():
                return candidate.read_bytes()
        from ..bridge import has_transport

        if has_transport():
            from ..native_modules.registry import NativeModuleError, native_module

            try:
                encoded = native_module("Assets").call("read", path=self.path)
            except NativeModuleError as exc:
                raise FileNotFoundError(f"asset not found: {self.path} ({exc.message})") from exc
            if encoded is not None:
                return base64.b64decode(encoded)
        raise FileNotFoundError(f"asset not found: {self.path} (looked under {[str(r) for r in assets_roots()]})")

    def read_text(self, encoding: str = "utf-8") -> str:
        """Return the file's contents decoded as text."""
        return self.read_bytes().decode(encoding)

    def exists(self) -> bool:
        """Whether some copy of the asset (overlay, bundle, or APK) exists."""
        if any((root / self.path).is_file() for root in assets_roots()):
            return True
        from ..bridge import has_transport

        if has_transport():
            from ..native_modules.registry import NativeModuleError, native_module

            try:
                return bool(native_module("Assets").call("exists", path=self.path))
            except NativeModuleError:
                return False
        return False

    @classmethod
    def __native_schema__(cls) -> Dict[str, Any]:
        """Assets cross the bridge as their URI string."""
        return {"type": "string"}

    def __native_value__(self) -> str:
        return self.uri


def asset(path: str) -> Asset:
    """Reference a file bundled under ``app/assets/``.

    Args:
        path: Path relative to ``app/assets/``, such as
            ``"images/logo.png"``. Density variants (``logo@2x.png``) are
            picked automatically; always name the base file.

    Returns:
        An [`Asset`][pythonnative.Asset].

    Raises:
        ValueError: If ``path`` is absolute, empty, or escapes the assets
            directory.

    Example:
        ```python
        pn.Image(source=pn.asset("images/logo.png"))
        pn.Text("Hi", style=pn.style(font_family="Poppins"))  # app/assets/fonts/Poppins-*.ttf
        ```
    """
    return Asset(path)


# ----------------------------------------------------------------------
# Manifest
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AssetManifest:
    """Everything a runtime needs to know about one assets directory.

    Attributes:
        files: Every asset path, sorted.
        variants: ``base path -> {scale string -> variant path}`` for
            every image with density variants (and for base images, so a
            lookup is one dictionary hit).
        fonts: The font faces found under ``fonts/`` (or anywhere in the
            directory with a font suffix).
    """

    files: Tuple[str, ...] = ()
    variants: Dict[str, Dict[str, str]] = field(default_factory=dict)
    fonts: Tuple[FontFace, ...] = ()

    def resolve(self, path: str, scale: float = 1.0) -> Optional[str]:
        """Return the variant of ``path`` that best matches ``scale``.

        Args:
            path: An asset path or ``asset://`` URI (a base name; a
                variant name is normalized to its base first).
            scale: The device pixel ratio.

        Returns:
            The path to load, or ``None`` if the manifest has no such file.
        """
        base, _ = split_variant(normalize_path(path))
        group = self.variants.get(base)
        if group:
            return choose_variant({float(key): value for key, value in group.items()}, scale)
        return base if base in self.files else None

    def faces(self, family: str) -> List[FontFace]:
        """Every face of ``family`` (case-insensitive)."""
        wanted = family.strip().lower()
        return [face for face in self.fonts if face.family.lower() == wanted]

    def to_dict(self) -> Dict[str, Any]:
        """A JSON-ready form (what the builder writes and the bridge sends)."""
        return {
            "version": 1,
            "files": list(self.files),
            "variants": {base: dict(group) for base, group in sorted(self.variants.items())},
            "fonts": [
                {
                    "family": face.family,
                    "weight": face.weight,
                    "italic": face.italic,
                    "postscript_name": face.postscript_name,
                    "path": face.path,
                }
                for face in self.fonts
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssetManifest":
        """Rebuild a manifest written by [`to_dict`][pythonnative.assets.AssetManifest.to_dict]."""
        return cls(
            files=tuple(str(path) for path in data.get("files", ())),
            variants={
                str(base): {str(k): str(v) for k, v in group.items()}
                for base, group in data.get("variants", {}).items()
            },
            fonts=tuple(
                FontFace(
                    family=str(face["family"]),
                    weight=int(face.get("weight", 400)),
                    italic=bool(face.get("italic", False)),
                    postscript_name=str(face.get("postscript_name", "")),
                    path=str(face["path"]),
                )
                for face in data.get("fonts", ())
            ),
        )

    def dumps(self) -> str:
        """The manifest as pretty JSON."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def _scale_key(scale: float) -> str:
    return str(int(scale)) if float(scale).is_integer() else repr(scale)


def scan(root: Union[str, Path], *, log: Any = None) -> AssetManifest:
    """Describe the assets directory at ``root``.

    Hidden files, editor swap files, and ``__pycache__`` are skipped. Font
    files that can't be parsed are reported through ``log`` (when given)
    and omitted, so one broken font never breaks a build.

    Args:
        root: The ``app/assets/`` directory. A missing directory yields an
            empty manifest.
        log: Optional callable that receives warning strings.
    """
    root = Path(root)
    files: List[str] = []
    if root.is_dir():
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "__pycache__")
            for name in sorted(filenames):
                if name.startswith(".") or name.endswith(("~", ".swp", ".tmp")) or name == MANIFEST_NAME:
                    continue
                rel = Path(dirpath, name).relative_to(root).as_posix()
                files.append(rel)
    files.sort()
    variants: Dict[str, Dict[str, str]] = {}
    for rel in files:
        base, scale = split_variant(rel)
        if scale != 1.0 or base != rel or posixpath.splitext(rel)[1].lower() in _IMAGE_SUFFIXES:
            variants.setdefault(base, {})[_scale_key(scale)] = rel
    fonts: List[FontFace] = []
    for rel in files:
        if rel.lower().endswith(FONT_SUFFIXES):
            try:
                fonts.append(read_font_face(root / rel, path=rel))
            except (FontParseError, OSError) as exc:
                if log is not None:
                    log(f"Skipping font {rel}: {exc}")
    return AssetManifest(files=tuple(files), variants=variants, fonts=tuple(fonts))


_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"})


def write_manifest(root: Union[str, Path], *, log: Any = None) -> AssetManifest:
    """Scan ``root`` and write ``pn_assets.json`` inside it.

    The build tool calls this on the staged copy of ``app/assets/`` so
    the native runtimes can resolve variants and register fonts without
    listing the bundle at startup. Returns the manifest that was written.
    A missing ``root`` is created so the bundle always carries a manifest.
    """
    root = Path(root)
    manifest = scan(root, log=log)
    root.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST_NAME).write_text(manifest.dumps(), encoding="utf-8")
    return manifest


# ----------------------------------------------------------------------
# Runtime roots
# ----------------------------------------------------------------------


def assets_roots() -> List[Path]:
    """Directories that may hold ``app/assets/`` files, most specific first.

    The dev overlay (when ``pn start`` is connected) comes before the
    bundled or checked-out ``app/`` package. On Android the bundled copy
    isn't a directory at all (it lives in the APK), so only the overlay is
    listed there; [`Asset.read_bytes`][pythonnative.assets.Asset.read_bytes] falls
    back to the native ``Assets`` module.
    """
    roots: List[Path] = []
    from ..hot_reload import overlay_root

    overlay = overlay_root()
    if overlay:
        roots.append(Path(overlay) / "app" / ASSETS_DIR)
    override = os.environ.get("PN_ASSETS_ROOT")
    if override:
        roots.append(Path(override))
    for bundled in _bundled_roots(exclude=overlay):
        if bundled not in roots:
            roots.append(bundled)
    return roots


def _bundled_roots(*, exclude: Optional[str]) -> List[Path]:
    """Every ``app/assets/`` directory reachable from ``sys.path`` (bundle or checkout).

    The overlay shadows the bundled ``app`` package on ``sys.path``, so
    this walks the path entries directly instead of asking the import
    system where ``app`` lives.
    """
    import sys

    found: List[Path] = []
    for entry in sys.path:
        if not entry or (exclude and os.path.abspath(entry) == os.path.abspath(exclude)):
            continue
        candidate = Path(entry) / "app" / ASSETS_DIR
        if candidate.is_dir() and candidate not in found:
            found.append(candidate)
    return found


def font_faces() -> Tuple[FontFace, ...]:
    """The font faces bundled with the app.

    Readable roots (the dev overlay, a checkout, the iOS bundle) are
    scanned directly. On Android the bundled ``app/assets/`` lives inside
    the APK rather than on disk, so its faces come from the manifest the
    build wrote, read through the native ``Assets`` module.
    """
    faces: List[FontFace] = []
    seen = set()

    def add(face: FontFace) -> None:
        key = (face.family.lower(), face.weight, face.italic)
        if key not in seen:
            seen.add(key)
            faces.append(face)

    for root in assets_roots():
        for face in scan(root).fonts:
            add(face)
    if not _bundled_roots(exclude=None):
        for face in _native_manifest().fonts:
            add(face)
    return tuple(faces)


def _native_manifest() -> AssetManifest:
    """The bundled manifest as the native runtime sees it, or an empty one.

    Used when the bundle isn't a directory Python can list (Android).
    """
    from ..bridge import has_transport

    if not has_transport():
        return AssetManifest()
    from ..native_modules.registry import NativeModuleError, native_module

    try:
        encoded = native_module("Assets").call("read", path=MANIFEST_NAME)
    except NativeModuleError:
        return AssetManifest()
    if not encoded:
        return AssetManifest()
    try:
        return AssetManifest.from_dict(json.loads(base64.b64decode(encoded)))
    except (ValueError, KeyError, TypeError):
        return AssetManifest()


# ----------------------------------------------------------------------
# Dev-time coordination with the native runtime
# ----------------------------------------------------------------------

_generation = 0
_generation_lock = threading.Lock()


def generation() -> int:
    """A counter bumped whenever synced assets change (for caches)."""
    return _generation


def bump_generation() -> int:
    """Invalidate asset caches after a sync; returns the new generation."""
    global _generation
    with _generation_lock:
        _generation += 1
        return _generation


def configure_native(paths: Optional[Iterable[str]] = None) -> bool:
    """Tell the native runtime about the dev overlay's assets.

    Called by the dev client after a sync and by ``bootstrap.start`` in
    debug builds. It scans ``<overlay>/app/assets/`` and sends the
    resulting manifest to the native ``Assets`` module, which then
    resolves ``asset://`` URIs against the overlay before the bundle and
    registers any overlay fonts.

    Args:
        paths: The synced paths (``"app/assets/..."``) when known. When
            given and none of them is under ``app/assets/``, nothing is
            sent.

    Returns:
        ``True`` if a manifest was pushed.
    """
    if paths is not None and not any(_is_asset_path(path) for path in paths):
        return False
    from ..bridge import has_transport
    from ..hot_reload import overlay_root

    overlay = overlay_root()
    if not overlay or not has_transport():
        return False
    root = Path(overlay) / "app" / ASSETS_DIR
    manifest = scan(root)
    bump_generation()
    from ..native_modules.registry import NativeModuleError, native_module

    try:
        native_module("Assets").call("configure", overlay=str(root), manifest=manifest)
    except NativeModuleError as exc:
        from .. import diagnostics

        diagnostics.warn(f"Assets.configure failed: {exc}")
        return False
    return True


def _is_asset_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith(f"app/{ASSETS_DIR}/")


def manifest_for_sync(files: Sequence[str]) -> List[str]:
    """Filter a synced path list to the asset paths (helper for the dev client)."""
    return [path for path in files if _is_asset_path(path)]
