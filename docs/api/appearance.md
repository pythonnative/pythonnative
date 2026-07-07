# Appearance

System color-scheme tracking with an optional app-level override.
The screen host publishes the platform's light/dark setting into this
module; [`use_color_scheme`][pythonnative.use_color_scheme] and
[`use_theme`][pythonnative.use_theme] subscribe to it and re-render
components when the effective scheme changes.

```python
import pythonnative as pn


@pn.component
def SchemeAwareBadge():
    scheme = pn.use_color_scheme()  # "light" or "dark"
    theme = pn.use_theme()  # built-in theme for the scheme
    return pn.Text(
        f"Currently {scheme}",
        style={"color": theme["text_color"]},
    )
```

Force an appearance regardless of the system setting (for example
from an in-app toggle), or return to following the system:

```python
pn.appearance.set_color_scheme("dark")  # force dark
pn.appearance.set_color_scheme(None)  # follow the system again
```

::: pythonnative.appearance
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Theming with [`use_theme`][pythonnative.use_theme] and
  [`ThemeContext`][pythonnative.ThemeContext]: see
  [Style](style.md) and the [Styling guide](../guides/styling.md).
