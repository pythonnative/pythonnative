# Assets

Files under `app/assets/` are bundled into the iOS app, the Android APK,
and the browser preview, and are addressed from Python by relative path:

```python
import pythonnative as pn

logo = pn.asset("images/logo.png")   # Asset("images/logo.png")
pn.Image(source=logo, style=pn.style(width=120, height=40))
config = pn.asset("data/config.json").read_text()
```

The [Assets guide](../guides/assets.md) covers density variants, fonts,
icons, and how the folder is bundled and synced.

::: pythonnative.assets
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Fonts

Bundled `.ttf` and `.otf` files are parsed at build time so `font_family`
can refer to them by family name.

::: pythonnative.assets.fonts
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Measure and prefetch images with [`Images`](images.md).
- Draw bundled vectors with [`Svg`][pythonnative.components.Svg] and
  [`Icon`][pythonnative.Icon]: see [Graphics](graphics.md).
