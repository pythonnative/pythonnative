# Camera

`pythonnative.camera` gives you two ways to use the camera. `Camera.take_photo`
opens the system's own capture screen and returns a photo. `CameraView` is a live
preview inside your screen, with pictures, video, and barcode scanning under your
control. It's built on AVFoundation on iOS and CameraX on Android.

## Setup

```toml
[plugins]
use = ["camera"]

[permissions]
camera = "Scan receipts with your camera."
microphone = "Record sound with your videos."
```

`camera` is required, and a build without it fails with a message naming the line
to add. `microphone` is needed only for video with sound. The plugin also marks the
camera and microphone as optional hardware on Android, so that declaring these
permissions doesn't hide the app from devices without them.

## API tour

### The system screen

```python
from pythonnative.camera import Camera


async def add_receipt() -> None:
    path = await Camera.take_photo(quality=0.8)
    if path is None:
        return  # Canceled, refused, or no camera.
    await upload(path)
```

### A live preview

```python
import pythonnative as pn
from pythonnative.camera import Barcode, CameraError, CameraView


@pn.component
def Scanner() -> pn.Node:
    camera = pn.use_ref()
    problem, set_problem = pn.use_state(None)

    async def capture() -> None:
        photo = await camera.current.take_picture(quality=0.8)
        print(photo.path, photo.width, photo.height)

    def scanned(barcode: Barcode) -> None:
        print(barcode.type, barcode.data)

    def failed(error: CameraError) -> None:
        set_problem(error.code)

    return pn.Column(
        CameraView(
            pn.Text("Align the code in the frame"),
            ref=camera,
            facing="back",
            flash="auto",
            zoom=1.5,
            barcode_types=["qr", "ean13"],
            on_barcode=scanned,
            on_error=failed,
            style=pn.style(flex=1),
        ),
        pn.Button("Capture", on_press=capture),
        style=pn.style(flex=1),
    )
```

A preview has no intrinsic size, so give it one with `style`. Its children draw on
top of it.

`CameraView` prompts for the `camera` permission when it first appears. A missing
camera or a refused prompt never raises. The view shows a placeholder saying what's
wrong and calls `on_error` with a
[`CameraError`][pythonnative.camera.CameraError], whose `code` is `unavailable`,
`permission_denied`, or `capture_failed`. A view whose permission was refused tries
again the next time it's mounted.

### Pictures and video

`ref.current` is a [`CameraViewHandle`][pythonnative.camera.CameraViewHandle]:

```python
async def record_clip(camera: pn.Ref) -> None:
    await camera.current.start_recording()
    await asyncio.sleep(5)
    recording = await camera.current.stop_recording()
    print(recording.path, recording.duration)
```

`start_recording` captures sound by default, which prompts for `microphone`. If the
user refuses, or the app didn't declare it, the call raises with the code
`permission_denied` rather than silently recording without sound. Pass `audio=False`
to record silent video and skip the prompt.

Handle methods raise
[`NativeModuleError`][pythonnative.native_modules.registry.NativeModuleError] with
the code `not_ready` when the camera isn't running, `busy` for a conflicting capture,
`not_recording` from `stop_recording` when nothing is being recorded, and
`capture_failed` otherwise.

### Barcodes

Scanning runs only while `barcode_types` isn't empty, and costs nothing otherwise.
`on_barcode` fires when a code comes into view, and for the same text again only
after it has been out of view for a moment, so holding a code in frame doesn't flood
your handler.

## Platform differences

| | iOS | Android | Browser preview |
| --- | --- | --- | --- |
| `Camera.take_photo` | `UIImagePickerController` | `ACTION_IMAGE_CAPTURE`, after asking for `camera` | Returns `None` |
| `allow_editing` | Shows the crop editor | Ignored: there's no system crop screen | Ignored |
| Video file | QuickTime (`.mov`) | MPEG-4 (`.mp4`) | A `blob:` URL |
| Barcode engine | `AVCaptureMetadataOutput` | ML Kit, bundled in the app | `BarcodeDetector` where the browser has it |
| `codabar` | iOS 15.4 or later | Yes | Depends on the browser |
| `zoom`, `flash="torch"` | Yes | Yes | Only if the webcam's track supports them |
| `flash="on"`, `"auto"` | Fires on `take_picture` | Fires on `take_picture` | Ignored |
| More than one view | Each has its own session, though the hardware runs one at a time | One at a time: the one shown most recently wins | Each has its own stream |

On Android, barcode scanning pauses while recording, because few devices can run a
preview, pictures, video, and analysis together. A device that can't run pictures
alongside video raises `not_ready` from `take_picture` until the recording ends.

Android's barcode scanning brings ML Kit's bundled model into every app that enables
`camera`, about 2.4 MB per ABI. Google's ML Kit documentation describes the data the
library reports, which belongs in your Play data safety form.

In the browser preview, `getUserMedia` needs a secure origin, which `localhost` counts
as.

## What a simulator can't show

**iOS simulator.** It has no camera, so everything past the placeholder is untested:
the live preview, `take_picture`, recording, `flash`, `zoom`, `facing`, barcode
scanning, and `Camera.take_photo` taking a picture. What was run there: the view shows
"Camera unavailable" and `on_error` reports `unavailable`, `take_picture` and
`start_recording` raise `not_ready`, `stop_recording` raises `not_recording`,
`take_photo` returns `None`, and remounting works. **Try the iOS capture paths on a
device before relying on them.**

**Android emulator (API 31).** Run for real on its front (emulated) camera: the
preview, the permission prompt and refusal, `take_picture` at two qualities, video
with and without sound, `not_recording`, remounting, and `Camera.take_photo` through
the system camera app and `FileProvider`. Some things couldn't be fully exercised:

- `take_picture` on the emulator's back (virtual scene) camera crashes the emulator's
  camera HAL, in `NV21JpegCompressor` in `camera.ranchu.so`, so the call raises
  `capture_failed` after 30 seconds. The system camera app and video both work on that
  camera, and the crash is outside the app's process. Whether a device behaves this
  way wasn't checked, because no device was available.
- Barcode scanning through the camera wasn't seen, because no barcode could be put in
  front of the virtual lens. ML Kit decoded a QR code from a bitmap in the running app,
  and the analysis use case ran alongside the preview without errors.
- `flash` has no effect to observe, because the emulator has no flash unit.

**Browser preview.** The placeholder and `on_error` were run with the camera blocked.
The live preview, capture, and recording weren't, because no camera was available to
the test browser.
