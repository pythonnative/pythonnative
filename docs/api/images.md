# Images

The shared image pipeline behind the
[`Image`][pythonnative.Image] and
[`ImageBackground`][pythonnative.ImageBackground] components. Remote
sources are downloaded on a background thread with an in-memory LRU
cache, a disk cache, and request deduplication (many views asking for
the same URL trigger one download). Platform handlers decode the
cached file downsampled to the view's bounds, so oversized photos
don't pin full-resolution bitmaps in memory.

Most apps never call this module directly; the `Image` component's
`placeholder_color`, `on_load`, and `on_error` props cover the common
cases:

```python
import pythonnative as pn

pn.Image(
    source="https://example.com/photo.jpg",
    placeholder_color="#E2E8F0",
    on_load=lambda: print("loaded"),
    on_error=lambda message: print("failed:", message),
    style={"width": 200, "height": 120},
)
```

::: pythonnative.images
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]
