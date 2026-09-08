# Offline inbox

This reference app combines one shared repository, 2,000 immutable issue records,
variable-height native list rows, deferred search, a detail form, optimistic
persistence with rollback, and native stack navigation. The local extension
exercises generated props and synchronous and asynchronous module adapters.

From this directory, run `pn run ios` or `pn run android`. Use `pn preview` for
the browser version. The native extension badge appears on mobile devices.

After changing `app/native_contracts.py`, run `python generate_contracts.py` and
rebuild the app. `native/pn_plugin.json` points at the generated schema and the
Swift and Kotlin registration entry points. It doesn't import target code during
the build.

Run the native acceptance flow from the repository root:

```sh
maestro --device DEVICE_ID test -e APP_ID=dev.pythonnative.inbox tests/e2e/reference/inbox.yaml
```

The flow resets this example app's data, searches, edits and closes an issue,
saves it, restarts the process, and verifies the persisted result.
