# Debugging

Set breakpoints, step through code, and inspect variables in the Python
running on a phone, a simulator, an emulator, or the browser preview,
from VS Code or any other editor that speaks the Debug Adapter Protocol.
PythonNative uses [`debugpy`](https://github.com/microsoft/debugpy), the
debugger behind VS Code's Python extension.

## Attach from VS Code

1. Start the dev server and open your app on a device or in the preview:

   ```bash
   pn start
   ```

2. In VS Code, run the **PythonNative: Attach** configuration (Run and
   Debug, or ++f5++). `pn init` writes it to `.vscode/launch.json`:

   ```json
   {
     "name": "PythonNative: Attach",
     "type": "debugpy",
     "request": "attach",
     "connect": {"host": "127.0.0.1", "port": 5678},
     "justMyCode": true
   }
   ```

3. Set breakpoints in your files under `app/`. They bind on the device,
   and the app pauses when it reaches one.

`pn start` listens on `127.0.0.1:5678` and forwards each connection to
one app: the most recently connected device, or the browser preview when
no device is connected. To pick another, use **Debug with VS Code** in
that device's [dev menu](devtools.md#the-dev-menu) or the debugger
control in DevTools' header. Press ++d++ in the `pn start` terminal to see
which app the next session will attach to.

## How it works

- **The debugger runs inside the app.** The dev client starts `debugpy`
  with its debug adapter in the app's own process, because iOS and Android
  apps can't start the separate adapter process `debugpy` normally uses.
- **The connection goes through `pn start`.** A device's debugger listens
  only on the device's own loopback interface. `pn start` carries the
  session over the authenticated dev connection, so no port is opened on
  your network, and a phone on Wi-Fi works the same way as a simulator.
- **`debugpy` is synced like a package.** The first session sends
  `debugpy`'s Python sources from the environment `pn start` runs in (it's
  a dependency of `pythonnative`) into the app's development overlay. Its
  compiled speedups stay behind; the pure-Python tracer is slower but
  only runs while a debugger is attached.
- **Paths are mapped.** The app runs a copy of your sources from its
  overlay or bundle. The dev client maps those paths to your project and
  installed packages, so breakpoints set in your editor bind and stack
  frames open the right files.

## `breakpoint()`

In a development build, `breakpoint()` pauses in the attached debugger.
Without a debugger attached, it prints where it was and how to attach,
then continues, instead of starting `pdb`, which would wait forever for
input on a phone.

## While paused

The paused thread is the app's Python thread. The native UI keeps
running: scrolling, native animations, and gestures still move, but taps
that call Python wait until you continue, and Fast Refresh waits too.
The dev client's network threads are excluded from the debugger, so the
session stays connected while you inspect variables.

Watch expressions and the debug console evaluate on the paused thread.
To run code on the live application loop instead, with `await`, use the
REPL in [DevTools' Console](devtools.md#console).

## Other editors

Any Debug Adapter Protocol client that supports `debugpy` can attach to
`127.0.0.1:5678` with an "attach" request: VS Code and its forks, Zed,
Neovim (`nvim-dap-python`), and Emacs (`dap-mode`). PyCharm's debugger
uses its own protocol rather than `debugpy`, so it can't attach.

## Troubleshooting

- **"no app is connected."** Open the app (press ++i++ or ++a++ in `pn
  start`, or open the preview) before attaching.
- **"couldn't start debugging: debugpy isn't available."** Install it in
  the environment that runs `pn start`: `pip install debugpy`.
- **Breakpoints stay gray.** The file must be part of the synced project
  (under `app/`). Check that `justMyCode` is `true` for your code, or set
  it to `false` to step into PythonNative and installed packages.
- **Port 5678 is in use.** Run `pn start --debug-port 5679` and change the
  port in `launch.json`, or pass `--debug-port 0` to turn the proxy off.
