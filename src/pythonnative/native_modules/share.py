"""Present the system share sheet.

[`Share.share`][pythonnative.Share] is a coroutine that opens
``UIActivityViewController`` (iOS) or an ``ACTION_SEND`` chooser
(Android) through the native ``Share`` module and resolves to ``True``
once the user completes a share or ``False`` if they dismiss it.

Example:
    ```python
    import pythonnative as pn

    async def share_link():
        await pn.Share.share(
            message="Check out PythonNative!",
            url="https://example.com",
        )
    ```
"""

from __future__ import annotations

from typing import Optional

from .registry import native_module


class Share:
    """System share-sheet interface."""

    @staticmethod
    async def share(
        *,
        message: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        """Open the share sheet with ``message`` / ``url``.

        Args:
            message: Text body to share.
            url: A URL to share (combined with ``message`` on Android).
            title: Chooser title (Android) / subject (iOS mail).

        Returns:
            ``True`` if the user completed a share, ``False`` if they
            dismissed the sheet or the platform has no share UI (desktop).

        Raises:
            NativeModuleError: If the sheet could not be presented.
        """
        return bool(await native_module("Share").call_async("share", message=message, url=url, title=title))
