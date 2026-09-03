"""Cross-platform camera and gallery access.

Both entry points are coroutines: ``await Camera.take_photo()`` returns
the saved image path (a ``str``) or ``None`` if the user cancels. The
native ``Camera`` module presents ``UIImagePickerController`` (iOS) or
launches ``MediaStore.ACTION_IMAGE_CAPTURE`` / ``ACTION_PICK``
(Android) and resolves the call when the picker finishes; Python only
awaits the promise.

Example:
    ```python
    import pythonnative as pn

    async def add_photo():
        path = await pn.Camera.take_photo()
        if path is None:
            return  # user cancelled
        await save_to_album(path)
    ```
"""

from __future__ import annotations

from typing import Any, Optional

from .registry import native_module


class Camera:
    """Camera and image-picker interface (static coroutines)."""

    @staticmethod
    async def take_photo(**options: Any) -> Optional[str]:
        """Launch the device camera to capture a photo.

        Args:
            **options: Forwarded to the native module (``quality``,
                ``allow_editing``, ...). Unknown keys are ignored.

        Returns:
            The saved image path, or ``None`` if the user cancelled or
            no camera is available.
        """
        return await _launch("take_photo", options)

    @staticmethod
    async def pick_from_gallery(**options: Any) -> Optional[str]:
        """Open the system gallery picker.

        Returns:
            The selected image path, or ``None`` if the user cancelled.
        """
        return await _launch("pick_from_gallery", options)


async def _launch(method: str, options: Any) -> Optional[str]:
    try:
        result = await native_module("Camera").call_async(method, **options)
    except Exception:
        return None
    return str(result) if result else None
