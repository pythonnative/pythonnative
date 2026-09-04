# Hello World

The smallest PythonNative app: a counter with navigation to a detail
screen.

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
