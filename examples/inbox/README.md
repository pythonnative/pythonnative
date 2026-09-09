# Offline inbox

This reference app combines one shared repository, 2,000 immutable issue records,
variable-height native list rows, deferred search, a detail form, optimistic
persistence with rollback, and native stack navigation. Its separately packaged
extension exercises generated props and synchronous and asynchronous module adapters.

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

Run the complete mobile acceptance flow from the repository root:

```sh
uv run scripts/run-e2e.sh ios inbox
uv run scripts/run-e2e.sh android inbox
```

The flow resets this example app's data, searches, edits and closes an issue,
saves it, restarts the process, and verifies the persisted result. Both mobile
CI matrices include this flow, with the extension installed from its wheel.
