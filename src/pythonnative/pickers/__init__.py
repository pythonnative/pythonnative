"""Let the user choose photos, videos, and documents with the system pickers.

Enable it in ``pythonnative.toml``. The pickers themselves need no permission:
the system shows them in its own process, and the app only gets what the user
chose. Declare ``photo_library`` only if you also read the library directly.

```toml
[plugins]
use = ["pickers"]
```

Example:
    ```python
    from pythonnative.pickers import pick_documents, pick_images

    async def add_photos() -> None:
        for photo in await pick_images(limit=5):
            await upload(photo.path, photo.mime_type)

    async def attach_pdf() -> None:
        files = await pick_documents(types=["application/pdf"])
        if files:
            print(files[0].name, files[0].size)
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Sequence

from ..native_modules.registry import native_module
from ..sdk.plugin import plugin_module

__all__ = ["PickedFile", "pick_documents", "pick_images", "pick_videos"]


@dataclass(frozen=True)
class PickedFile:
    """One file the user chose, already copied somewhere the app can read.

    Attributes:
        path: The copy in the app's cache directory, which the system may clear
            when it runs low on space, so move what you want to keep. In the
            browser preview, this is a ``blob:`` URL.
        name: The name the file had, for display.
        mime_type: Its MIME type, or ``application/octet-stream`` when unknown.
        size: Its size in bytes.
    """

    path: str
    name: str
    mime_type: str
    size: int


class _PickersService(Protocol):
    async def pick_images(self, *, limit: int = 1, quality: float = 0.9) -> List[PickedFile]: ...

    async def pick_videos(self, *, limit: int = 1) -> List[PickedFile]: ...

    async def pick_documents(
        self, *, types: Optional[List[str]] = None, multiple: bool = False
    ) -> List[PickedFile]: ...


class _Fallback:
    """No picker off device: every call looks like the user canceled."""

    def pick_images(self, *, limit: int = 1, quality: float = 0.9) -> List[PickedFile]:
        return []

    def pick_videos(self, *, limit: int = 1) -> List[PickedFile]:
        return []

    def pick_documents(self, *, types: Optional[List[str]] = None, multiple: bool = False) -> List[PickedFile]:
        return []


plugin_module("Pickers", _PickersService, plugin="pickers", fallback=_Fallback, browser=True)


def _limit(limit: int) -> int:
    if limit < 0:
        raise ValueError(f"limit must be 0 or more, got {limit!r}")
    return int(limit)


async def pick_images(limit: int = 1, quality: float = 0.9) -> List[PickedFile]:
    """Open the system photo picker.

    Args:
        limit: The most photos the user can choose, or 0 for as many as the
            system allows. iOS 13 can only ever choose one. Where Android falls
            back to the document picker, which can't enforce a number, extra
            choices are dropped.
        quality: JPEG quality from 0 to 1. Below 1, photos are re-encoded as
            JPEG, which also turns HEIC into something every library can read.
            PNG and GIF keep their bytes, to preserve transparency and animation.
            At 1, every photo keeps its original bytes.

    Returns:
        The chosen photos, in the order chosen. An empty list means the user
        canceled.

    Raises:
        NativeModuleError: With the code ``busy`` when a picker is already open.
    """
    if not 0.0 <= quality <= 1.0:
        raise ValueError(f"quality must be between 0 and 1, got {quality!r}")
    result: List[PickedFile] = await native_module("Pickers").call_async(
        "pick_images", limit=_limit(limit), quality=float(quality)
    )
    return result


async def pick_videos(limit: int = 1) -> List[PickedFile]:
    """Open the system photo picker, showing only videos.

    Args:
        limit: The most videos the user can choose, or 0 for as many as the
            system allows. iOS 13 can only ever choose one.

    Returns:
        The chosen videos, with their original bytes. An empty list means the
        user canceled.

    Raises:
        NativeModuleError: With the code ``busy`` when a picker is already open.
    """
    result: List[PickedFile] = await native_module("Pickers").call_async("pick_videos", limit=_limit(limit))
    return result


async def pick_documents(types: Optional[Sequence[str]] = None, multiple: bool = False) -> List[PickedFile]:
    """Open the system document picker.

    Args:
        types: The MIME types to offer, such as ``"application/pdf"`` or
            ``"image/*"``. ``None`` offers every file.
        multiple: Let the user choose more than one.

    Returns:
        The chosen files. An empty list means the user canceled.

    Raises:
        NativeModuleError: With the code ``busy`` when a picker is already open.
    """
    if isinstance(types, str):
        raise TypeError("types must be a list of MIME types, not a single string")
    wanted = None if types is None else [str(item) for item in types]
    result: List[PickedFile] = await native_module("Pickers").call_async(
        "pick_documents", types=wanted, multiple=bool(multiple)
    )
    return result
