# Offline inbox

This reference app combines 2,000 immutable issue records, variable-height
native list rows, deferred and cancellable search, a detail form, optimistic
persistence with rollback, and native stack navigation. Its separately packaged
extension exercises generated props, nested records, typed events, cancellable
asynchronous methods, bundled resources, and exact SwiftPM and Maven dependencies.

- `app/repository.py` owns the data. A `pn.Store[Snapshot]` holds the issues,
  the loading flag, and the last error as one frozen dataclass, and the
  repository's `load` and `save` methods are its actions. The same rows also
  live in a keyed `pn.ListData`, so an edit patches one row of the unfiltered
  list instead of making it diff 2,000 items. A failed save restores the
  previous issue and records the error.
- `app/main.py` defines the screens and the `Root` stack. The inbox reads the
  whole snapshot with `pn.use_store(repository.store)`, and the detail screen
  selects just its issue and the error, so it re-renders only when those
  change. Search runs in `pn.use_query`, which cancels a pass that a newer
  keystroke makes stale. Every color comes from the theme, so the app follows
  the system's light or dark appearance.

Build the extension wheel from the repository root:

```sh
uv build --wheel examples/inbox-extension --out-dir examples/inbox/vendor
```

Then, from this directory, run `pn run ios` or `pn run android`. Use `pn preview`
for the browser version. The native extension badge appears on mobile devices.

After changing `../inbox-extension/src/inbox_extension/__init__.py`, regenerate
its schema, rebuild the wheel, and rebuild the app:

```sh
PYTHONPATH=../inbox-extension/src python ../inbox-extension/generate_contracts.py
```

The wheel declares a `pythonnative.plugins` entry point. Its `pn_plugin.json`
points to the generated schema and Swift and Kotlin registration entry points.
Build discovery reads package metadata without importing target code.

From this directory, check types (with the extension's typed facade) and the
rules of hooks:

```sh
MYPYPATH=../inbox-extension/src uv run mypy --strict app
uv run pn lint app
```

Run the complete mobile acceptance flow from the repository root:

```sh
uv run scripts/run-e2e.sh ios inbox
uv run scripts/run-e2e.sh android inbox
```

The flow resets this example app's data, searches, edits and closes an issue,
saves it, restarts the process, and verifies the persisted result. Both mobile
CI matrices include this flow, with the extension installed from its wheel.
`tests/test_inbox.py` runs the same search, edit, and persistence steps, plus
the rollback, without a device.
