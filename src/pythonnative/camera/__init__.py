"""The device camera: the system capture screen, or a live preview you control.

Enable it in ``pythonnative.toml``. Declare ``microphone`` as well if you
record video with sound:

```toml
[plugins]
use = ["camera"]

[permissions]
camera = "Scan receipts with your camera."
microphone = "Record sound with your videos."
```

Example:
    ```python
    import pythonnative as pn
    from pythonnative.camera import Barcode, Camera, CameraView

    async def snap() -> None:
        path = await Camera.take_photo(quality=0.8)
        if path is not None:
            await upload(path)

    @pn.component
    def Scanner() -> pn.Node:
        camera = pn.use_ref()

        async def capture() -> None:
            photo = await camera.current.take_picture(quality=0.8)
            print(photo.path, photo.width, photo.height)

        def scanned(barcode: Barcode) -> None:
            print(barcode.type, barcode.data)

        return pn.Column(
            CameraView(
                ref=camera,
                barcode_types=["qr", "ean13"],
                on_barcode=scanned,
                style=pn.style(flex=1),
            ),
            pn.Button("Capture", on_press=capture),
        )
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Callable, List, Literal, Optional, Protocol, Sequence

from ..element import Element, Node
from ..handles import HANDLE_TYPES, ViewHandle
from ..hooks import Ref
from ..native_modules.registry import native_module
from ..sdk.plugin import plugin_component, plugin_module
from ..sdk.schema import NativeField
from ..style import StyleProp

__all__ = [
    "Barcode",
    "BarcodeType",
    "Camera",
    "CameraError",
    "CameraFacing",
    "CameraFlash",
    "CameraView",
    "CameraViewHandle",
    "CameraViewProps",
    "Photo",
    "VideoRecording",
]

CameraFacing = Literal["back", "front"]
"""Which lens a [`CameraView`][pythonnative.camera.CameraView] uses."""

CameraFlash = Literal["off", "on", "auto", "torch"]
"""``on`` and ``auto`` fire when a picture is taken; ``torch`` stays lit."""

BarcodeType = Literal[
    "aztec",
    "codabar",
    "code128",
    "code39",
    "code93",
    "data_matrix",
    "ean13",
    "ean8",
    "itf14",
    "pdf417",
    "qr",
    "upc_a",
    "upc_e",
]
"""A barcode symbology. ``codabar`` needs iOS 15.4 or later."""


@dataclass(frozen=True)
class Photo:
    """A picture taken by a [`CameraView`][pythonnative.camera.CameraView].

    Attributes:
        path: The JPEG in the app's cache directory.
        width: Pixels across, as the picture displays.
        height: Pixels down, as the picture displays.
    """

    path: str
    width: int
    height: int


@dataclass(frozen=True)
class VideoRecording:
    """A video recorded by a [`CameraView`][pythonnative.camera.CameraView].

    Attributes:
        path: The video file in the app's cache directory: QuickTime
            (``.mov``) on iOS, MPEG-4 (``.mp4``) on Android, and a ``blob:``
            URL in the browser preview.
        duration: Seconds recorded.
    """

    path: str
    duration: float


@dataclass(frozen=True)
class Barcode:
    """A barcode a [`CameraView`][pythonnative.camera.CameraView] saw.

    Attributes:
        type: Its symbology.
        data: The decoded text.
    """

    type: BarcodeType
    data: str


@dataclass(frozen=True)
class CameraError:
    """Why a [`CameraView`][pythonnative.camera.CameraView] can't show the camera.

    Attributes:
        code: ``unavailable`` when the device has no such camera (the iOS
            simulator has none at all), ``permission_denied`` when the user
            refused, or ``capture_failed`` when the session stopped working.
        message: A description for logs, not for end users.
    """

    code: str
    message: str


@dataclass(frozen=True)
class CameraViewProps:
    """Props of [`CameraView`][pythonnative.camera.CameraView], which documents them."""

    facing: CameraFacing = "back"
    flash: CameraFlash = "off"
    zoom: float = 1.0
    barcode_types: Optional[List[BarcodeType]] = None
    on_barcode: Optional[Callable[[Barcode], Any]] = None
    on_ready: Optional[Callable[[], Any]] = None
    on_error: Optional[Callable[[CameraError], Any]] = None
    # Bare `NativeField()` keeps these schemas identical to `View`'s. A difference
    # would take the shared getters off `PNViewProps`, which `ViewStyler` needs.
    accessibility_label: Annotated[Optional[str], NativeField()] = None
    test_id: Annotated[Optional[str], NativeField()] = None


class _CameraService(Protocol):
    async def take_photo(self, *, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]: ...

    async def take_picture(self, *, tag: int, quality: float = 0.9) -> Photo: ...

    async def start_recording(self, *, tag: int, audio: bool = True) -> None: ...

    async def stop_recording(self, *, tag: int) -> VideoRecording: ...


class _Fallback:
    """No camera off device: the system screen reports a cancel, and captures come back empty."""

    def take_photo(self, *, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]:
        return None

    def take_picture(self, *, tag: int, quality: float = 0.9) -> Photo:
        return Photo(path="", width=0, height=0)

    def start_recording(self, *, tag: int, audio: bool = True) -> None:
        del tag, audio

    def stop_recording(self, *, tag: int) -> VideoRecording:
        return VideoRecording(path="", duration=0.0)


plugin_module("Camera", _CameraService, plugin="camera", fallback=_Fallback, browser=True)

_camera_view = plugin_component("CameraView", CameraViewProps, plugin="camera", measurement="container")


class CameraViewHandle(ViewHandle):
    """Handle for [`CameraView`][pythonnative.camera.CameraView], published on its ``ref``.

    Every method raises
    [`NativeModuleError`][pythonnative.native_modules.registry.NativeModuleError]
    with a ``code``: ``not_ready`` when the camera isn't running,
    ``permission_denied`` when a required permission was refused,
    ``busy`` for a conflicting capture, or ``capture_failed``. Off device, the
    fallback returns a record with an empty ``path``.
    """

    __slots__ = ()

    async def take_picture(self, *, quality: float = 0.9) -> Photo:
        """Take a picture and save it as a JPEG in the app's cache directory.

        Args:
            quality: JPEG quality from 0 to 1.

        Returns:
            The saved picture.
        """
        result: Photo = await native_module("Camera").call_async(
            "take_picture", tag=self.tag, quality=_unit(quality, "quality")
        )
        return result

    async def start_recording(self, *, audio: bool = True) -> None:
        """Start recording video, returning once frames are being written.

        Args:
            audio: Capture sound, prompting for the ``microphone`` permission,
                which the app must declare under ``[permissions]``. Refusing it
                raises rather than silently recording without sound. Pass
                ``False`` to record silent video and skip the prompt.
        """
        await native_module("Camera").call_async("start_recording", tag=self.tag, audio=bool(audio))

    async def stop_recording(self) -> VideoRecording:
        """Stop recording and wait for the file to be finished.

        Returns:
            The saved video.

        Raises:
            NativeModuleError: With the code ``not_recording`` when nothing is
                being recorded, or ``capture_failed`` when no video was saved
                (some platforms reject a recording too short to have a frame).
        """
        result: VideoRecording = await native_module("Camera").call_async("stop_recording", tag=self.tag)
        return result


HANDLE_TYPES["CameraView"] = CameraViewHandle


def CameraView(
    *children: Node,
    facing: CameraFacing = "back",
    flash: CameraFlash = "off",
    zoom: float = 1.0,
    barcode_types: Optional[Sequence[BarcodeType]] = None,
    on_barcode: Optional[Callable[[Barcode], Any]] = None,
    on_ready: Optional[Callable[[], Any]] = None,
    on_error: Optional[Callable[[CameraError], Any]] = None,
    accessibility_label: Optional[str] = None,
    test_id: Optional[str] = None,
    style: StyleProp = None,
    ref: Optional[Ref] = None,
    key: Optional[str] = None,
) -> Element:
    """Show a live camera preview: AVFoundation on iOS, CameraX on Android.

    A preview has no intrinsic size, so give it one with ``style``, such as
    ``pn.style(flex=1)`` or ``pn.style(height=240)``. Passing a ``ref``
    publishes a [`CameraViewHandle`][pythonnative.camera.CameraViewHandle] on
    ``ref.current``.

    It prompts for the ``camera`` permission when it first appears. It never
    raises for a missing camera or a refused prompt: it shows a placeholder and
    calls ``on_error``, which is what happens on the iOS simulator. Android runs
    one preview at a time, so the ``CameraView`` shown most recently wins.

    Args:
        *children: Elements to draw on top of the preview, such as a scan frame.
        facing: The lens to use.
        flash: The flash mode. A device without a flash ignores it.
        zoom: Magnification, where 1 is none. It's clamped to what the current
            lens supports.
        barcode_types: The symbologies to look for. Scanning runs only when this
            isn't empty, and costs nothing otherwise.
        on_barcode: Called with a [`Barcode`][pythonnative.camera.Barcode] when
            one comes into view, and for the same text again only after it has
            been out of view for a moment.
        on_ready: Called each time the preview starts.
        on_error: Called with a [`CameraError`][pythonnative.camera.CameraError]
            when the camera can't run.
        accessibility_label: Screen reader label for the preview.
        test_id: Identifier for UI tests.
        style: Layout and visual style.
        ref: Optional [`Ref`][pythonnative.Ref] from ``use_ref()``.
        key: Stable identity among siblings.

    Returns:
        The preview element.

    Raises:
        PluginNotEnabledError: On a device whose build doesn't include ``camera``.
    """
    element = _camera_view(
        *children,
        facing=facing,
        flash=flash,
        zoom=zoom,
        barcode_types=None if barcode_types is None else list(barcode_types),
        on_barcode=on_barcode,
        on_ready=on_ready,
        on_error=on_error,
        accessibility_label=accessibility_label,
        test_id=test_id,
        style=style,
        key=key,
    )
    if ref is None:
        return element
    return Element(element.type, {**element.props, "ref": ref}, list(element.children), key=key)


def _unit(value: float, name: str) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value!r}")
    return number


class Camera:
    """The system camera screen.

    Raises:
        NativeModuleError: If the native module fails, or with the code
            ``plugin_not_enabled`` when ``camera`` isn't in the build.
    """

    @staticmethod
    async def take_photo(*, quality: float = 0.9, allow_editing: bool = False) -> Optional[str]:
        """Open the system camera screen and let the user take a photo.

        Android asks for the ``camera`` permission first, because the system
        refuses this screen to an app that declares it without holding it.

        Args:
            quality: JPEG quality from 0 to 1.
            allow_editing: Show the crop editor before saving, on iOS. Android
                has no system crop screen and ignores this.

        Returns:
            The path of a full-size JPEG in the app's cache directory, or
            ``None`` when the user canceled or refused the permission, or the
            device has no camera (such as the iOS simulator).

        Raises:
            NativeModuleError: With the code ``busy`` when the screen is
                already open.
        """
        result = await native_module("Camera").call_async(
            "take_photo", quality=_unit(quality, "quality"), allow_editing=bool(allow_editing)
        )
        return str(result) if result else None
