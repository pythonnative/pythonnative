# Hello world

The smallest possible PythonNative app. You'll learn how to:

- Define a component with `@pn.component`.
- Manage state with `use_state`.
- Compose elements with `pn.Column`.
- Run it with `pn run`.

## The code

Save this as `app/main.py`:

```python
import pythonnative as pn


@pn.component
def App():
    count, set_count = pn.use_state(0)
    return pn.Column(
        pn.Text(f"Count: {count}", style={"font_size": 24, "bold": True}),
        pn.Button("Tap me", on_click=lambda: set_count(count + 1)),
        style={"spacing": 12, "padding": 16, "align_items": "stretch"},
    )
```

## What's happening

- `@pn.component` registers `App` as a function component. Hooks
  (like `use_state`) work because the decorator establishes a hook
  context for each call.
- `pn.use_state(0)` returns `(value, setter)`. The setter triggers a
  re-render scheduled by the screen host.
- `pn.Column(*children, style=...)` returns a vertical container
  element. Both the children and the style are read on every render;
  the reconciler diffs them against the previous render and updates
  the underlying `UIView` / `FrameLayout` in place.
- `pn.Text` and `pn.Button` map to native widgets via their
  registered [`ViewHandler`][pythonnative.native_views.base.ViewHandler]
  implementations.
- After every commit a [layout pass](../concepts/layout.md) computes
  an absolute frame for every element using PythonNative's pure-Python
  flexbox engine, so `spacing`, `padding`, and `align_items` produce
  the same geometry on Android and iOS.

## Run it

From the project root:

```bash
pn run android   # or: pn run ios
```

`pn run` will:

1. Stage your `app/` and the bundled `pythonnative` package into the
   appropriate native template under `build/`.
2. Build it (`gradle installDebug` on Android, `xcodebuild` on iOS).
3. Install and launch it on a connected device or simulator.
4. Stream logs back to the terminal.

For an even tighter loop while iterating, add `--hot-reload`:

```bash
pn run android --hot-reload
```

See [Hot reload guide](../guides/hot-reload.md) for the details.

## Next steps

- Build a slightly richer counter: [Counter](counter.md).
- Add a second screen and navigation: [Navigation](navigation.md).
- Learn the runtime model: [Mental model](../concepts/mental-model.md).
