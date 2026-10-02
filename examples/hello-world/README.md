# Hello World

A small tour of PythonNative: four tabs inside a native stack, typed
screens, a theme with light and dark variants, and a setting that's
saved on the device.

- `app/main.py` defines the navigators as module-level values. `Tabs`
  (Home, Layout, List, and Settings) is the first screen of the `Root`
  stack, and the Showcase, Forms, and Async Demo screens push on top of
  it with calls like `nav.push(ShowcaseScreen(message="Hi"))`.
- `app/theme.py` subclasses `pn.Theme` to add the demo's own color
  tokens and defines the styles every screen shares. `App` passes the
  light and dark themes to `pn.ThemeProvider`, so the screens and the
  navigation bars follow the system appearance.
- `app/preferences.py` saves the appearance chosen on the Settings tab
  (System, Light, or Dark) with `pn.use_persisted_state` and applies it
  at launch.
- `app/screens/` holds one file per screen. They cover state and
  effects, flex layout, a virtualized `FlatList`, native alerts,
  animations, forms with a title that follows the input, and async
  data with `Suspense`, `use_query`, and `use_mutation`.

## Preview it in the browser (fastest)

From this directory, install the example's dependencies (the preview
imports your real app code), then launch it. This app declares `emoji`
in `[requirements].packages`, so install it locally for the preview:

```bash
pip install emoji
pn preview
```

A browser tab opens running `app/main.py`'s `App` in a phone frame.
Edit any component under `app/`, save, and the page Fast Refreshes in
place (no simulator or device needed). See the
[Browser preview guide](../../docs/guides/browser-preview.md).

## Run on a device or simulator

Leave `pn preview` running and, in another terminal:

```bash
pn run ios
# or
pn run android
```

The debug build connects to the same dev server, so saves under `app/`
Fast Refresh it too and its logs show up in the `pn preview` terminal.
See the [Development workflow](../../docs/guides/dev-workflow.md).

## Check it

From this directory, the app passes strict type checking and the hook
linter:

```bash
uv run mypy --strict app
uv run pn lint app
```
