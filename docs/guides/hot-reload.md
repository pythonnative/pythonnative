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
   application thread.
4. `apply_reload` re-executes the changed module, then the other
   imported modules under `app` that may hold bindings to it (the
   entry module's `from app.screens.home import HomeScreen`, for
   instance), leaves first.
5. The application host runs **Fast Refresh**: it walks its VNode
   tree, finds each component function whose module was reloaded,
   looks up the replacement by `__module__` + `__qualname__`, and
   rewrites the `Element.type` references in place. The next
   reconcile sees the new function with the same `HookState`, so state
   survives when the captured hook signature is compatible. Hook-order or
   custom-hook changes remount the affected component, and a changed class
   definition remounts the application (see
   [When state survives](#when-state-survives)).
6. The host re-renders. Layout and native views update incrementally
   through the normal reconciler path.
7. The client reports back (`fast_refresh: app.screens.home 42ms`),
   which prints in the `pn start` terminal and toasts in the preview.

If Fast Refresh can't find a clean swap (a component's `__qualname__`
changed, a render raised with the new function, or the swap itself
failed), the host falls back to a **full remount** of its root, so you
never get stuck with a stale tree. Hook state is reset in that case
and the report says `remount`. When no screen is mounted yet, nothing is
refreshed and nothing is reported; the first render reads the new files.

If the saved file fails to import (a syntax error mid-edit), the
previous module stays in `sys.modules`, the traceback shows in the
RedBox and the terminal, and the app keeps running. Fix the file and
save again.

Refresh walks the application's shared logical tree, including covered screens
and mounted list rows. Native containers don't create separate Python hosts.

## When state survives

A save keeps component state unless one of the following is true:

- **A component's hooks changed.** Fast Refresh records each component's
  hook calls (their order, kind, and binding names, following custom
  hooks defined in your app). If the new function's signature differs,
  only the instances of that component remount; the rest of the tree
  keeps its state.
- **A class definition changed.** Before reloading, `apply_reload`
  fingerprints every class defined in each module it's about to
  re-execute. The fingerprint covers the class's name, metaclass, and
  bases; its annotated field names; its dataclass fields and their
  defaults; its immutable class attributes (numbers, strings, tuples, and
  `Enum` member values); and the bytecode, constants, names, and defaults
  of every method, property, `staticmethod`, and `classmethod`. If a class
  that existed before is removed, renamed, or has a different fingerprint
  after the reload, the whole application remounts, because an instance
  of the old class could still sit in `use_state`, `use_memo`, or
  `use_ref`.

Everything else preserves state. In particular, these never force a
remount:

- Editing a component's body, text, styles, or props (as long as its hooks
  stay the same).
- Adding, editing, or removing plain functions, lambdas, and constants.
  They're rebound when the module re-executes, and components pick them
  up on their next render.
- Defining or editing a `TypedDict` or `Protocol`. They describe shapes;
  nothing holds an instance of the class itself.
- Re-executing a module whose classes didn't change. A dataclass, `Enum`,
  `NamedTuple`, or exception class that's identical to its previous
  definition keeps its fingerprint.
- Moving a class, adding blank lines or comments around it, or editing
  the text of its docstring or its methods' docstrings. Line numbers,
  file names, and docstring text aren't part of the fingerprint.
- Adding a new class. No live instance can refer to it yet.

!!! note "Unchanged classes are still new objects"
    Re-executing a module creates new class objects even when their
    fingerprints match. An instance created before the save keeps its old
    class, so `isinstance` checks against the new class, or identity
    comparisons between an old `Enum` member held in state and a new one,
    return `False`. Compare `Enum` members by `.name` or `.value` if that
    matters during development, or reload the app.

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
    Fast Refresh compares captured hook signatures before preserving
    state. Hook-order and custom-hook changes remount affected component
    instances. Changed class definitions remount the application; see
    [When state survives](#when-state-survives).

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

The app also needs your dev token, which `pn run` passes along with the
server's URL; see [The dev token](dev-workflow.md#the-dev-token). If
you delete the token file, relaunch installed debug builds with `pn run`
so they pick up the new one.

Release builds have no Fast Refresh at all: they leave out
`pythonnative.hot_reload`, `pythonnative.refresh`, and the dev client.
See [Building for release](building-for-release.md#what-a-release-bundle-leaves-out).

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
