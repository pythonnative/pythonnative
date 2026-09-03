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
| [Navigation](examples/navigation.md) | Stack, tab, and drawer navigators side-by-side. |
| [Collapsing header & bottom sheet](examples/collapsing-header.md) | Scroll-driven animation, `Animated.event`, gestures, and stacking. |

## Working from a project

```bash
pn init my-app
cd my-app
# Edit app/main.py and paste any of the snippets below.
pn preview       # fast desktop preview with Fast Refresh
pn run android   # or: pn run ios
```

The `app/main.py` that `pn init` writes already returns a small
counter; replace it with one of the snippets to try a different
example. The quickest way to iterate is
[`pn preview`](guides/desktop-preview.md), which renders the app in a
desktop window and reloads on every save; use `pn run` when you want it
on a real device or simulator.

## Snippets

### Reusable components

Compose small components and pass them as children:

```python
import pythonnative as pn


@pn.component
def LabeledInput(label: str = "", placeholder: str = ""):
    return pn.Column(
        pn.Text(label, style={"font_size": 14, "bold": True}),
        pn.TextInput(placeholder=placeholder),
        style={"spacing": 4},
    )


@pn.component
def SignUp():
    return pn.ScrollView(
        pn.Column(
            pn.Text("Sign up", style={"font_size": 24, "bold": True}),
            LabeledInput(label="Name", placeholder="Enter your name"),
            LabeledInput(label="Email", placeholder="you@example.com"),
            pn.Button("Submit", on_press=lambda: print("submitted")),
            style={"spacing": 12, "padding": 16},
        )
    )
```

### Theming

```python
BRAND = pn.DEFAULT_LIGHT_THEME.replace(primary_color="#0a84ff")


@pn.component
def Header():
    theme = pn.use_theme()  # follows light/dark mode unless a provider pins one
    return pn.Text(
        "Hello",
        style={"color": theme.primary_color, "font_size": theme.font_size_title, "bold": True},
    )


@pn.component
def App():
    return pn.ThemeContext.Provider(
        BRAND,
        pn.Column(Header(), style={"padding": 16}),
    )
```

### Wrapping with an error boundary

```python
@pn.component
def Risky():
    raise RuntimeError("oops")


@pn.component
def Safe():
    return pn.ErrorBoundary(
        Risky(),
        fallback=lambda exc: pn.Text(f"Failed: {exc}"),
    )
```

### Flex distribution and absolute positioning

```python
@pn.component
def LayoutShowcase():
    return pn.Column(
        pn.Row(
            pn.View(style={"flex": 1, "height": 60, "background_color": "#FAD"}),
            pn.View(style={"flex": 2, "height": 60, "background_color": "#ADF"}),
            pn.View(style={"flex": 1, "height": 60, "background_color": "#DFA"}),
            style={"spacing": 8, "align_items": "stretch"},
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
        style={"spacing": 12, "padding": 16},
    )
```

See [Layout engine](concepts/layout.md) for the full set of supported
flexbox features.

## Next steps

- Walk through the smallest possible app: [Hello world](examples/hello-world.md).
- Learn the bigger picture: [Mental model](concepts/mental-model.md).
- See the live API: [Package overview](api/pythonnative.md).
