# PythonNative E2E Suite

A comprehensive demo app that exercises every public feature in `pythonnative`. It's the target of the top-level Maestro E2E suite and doubles as a living reference for the framework's surface area.

It's structured for automated testing. Each PythonNative feature gets a dedicated screen that:

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

## How the app is built

- `app/main.py` defines `Root`, a module-level `pn.StackNavigator` built from the registry. Every demo is a `pn.Screen` named after its registry `id`, so route names stay stable for the flows. `App` wraps it in a `pn.NavigationContainer` bound to the app-wide `pn.NavigationRef` in `app/navigation_ref.py`.
- A `pn.ThemeProvider` supplies the suite's light and dark themes from `app/app_theme.py`, a `pn.Theme` subclass with one extra token. The provider follows the color scheme, so a demo that calls `pn.appearance.set_color_scheme` repaints the app and the navigator chrome.
- `app/theme.py` holds the shared styles: layout styles on a `pn.StyleSheet` class and theme colors on a class built with `pn.use_styles`.
- `app/screens/scaffold.py` holds the components every demo renders: `DemoScreen`, `DemoSection`, `ResultText`, `Hint`, `Label`, and `ButtonsRow`.
- Screens are components, and their parameters are their route params. The category list opens a demo with `nav.push(Demo())`, and demos navigate with typed targets such as `nav.push(ParamsPassingDemo(value="alpha"))`.

## Adding a new feature demo

1. Add a screen module under `app/screens/<category>/<feature>.py` exporting a `pn.component`-decorated function annotated `-> pn.Node`. Give every parameter a default so the category list can open it with no arguments.
2. Register it in `app/registry.py` with a unique `id`.
3. Add a Maestro flow at `tests/e2e/flows/<category>/<feature>.yaml` that opens the screen through its category and asserts the expected behavior, and list it in the category's suite under `tests/e2e/suites/` and in `tests/e2e/android.yaml` and `tests/e2e/ios.yaml`.
4. Re-run `scripts/check-e2e-coverage.py` to make sure every public symbol in `pythonnative.__all__` is covered by a flow.

## Checking the app

From the repo root:

```bash
uv run pytest -q tests/test_e2e_suite_renders.py    # renders every demo headlessly
uv run pn lint examples/e2e-suite/app
uv run scripts/check-e2e-coverage.py
(cd examples/e2e-suite && uv run --project ../.. mypy --strict app)
```

The root `mypy.ini` excludes this app because its top-level package is named `app`, like the other examples, so it's type-checked from its own directory.

See `tests/e2e/AGENTS.md` for a deeper tour of how AI agents should interact with this suite.
