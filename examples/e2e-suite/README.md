# PythonNative E2E Suite

A comprehensive demo app that exercises every public feature in `pythonnative`. It is the target of the top-level Maestro E2E suite and doubles as a living reference for the framework's surface area.

Unlike `examples/hello-world`, this app is not a marketing demo: it is structured for automated testing. Each PythonNative feature gets a dedicated screen that:

- Renders a stable, unique title (so Maestro can wait for the screen to appear).
- Exposes interactive controls with stable, unique labels (so Maestro can tap them).
- Prints a "Result:" line that reflects the feature's state (so Maestro can assert behavior, not just rendering).

## Running locally

From the repo root:

```bash
cd examples/e2e-suite
pn run android    # or: pn run ios
```

Then, in another shell:

```bash
# Android
maestro test tests/e2e/android.yaml

# iOS (use --platform ios if Android is also connected)
maestro --platform ios test tests/e2e/ios.yaml
```

## Adding a new feature demo

1. Add a screen module under `app/screens/<category>/<feature>.py` exporting a `pn.component`-decorated function.
2. Register it in `app/registry.py` with a unique `id`.
3. Add a Maestro flow at `tests/e2e/flows/<category>/<feature>.yaml` that opens the screen via its registry `id` and asserts the expected behavior.
4. Re-run `scripts/check-e2e-coverage.py` to make sure every public symbol in `pythonnative.__all__` is covered by a flow.

See `tests/e2e/AGENTS.md` for a deeper tour of how AI agents should interact with this suite.
