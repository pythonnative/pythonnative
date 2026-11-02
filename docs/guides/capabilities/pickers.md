# Pickers

`pythonnative.pickers` opens the system's photo and document pickers and hands
you copies of what the user chose. The system draws these pickers in its own
process, so they need no permission: the app only ever sees what the user picked.

## Setup

```toml
[plugins]
use = ["pickers"]
```

That's all the pickers need. The plugin also owns the `photo_library` permission
name, for an app that reads the library directly. Declare it only in that case:

```toml
[permissions]
photo_library = "Show your albums."
```

## API tour

```python
from pythonnative.pickers import pick_documents, pick_images, pick_videos


async def add_photos() -> None:
    for photo in await pick_images(limit=5, quality=0.8):
        await upload(photo.path, photo.mime_type)


async def add_clip() -> None:
    videos = await pick_videos()
    if not videos:
        return  # The user canceled.
    await upload(videos[0].path, videos[0].mime_type)


async def attach() -> None:
    files = await pick_documents(types=["application/pdf", "image/*"], multiple=True)
    for file in files:
        print(file.name, file.size)
```

Every function returns a list of
[`PickedFile`][pythonnative.pickers.PickedFile] records with `path`, `name`,
`mime_type`, and `size`. An empty list means the user canceled, which isn't an
error. A second picker opened while one is up raises
[`NativeModuleError`][pythonnative.native_modules.registry.NativeModuleError]
with the code `busy`.

`path` points at a copy in the app's cache directory. The system can clear that
directory when it runs low on space, so move anything you want to keep.

`quality` applies only to `pick_images`. Below 1, a photo is re-encoded as a
JPEG, which also turns HEIC into something every library can read. PNG and GIF
keep their bytes, to preserve transparency and animation. At 1, every photo keeps
its original bytes.

`limit=0` means as many as the system allows.

`types` takes MIME types and the wildcards `image/*`, `video/*`, `audio/*`,
`text/*`, and `application/*`. Pass `None` to offer every file.

## Platform differences

| | iOS | Android | Browser preview |
| --- | --- | --- | --- |
| Photos and videos | `PHPickerViewController`, or `UIImagePickerController` on iOS 13 | `ACTION_PICK_IMAGES` on API 33, and on API 30 to 32 with the SDK extension; `ACTION_GET_CONTENT` otherwise | `<input type=file>` |
| Documents | `UIDocumentPickerViewController` | `ACTION_OPEN_DOCUMENT` | `<input type=file>` |
| `limit` | Enforced by the picker. iOS 13 can only choose one | Enforced by the photo picker. `ACTION_GET_CONTENT` can't enforce a number, so extra choices are dropped | Extra choices are dropped |
| `path` | A file path | A file path | A `blob:` URL |

A browser opens its file chooser only during the press that caused it. The round
trip through Python normally stays within that window. A browser that doesn't
fire the `cancel` event never settles the call when the user cancels.

## What a simulator can't show

**iOS simulator (iOS 26).** Run for real: `pick_images` choosing two sample photos,
which arrive as JPEG files in the cache; canceling each picker with its button and
with a swipe; and the `photo_library` status. Choosing a video or a document wasn't
run, because the simulator holds none. The iOS 13 fallback through
`UIImagePickerController` compiles but wasn't run, because no iOS 13 simulator was
available.

**Android emulator (API 31).** Run for real: `pick_images` choosing a PNG through
`ACTION_GET_CONTENT`, which arrives with its original bytes, and canceling
`pick_documents`. `ACTION_PICK_IMAGES` wasn't run, because this image doesn't have
the SDK extension it needs. Re-encoding a JPEG with an EXIF rotation wasn't run through
a picker either.

**Browser preview.** `pick_videos` ran with a scripted file chooser, so a browser's own
dialog wasn't involved.

The e2e flow opens the document picker and cancels it on both simulators. It doesn't
choose an item, because a picker's contents and layout belong to the system and differ
between OS versions.
