# Hello World

The smallest PythonNative app: a counter with navigation to a detail
screen.

## Preview it on your desktop (fastest)

From this directory, install the example's dependencies (the preview
imports your real app code), then launch it:

```bash
pip install -r requirements.txt
pn preview
```

A desktop window opens running `app/main.py`'s `App`. Edit any component
under `app/`, save, and the window Fast Refreshes in place — no
simulator or device needed. See the
[Desktop preview guide](../../docs/guides/desktop-preview.md).

## Run on a device or simulator

```bash
pn run ios
# or
pn run android
```

Add `--hot-reload` to push edits to the running app without a full
rebuild.
