"""Cross-platform camera and gallery access.

Both entry points are coroutines: ``await Camera.take_photo()`` returns
the saved image path (a ``str``) or ``None`` if the user cancels.
Internally each call instantiates a fresh native delegate / activity
request and bridges its completion onto the PythonNative asyncio
runtime, so callers don't have to know whether the picker is backed by
``UIImagePickerController`` (iOS) or
``Intent(MediaStore.ACTION_IMAGE_CAPTURE)`` (Android).

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

import asyncio
from typing import Any, Callable, Dict, Optional

from ..runtime import resolve_future
from ..utils import IS_ANDROID, IS_IOS

# Retain pool keyed by ``id(delegate)`` so iOS UIImagePickerController
# delegates aren't garbage-collected before the picker calls back.
_pending_delegates: Dict[int, Any] = {}


class Camera:
    """Camera and image-picker interface.

    All methods are static coroutines. They dispatch to the iOS or
    Android implementation at call time based on the runtime
    platform.
    """

    @staticmethod
    async def take_photo(**options: Any) -> Optional[str]:
        """Launch the device camera to capture a photo.

        Args:
            **options: Reserved for platform-specific tuning. Currently
                unused; future kwargs (e.g., ``quality``,
                ``flash_mode``) will land here.

        Returns:
            The saved image path, or ``None`` if the user cancelled or
            no camera is available.
        """
        return await _launch("camera", **options)

    @staticmethod
    async def pick_from_gallery(**options: Any) -> Optional[str]:
        """Open the system gallery picker.

        Args:
            **options: Reserved for platform-specific tuning.

        Returns:
            The selected image path, or ``None`` if the user cancelled.
        """
        return await _launch("gallery", **options)


async def _launch(source: str, **options: Any) -> Optional[str]:
    del options
    loop = asyncio.get_running_loop()
    future: asyncio.Future[Optional[str]] = loop.create_future()

    def _on_result(path: Optional[str]) -> None:
        resolve_future(future, path)

    if IS_ANDROID:
        _android_launch_picker(_on_result, source=source)
    elif IS_IOS:
        _ios_launch_picker(_on_result, source=source)
    else:
        resolve_future(future, None)

    return await future


# ======================================================================
# iOS implementation: UIImagePickerControllerDelegate
# ======================================================================


def _ios_launch_picker(on_result: Callable[[Optional[str]], None], source: str) -> None:
    try:
        from rubicon.objc import SEL, ObjCClass, objc_method

        UIImagePickerController = ObjCClass("UIImagePickerController")
        NSObject = ObjCClass("NSObject")

        class _PNImagePickerDelegate(NSObject):  # type: ignore[misc,valid-type]
            _callback: Optional[Callable[[Optional[str]], None]] = None
            _picker: Any = None

            @objc_method
            def imagePickerController_didFinishPickingMediaWithInfo_(self, picker: Any, info: Any) -> None:
                path = _ios_extract_path(info)
                try:
                    picker.dismissViewControllerAnimated_completion_(True, None)
                except Exception:
                    pass
                cb = self._callback
                self._callback = None
                _pending_delegates.pop(id(self), None)
                if cb is not None:
                    try:
                        cb(path)
                    except Exception:
                        pass

            @objc_method
            def imagePickerControllerDidCancel_(self, picker: Any) -> None:
                try:
                    picker.dismissViewControllerAnimated_completion_(True, None)
                except Exception:
                    pass
                cb = self._callback
                self._callback = None
                _pending_delegates.pop(id(self), None)
                if cb is not None:
                    try:
                        cb(None)
                    except Exception:
                        pass

        delegate = _PNImagePickerDelegate.new()
        delegate._callback = on_result
        _pending_delegates[id(delegate)] = delegate

        picker = UIImagePickerController.alloc().init()
        picker.setSourceType_(1 if source == "camera" else 0)
        picker.setDelegate_(delegate)

        UIApplication = ObjCClass("UIApplication")
        top = UIApplication.sharedApplication.keyWindow.rootViewController
        while top is not None and top.presentedViewController is not None:
            top = top.presentedViewController
        if top is not None:
            top.presentViewController_animated_completion_(picker, True, None)
        else:
            _pending_delegates.pop(id(delegate), None)
            on_result(None)

        # Reference SEL/objc_method so the lint pass keeps the import —
        # they're needed for the delegate class above.
        _ = (SEL, objc_method)
    except Exception:
        on_result(None)


def _ios_extract_path(info: Any) -> Optional[str]:
    """Best-effort extraction of an image path from picker ``info``."""
    try:
        url = info.objectForKey_("UIImagePickerControllerImageURL")
        if url is not None:
            try:
                return str(url.absoluteString)
            except Exception:
                try:
                    return str(url.path)
                except Exception:
                    pass
        image = info.objectForKey_("UIImagePickerControllerOriginalImage")
        if image is not None:
            return _ios_write_image_to_tmp(image)
    except Exception:
        return None
    return None


def _ios_write_image_to_tmp(image: Any) -> Optional[str]:
    """Encode a UIImage to JPEG and write it to NSCachesDirectory."""
    try:
        from rubicon.objc import ObjCClass

        try:
            data = image.jpegDataWithCompressionQuality_(0.85)
        except Exception:
            return None
        if data is None:
            return None
        NSString = ObjCClass("NSString")
        NSFileManager = ObjCClass("NSFileManager")
        manager = NSFileManager.defaultManager
        urls = manager.URLsForDirectory_inDomains_(13, 1)  # NSCachesDirectory, NSUserDomainMask
        if urls is None or urls.count == 0:
            return None
        cache_dir = urls.firstObject
        import time as _time

        filename = NSString.stringWithFormat_("pn-camera-%d.jpg", int(_time.time() * 1000))
        target = cache_dir.URLByAppendingPathComponent_(filename)
        if not data.writeToURL_atomically_(target, True):
            return None
        try:
            return str(target.path)
        except Exception:
            return str(target.absoluteString)
    except Exception:
        return None


# ======================================================================
# Android implementation: ActivityResultLauncher / startActivityForResult
# ======================================================================


_android_pending_results: Dict[int, Callable[[Optional[str]], None]] = {}
_android_next_request_code: int = 50001


def _android_next_code() -> int:
    global _android_next_request_code
    code = _android_next_request_code
    _android_next_request_code += 1
    return code


def _android_launch_picker(on_result: Callable[[Optional[str]], None], source: str) -> None:
    try:
        from java import jclass

        from ..utils import get_android_context

        Intent = jclass("android.content.Intent")
        MediaStore = jclass("android.provider.MediaStore")
        ctx = get_android_context()

        if source == "camera":
            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        else:
            intent = Intent(Intent.ACTION_PICK)
            intent.setType("image/*")

        # ``startActivityForResult`` requires the host to be an
        # Activity; in unit tests we may only have an Application
        # context, in which case we fall back to ``startActivity`` and
        # report ``None`` (the caller has no Activity to dispatch the
        # result back through).
        Activity = jclass("android.app.Activity")
        if not Activity.isInstance(ctx):
            ctx.startActivity(intent)
            on_result(None)
            return

        request_code = _android_next_code()
        _android_pending_results[request_code] = on_result
        try:
            ctx.startActivityForResult(intent, request_code)
        except Exception:
            _android_pending_results.pop(request_code, None)
            on_result(None)
    except Exception:
        on_result(None)


def deliver_android_activity_result(request_code: int, result_code: int, data: Any) -> bool:
    """Forward an Activity result to the registered camera coroutine.

    The host Activity should call this from ``onActivityResult`` so
    the pending
    [`take_photo`][pythonnative.native_modules.camera.Camera.take_photo]
    /
    [`pick_from_gallery`][pythonnative.native_modules.camera.Camera.pick_from_gallery]
    awaitable receives a path. Returns ``True`` if a Python callback
    was invoked (so the host can short-circuit further handlers).
    """
    cb = _android_pending_results.pop(request_code, None)
    if cb is None:
        return False
    path: Optional[str] = None
    try:
        if result_code == -1 and data is not None:  # RESULT_OK
            uri = data.getData()
            if uri is not None:
                path = str(uri)
            else:
                try:
                    extras = data.getExtras()
                    if extras is not None:
                        thumb = extras.get("data")
                        if thumb is not None:
                            path = _android_write_bitmap_to_cache(thumb)
                except Exception:
                    pass
    except Exception:
        path = None
    try:
        cb(path)
    except Exception:
        pass
    return True


def _android_write_bitmap_to_cache(bitmap: Any) -> Optional[str]:
    """Persist a Bitmap to the app cache directory and return its path."""
    try:
        from java import jclass

        from ..utils import get_android_context

        ctx = get_android_context()
        cache_dir = ctx.getCacheDir()
        File = jclass("java.io.File")
        FileOutputStream = jclass("java.io.FileOutputStream")
        Bitmap = jclass("android.graphics.Bitmap")
        import time as _time

        target = File(cache_dir, f"pn-camera-{int(_time.time() * 1000)}.jpg")
        out = FileOutputStream(target)
        try:
            bitmap.compress(Bitmap.CompressFormat.JPEG, 85, out)
        finally:
            out.close()
        return str(target.getAbsolutePath())
    except Exception:
        return None
