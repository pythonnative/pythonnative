# Graphics

Vector drawing and visual effects: [`Icon`][pythonnative.Icon] for the
bundled Lucide icon set, [`Svg`][pythonnative.components.Svg] with the shape
classes in `pythonnative.svg` (below), and the
[`LinearGradient`][pythonnative.components.LinearGradient] and
[`BlurView`][pythonnative.components.BlurView] containers. The component
factories themselves are documented on the [Components](components.md) page.

```python
import pythonnative as pn
from pythonnative import svg

pn.Icon("heart", color="#DC2626")

pn.Svg(
    svg.Circle(cx=12, cy=12, r=10, fill="#FDE68A"),
    svg.Path(d="M8 13 q4 5 8 0", stroke="#B45309", stroke_width=2, fill="none"),
    style=pn.style(width=48, height=48),
)

pn.LinearGradient(pn.Text("Hi"), colors=["#6366F1", "#EC4899"], style=pn.style(padding=16))
```

See the [Assets guide](../guides/assets.md) for the drawing model and
platform notes.

## Icons

::: pythonnative.icons
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## SVG shapes and parsing

::: pythonnative.svg
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]
