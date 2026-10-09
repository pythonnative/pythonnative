# Examples

Small, self-contained snippets and full apps that show PythonNative's
component model and patterns. Each example is also runnable inside a
project scaffolded with `pn init`.

## Featured examples

| Page | What it covers |
|---|---|
| [Hello world](examples/hello-world.md) | The smallest possible app and how it boots. |
| [Counter](examples/counter.md) | `use_state`, event handlers, and basic styling. |
| [Forms](examples/forms.md) | `TextInput`, controlled inputs, validation, submit. |
| [Lists](examples/lists.md) | `FlatList`, keyed children, dynamic rendering. |
| [Navigation](examples/navigation.md) | Typed screens, stack, tab, and drawer navigators, and nesting. |
| [Collapsing header & bottom sheet](examples/collapsing-header.md) | Scroll-driven animation, `Animated.event`, gestures, and stacking. |

## Complete apps

The repository also includes runnable projects with their own setup instructions:

- [Inbox](https://github.com/pythonnative/pythonnative/tree/main/examples/inbox):
  an offline app with variable-height lists, shared state, search, editing,
  persistence, native navigation, and a generated native extension.
- [Feature catalog](https://github.com/pythonnative/pythonnative/tree/main/examples/e2e-suite):
  component and API demonstrations used by the mobile E2E suite.

## Working from a project

```bash
pn init my-app
cd my-app
# Edit app/main.py and paste any of the snippets below.
pn preview       # dev server + browser preview with Fast Refresh
pn run android   # or: pn run ios
```

The `app/main.py` that `pn init` writes already renders a small
counter with a detail screen; replace it with one of the snippets to
try a different example. The quickest way to iterate is
[`pn preview`](guides/browser-preview.md), which renders the app in a
browser tab and Fast Refreshes on every save; `pn run` puts it on a
device or simulator connected to the same dev server.

## Snippets

### Reusable components

Compose small components and pass them as children:

```python
import pythonnative as pn


@pn.component
def LabeledInput(label: str = "", placeholder: str = "") -> pn.Node:
    return pn.Column(
        pn.Text(label, style={"font_size": 14, "bold": True}),
        pn.TextInput(placeholder=placeholder),
        style={"gap": 4},
    )


@pn.component
def SignUp() -> pn.Node:
    return pn.ScrollView(
        pn.Column(
            pn.Text("Sign up", style={"font_size": 24, "bold": True}),
            LabeledInput(label="Name", placeholder="Enter your name"),
            LabeledInput(label="Email", placeholder="you@example.com"),
            pn.Button("Submit", on_press=lambda: print("submitted")),
            style={"gap": 12, "padding": 16},
        )
    )
```

### Theming

```python
from dataclasses import replace

import pythonnative as pn

LIGHT = replace(pn.LIGHT_THEME, colors=replace(pn.LIGHT_THEME.colors, primary="#0A84FF"))
DARK = replace(pn.DARK_THEME, colors=replace(pn.DARK_THEME.colors, primary="#64D2FF"))


class HeaderStyles:
    def __init__(self, theme: pn.Theme) -> None:
        self.title: pn.Style = {**theme.typography.title, "color": theme.colors.primary}
        self.container = pn.style(padding=theme.spacing.md, background_color=theme.colors.background)


@pn.component
def Header() -> pn.Node:
    styles = pn.use_styles(HeaderStyles)  # rebuilt only when the theme changes
    return pn.View(pn.Text("Hello", style=styles.title), style=styles.container)


@pn.component
def App() -> pn.Node:
    return pn.ThemeProvider(Header(), light=LIGHT, dark=DARK)
```

`ThemeProvider` picks `LIGHT` or `DARK` from the color scheme, and the
navigators use the same theme. See [Styling](guides/styling.md#themes).

### Wrapping with an error boundary

```python
@pn.component
def Risky() -> pn.Node:
    raise RuntimeError("oops")


@pn.component
def Safe() -> pn.Node:
    return pn.ErrorBoundary(
        Risky(),
        fallback=lambda exc: pn.Text(f"Failed: {exc}"),
    )
```

### Flex distribution and absolute positioning

```python
@pn.component
def LayoutShowcase() -> pn.Node:
    return pn.Column(
        pn.Row(
            pn.View(style={"flex": 1, "height": 60, "background_color": "#FAD"}),
            pn.View(style={"flex": 2, "height": 60, "background_color": "#ADF"}),
            pn.View(style={"flex": 1, "height": 60, "background_color": "#DFA"}),
            style={"gap": 8, "align_items": "stretch"},
        ),
        pn.View(
            pn.View(style={"position": "absolute", "top": 8, "left": 8,
                           "width": 32, "height": 32,
                           "background_color": "#F00"}),
            pn.View(style={"position": "absolute", "bottom": 8, "right": 8,
                           "width": 32, "height": 32,
                           "background_color": "#0A0"}),
            style={"width": 200, "height": 120, "background_color": "#EEE"},
        ),
        style={"gap": 12, "padding": 16},
    )
```

See [Layout engine](concepts/layout.md) for the full set of supported
flexbox features.

## Next steps

- Walk through the smallest possible app: [Hello world](examples/hello-world.md).
- Learn the bigger picture: [Mental model](concepts/mental-model.md).
- See the live API: [Package overview](api/pythonnative.md).
