# Hot reload

Hot reload turns your edit-save-rebuild loop into edit-save-see. The
`pn` CLI watches `app/` for changes and pushes the modified files
straight to the running app, where a small device-side helper reloads
the affected modules and asks the screen host to re-render.

## Turn it on

Add `--hot-reload` to your `pn run` invocation:

```bash
pn run android --hot-reload
# or
pn run ios --hot-reload
```

`pn` will:

1. Build and install the app once (the standard `run` flow).
2. Launch the app on a connected device or simulator.
3. Start a [`FileWatcher`][pythonnative.hot_reload.FileWatcher] over
   `app/`.
4. Push changed Python files into a writable on-device overlay.
5. Write a small reload manifest that the running app polls from the
   main thread.
6. Tail logs (Android) or print hot-reload notifications (iOS) until
   you press `Ctrl+C`.

## How the device sees changes

The native templates call
[`configure_dev_environment()`][pythonnative.hot_reload.configure_dev_environment]
before importing your app. That creates a `pythonnative_dev/` directory
in the app's writable sandbox and puts it before the bundled app code
on `sys.path`.

When a source file changes, the CLI copies it to that overlay:

- Android: app-private storage via `adb` + `run-as`
- iOS Simulator: the installed app's `Documents/pythonnative_dev/`
  directory

After the files are in place, the CLI writes `reload.json`. The
Android and iOS templates poll that manifest on the platform main
thread and call the screen host's reload hook. The host re-imports the
root component by dotted path, resets hook/navigation state for the
page, and mounts the refreshed tree.

## What gets reloaded

PythonNative reloads any `.py` file under `app/`. The device-side
[`ModuleReloader`][pythonnative.hot_reload.ModuleReloader] resolves
the file to a dotted module name (e.g., `app/pages/home.py` becomes
`app.pages.home`) and re-imports it from disk.

After reloading, every active screen host runs **Fast Refresh** in
place:

1. Walk the live VNode tree and collect every component function
   defined in a reloaded module.
2. Look up each function's replacement by `__module__` +
   `__qualname__` in the freshly reloaded module (unwrapping the
   `@pn.component` decorator).
3. Rewrite the `Element.type` references on every VNode in place;
   the next reconcile sees the new function with the same
   `HookState`, so state survives.

The next render runs through
[`Reconciler.reconcile`][pythonnative.reconciler.Reconciler.reconcile]
just like a normal re-render, so layout and native views are
updated incrementally. Component state (`use_state`, `use_reducer`,
refs) is preserved across the swap.

If Fast Refresh can't find a clean swap (for example, a
component's `__qualname__` changed, a new module was added that the
tree doesn't reference yet, or the swap raises), the host
**falls back** to a full remount of its root component so you never
get stuck with a stale tree. Hook state is reset in that case.

Per-screen scope: each native screen (UIViewController on iOS,
ScreenFragment on Android) runs its own host, so Fast Refresh
operates independently per host. Two pushed screens both running
Fast Refresh for the same changed module each swap their own
references.

## What doesn't reload

- Native template files (anything under `android_template/` or
  `ios_template/`). Changes there require a full rebuild because the
  Java/Swift code is compiled into the app binary.
- Files outside `app/`. If you have a shared library next to your
  project, copy or symlink it under `app/` to pick up changes.
- C extension modules. Hot reload only updates Python source files;
  recompiled `.so` / `.dylib` libraries are not re-loaded mid-session.

## Common pitfalls

!!! warning "Top-level side effects"
    Code that runs at import time (e.g., a global registry that
    registers itself when the module is imported) runs again on every
    reload. Idempotent registration is fine; non-idempotent setup
    (counters, network calls) needs guarding.

!!! warning "References across modules"
    If module `a` does `from b import Foo` and only `b.py` changes,
    module `a` may still hold the *old* `Foo`. The screen host always
    reloads the root screen module after changed modules so common
    component imports update, but long-lived references (e.g., stashed
    in a global) can drift. When in doubt, restart the app.

!!! warning "Hook signature changes"
    Adding or removing a hook in a component changes the slot layout.
    Fast Refresh will swap the function in place but the next render
    can read the wrong slots, so the host falls back to a full
    remount when it detects the swap raises. If you see suspicious
    state after a hook-shape edit, close and reopen the affected
    screen (or restart the app) to clear the slate.

!!! info "Renaming a component"
    Fast Refresh keys on each function's `__qualname__`. Renaming a
    component changes the key, so the live VNode keeps its old
    function until the parent re-renders with the new name. In
    practice this means you may need to trigger one navigation or
    state change for the renamed component to take effect; closing
    and reopening the screen always works.

## Working without `--hot-reload`

Hot reload is opt-in. If you'd rather rebuild on every change (more
predictable, slower), use `pn run android` / `pn run ios` without the
flag, or split the loop:

```bash
pn run android --prepare-only   # stage files, skip the build
# ...edit...
pn run android                  # rebuild and re-install
```

`--prepare-only` is also useful for iterating on
`AndroidManifest.xml` or `Info.plist` because those changes never
hot-reload and you want the smallest possible cycle.

## Reading device logs

Hot reload streams logs by default so you can see exceptions from your
reloaded modules. Pass `--no-logs` to suppress the stream:

```bash
pn run android --hot-reload --no-logs
```

On iOS hot reload currently targets the Simulator flow. Use Console.app
or Xcode for full live logs while the CLI keeps the watcher process in
the foreground.

## Next steps

- Reference: [Hot reload API](../api/hot_reload.md).
- See where hot reload sits in the run loop: [`pn run`](../api/cli.md).
