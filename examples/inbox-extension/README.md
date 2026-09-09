# Inbox extension

A separately distributed PythonNative extension with a native `InboxBadge` and
an `InboxTools` service. Python annotations generate the shared contract; native
implementations inherit the generated module adapters. The `pythonnative.plugins`
entry point and package data make discovery work after wheel installation.

From the repository root:

```sh
PYTHONPATH=examples/inbox-extension/src python examples/inbox-extension/generate_contracts.py
uv build --wheel examples/inbox-extension --out-dir examples/inbox/vendor
```

The Inbox reference app consumes the wheel. Its mobile acceptance jobs build the
native extension and exercise both its badge and module calls.
