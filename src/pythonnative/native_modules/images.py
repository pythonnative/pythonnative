"""Image utilities backed by the native image pipeline.

[`Images`][pythonnative.Images] exposes the parts of the platform image
loader that don't fit on the [`Image`][pythonnative.Image] element:
measuring an image before laying it out, warming the cache, and clearing
it. Every method takes the same ``source`` values ``Image`` does (a
bundled [`Asset`][pythonnative.Asset], a URL, a ``data:`` URI, or a file
path) and runs off the main thread natively.

Example:
    ```python
    import pythonnative as pn

    size = await pn.Images.get_size(pn.asset("images/hero.jpg"))
    await pn.Images.prefetch("https://example.com/banner.png")
    ```

Off device (tests, ``pn preview``) sizes are read from the file headers
of PNG, JPEG, GIF, WebP, and BMP files, and ``prefetch`` is a no-op that
reports whether the source is reachable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from ..assets import Asset
from .registry import native_module

__all__ = ["ImageSize", "Images"]


@dataclass(frozen=True)
class ImageSize:
    """Logical dimensions of an image, in points.

    Attributes:
        width: Width in logical points (pixels divided by the asset's scale).
        height: Height in logical points.
    """

    width: float
    height: float


def _uri(source: Union[str, Asset]) -> str:
    if isinstance(source, Asset):
        return source.uri
    text = str(source)
    if not text:
        raise ValueError("image source is empty")
    return text


class Images:
    """Measure, prefetch, and clear images through the native loader.

    Raises:
        NativeModuleError: If the native module reports a failure (for
            instance an unreachable URL or a missing asset).
    """

    @staticmethod
    async def get_size(source: Union[str, Asset]) -> ImageSize:
        """Return the logical size of ``source`` without displaying it.

        Bundled assets report the size of their ``1x`` variant (the
        variant's pixel size divided by its scale), so the result is
        the size the image would take in layout.
        """
        value: Any = await native_module("Images").call_async("get_size", uri=_uri(source))
        if isinstance(value, ImageSize):
            return value
        return ImageSize(width=float(value["width"]), height=float(value["height"]))

    @staticmethod
    async def prefetch(source: Union[str, Asset]) -> bool:
        """Download and cache ``source`` ahead of time; ``True`` on success."""
        return bool(await native_module("Images").call_async("prefetch", uri=_uri(source)))

    @staticmethod
    def clear_cache() -> None:
        """Drop the in-memory and on-disk image caches."""
        native_module("Images").call("clear_cache")
