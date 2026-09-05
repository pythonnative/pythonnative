# Fast Refresh

Fast Refresh turns the edit-save-rebuild loop into edit-save-see. The
[dev server](dev-workflow.md) watches `app/`, pushes each changed file
to every connected client (the browser preview, simulators, emulators,
phones), and each client reloads the affected modules and refreshes its
mounted screens in place, keeping component state.

There's nothing to turn on. `pn start` (or `pn preview`) is the server;
any debug build launched with `pn run` while it's running is a client.

```bash
pn start            # terminal 1
pn run ios          # terminal 2 (or android, or open the browser preview)
```

## What happens on save

1. The server's watcher notices `app/screens/home.py` changed, updates
   its manifest, and broadcasts an `update` with the new contents.
2. Each client writes the file into its **overlay**, a writable
   directory that sits ahead of the bundled sources on `sys.path`
   (the browser preview has no overlay; the project directory is
   already on its path).
3. The client resolves the path to a module (`app.screens.home`) and
   calls [`apply_reload`][pythonnative.hot_reload.apply_reload] on the
   main thread.
4. `apply_reload` re-executes the changed module, then the other
   imported modules under `app` that may hold bindings to it (the
   entry module's `from app.screens.home import HomeScreen`, for
   instance), leaves first.
5. Every live screen host runs **Fast Refresh**: it walks its VNode
   tree, finds each component function whose module was reloaded,
   looks up the replacement by `__module__` + `__qualname__`, and
   rewrites the `Element.type` references in place. The next
   reconcile sees the new function with the same `HookState`, so state
   survives.
6. The host re-renders. Layout and native views update incrementally
   through the normal reconciler path.
7. The client reports back (`fast_refresh: app.screens.home 42ms`),
   which prints in the `pn start` terminal and toasts in the preview.

If Fast Refresh can't find a clean swap (a component's `__qualname__`
changed, a render raised with the new function, or the swap itself
failed), the host falls back to a **full remount** of its root, so you
never get stuck with a stale tree. Hook state is reset in that case
and the report says `remount`.

If the saved file fails to import (a syntax error mid-edit), the
previous module stays in `sys.modules`, the traceback shows in the
RedBox and the terminal, and the app keeps running. Fix the file and
save again.

Per-screen scope: each native screen (`UIViewController` on iOS,
`ScreenFragment` on Android, a screen element in the preview) runs its
own host, so Fast Refresh operates independently per host. Two pushed
screens that both use a changed module each swap their own references.

## What gets reloaded

Any `.py` file under `app/`. Assets under `app/` (images, JSON, fonts)
are synced too, so an `Image` that points at a bundle-relative file
picks up the new bytes the next time it renders.

## What doesn't reload

- Native template files (anything under `android_template/` or
  `ios_template/`) and native plugins. Changes there require a rebuild;
  `pn run` detects them through the
  [native fingerprint](dev-workflow.md#when-native-rebuilds-happen) and
  runs the toolchain automatically.
- `pythonnative.toml`. Permissions, requirements, and app metadata are
  native inputs; `pn run` rebuilds when it changes.
- Files outside `app/`. If you have a shared library next to your
  project, copy or symlink it under `app/` to pick up changes.
- C extension modules. Recompiled `.so` / `.dylib` libraries are not
  reloaded mid-session.
- The `pythonnative` package itself. Reinstall and rebuild.

## Common pitfalls

!!! warning "Top-level side effects"
    Code that runs at import time (a global registry that registers
    itself when the module is imported) runs again on every reload.
    Idempotent registration is fine; non-idempotent setup (counters,
    network calls, opening files) needs guarding.

!!! warning "References across modules"
    If module `a` does `from b import Foo` and only `b.py` changes,
    `a` is re-executed too so its binding updates, but long-lived
    references stashed elsewhere (a module-level cache, an object held
    in `use_ref`) can drift. When in doubt, use **Reload app** in the
    preview or relaunch the device build.

!!! warning "Hook signature changes"
    Adding or removing a hook in a component changes the slot layout.
    Fast Refresh swaps the function in place, and the next render may
    read the wrong slots; the host falls back to a remount when it
    detects the swap raising. If you see suspicious state after a
    hook-shape edit, close and reopen the affected screen (or reload
    the app) to clear the slate.

!!! info "Renaming a component"
    Fast Refresh keys on each function's `__qualname__`. Renaming a
    component changes the key, so the live VNode keeps its old
    function until the parent re-renders with the new name. Trigger a
    navigation or state change, or reload the app.

## Without a dev server

Fast Refresh needs `pn start` running. If you `pn run` without one, the
CLI says so and builds an app that runs its bundled sources; start the
server and relaunch to connect it. For rebuild-on-every-change (more
predictable, much slower), pass `--rebuild`.

## Reading logs

Every dev client mirrors its `print` output, warnings, and tracebacks
to the `pn start` terminal, so you rarely need a device log viewer. For
native-level output, `pn logs ios` / `pn logs android` attach to
`os_log` and `logcat`; `pn run` does the same after launching unless
you pass `--no-logs`.

## Next steps

- The whole loop: [Development workflow](dev-workflow.md).
- Reference: [Hot reload API](../api/hot_reload.md) and
  [Dev server API](../api/devserver.md).
