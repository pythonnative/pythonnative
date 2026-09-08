# Images

`Image` loads and decodes images with the platform's native image loader. Each
platform caches responses and cancels obsolete requests when a source changes
or a component unmounts. Python doesn't download or decode image bytes.

Use `Image(source=...)` for bundled resources, files, or remote images. Supply
layout constraints when an image must reserve space before its content loads.
