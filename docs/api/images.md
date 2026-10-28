# Images

`Image` loads and decodes images with the platform's native image loader.
Each platform caches responses and cancels obsolete requests when a source
changes or a component unmounts. Python doesn't download or decode image
bytes.

Sources can be a bundled [`Asset`][pythonnative.Asset], an `https` URL, a
file path, or a `data:` URI. `default_source` shows a local image while a
remote one loads (and keeps it if the load fails); `blur_radius` blurs the
decoded bitmap. Supply layout constraints when an image must reserve space
before its content loads.

```python
pn.Image(
    source="https://example.com/photo.jpg",
    default_source=pn.asset("images/placeholder.png"),
    blur_radius=4,
    style=pn.style(width=200, height=120),
)
```

## Images module

[`Images`][pythonnative.Images] measures, prefetches, and clears the
cache of the same pipeline:

```python
size = await pn.Images.get_size(pn.asset("images/hero.png"))
await pn.Images.prefetch("https://example.com/photo.jpg")
pn.Images.clear_cache()
```

::: pythonnative.native_modules.images
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Bundle images, fonts, and vectors: [Assets guide](../guides/assets.md).
