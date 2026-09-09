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
    async def take_photo(*, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]:
        """Launch the device camera to capture a photo.

        Args:
            quality: JPEG compression quality from 0 to 1 on iOS. Android's
                system capture application controls its output quality.
            allow_editing: Present the iOS crop editor before saving.

        Returns:
            The saved image path, or ``None`` if the user cancelled (or
            there is no camera to present, as in the browser preview).

        Raises:
            NativeModuleError: If the picker can't be presented, for
                example because another picker is already open.
        """
        return await _launch("take_photo", {"quality": quality, "allow_editing": allow_editing})

    @staticmethod
    async def pick_from_gallery(*, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]:
        """Open the system gallery picker.

        Returns:
            The selected image path, or ``None`` if the user cancelled.

        Raises:
            NativeModuleError: If the picker can't be presented.
        """
        return await _launch("pick_from_gallery", {"quality": quality, "allow_editing": allow_editing})


async def _launch(method: str, options: Any) -> Optional[str]:
    result = await native_module("Camera").call_async(method, **options)
    return str(result) if result else None
