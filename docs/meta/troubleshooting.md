# Troubleshooting

Quick fixes for the errors people hit most often. If you don't see
yours here, the [FAQ](faq.md) covers conceptual questions, and
[GitHub issues](https://github.com/pythonnative/pythonnative/issues)
is a good place to ask.

## Setup and the `pn` CLI

### `pn: command not found`

The `pn` console script is installed alongside the package. After
`pip install pythonnative`, make sure your environment's
`bin/Scripts` directory is on `PATH` (it usually is when you `source
.venv/bin/activate`). For a quick check:

```bash
python -c "import pythonnative; print(pythonnative.__file__)"
which pn
```

If `python -c ...` works but `which pn` returns nothing, your shell
is finding a different Python. Reactivate the venv or run
`python -m pythonnative.cli.pn ...` directly.

### `Refusing to overwrite existing: app/, pythonnative.toml, ...`

`pn init` won't clobber existing project files. Pass `--force` or
remove the listed files first.

### `Do not list 'pythonnative' in [requirements].packages`

The CLI bundles the installed `pythonnative` package directly into
your app, so listing it in `[requirements].packages` would install a
second copy and confuse imports. Remove the line and re-run `pn run`.

### `Could not find bundled template directory ...`

You're running from a partially-built checkout. Make sure templates
have been packaged: `pip install -e .` from the repo root, or
re-install `pythonnative` from PyPI.

## Android (`pn run android`)

### `'adb' not found on PATH`

Install the Android platform tools and either add their `adb` to
`PATH` or set `ANDROID_HOME` so Gradle can find it:

```bash
brew install --cask android-platform-tools
export ANDROID_HOME=$HOME/Library/Android/sdk
```

### Gradle complains about `JAVA_HOME`

`pn run android` will best-effort detect Homebrew's `openjdk@17`. For
other setups, point `JAVA_HOME` at a JDK 17 installation:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
```

### `INSTALL_FAILED_UPDATE_INCOMPATIBLE`

The signing key changed (e.g., a different machine, or you switched
between debug and release variants). Uninstall the old copy:

```bash
adb uninstall com.pythonnative.android_template
```

### App launches but `print()` output never appears

`pn run android` streams the relevant logcat tags by default
(`python.stdout`, `python.stderr`). If you passed `--no-logs`, run
`adb logcat python.stdout:V python.stderr:V *:S` in a separate
terminal.

## iOS (`pn run ios`)

### `xcodebuild` not found

Install the Xcode command-line tools:

```bash
xcode-select --install
```

For full iOS Simulator builds you also need the full Xcode app from
the Mac App Store; the bare command-line tools are not enough.

### `No available iOS Simulators found`

Open Xcode at least once to download a runtime, or:

```bash
xcrun simctl list devices available
```

If the list is empty, install one via `Xcode -> Settings -> Platforms`.

### `SHA256 mismatch for Python-Apple-support tarball`

The pinned upstream archive was rotated. Update PythonNative (`pip
install --upgrade pythonnative`); the new release will pin the new
asset. As a stopgap, you can clear the cached archive at
`build/ios/ios_runtime/` and re-run.

### App crashes on launch with `dyld: Library not loaded`

The embedded `Python.framework` did not get copied into the `.app`
bundle. This usually means the build was cancelled mid-flight; clean
and try again:

```bash
pn clean
pn run ios
```

### Blank screen on Simulator, no logs

`pn run ios` rewires `sys.stdout` to file descriptor 2 so `print()`
output reaches the launching terminal alongside `NSLog`. If you don't
see *any* logs, the simulator isn't attached yet; press `Ctrl+C` to
stop, then re-run with the default flags (no `--no-logs`).

## Renderer

### `RuntimeError: <hook> called outside a @component function`

Hooks may only be called inside the body of a `@pn.component`
function (or another hook called from there). Most often this happens
when:

- You called the hook at module scope.
- You called it inside a regular function that wasn't decorated.
- You called it inside a callback (e.g., `on_press`); move the hook
  to the top of the component and use the captured value.

### `RuntimeError: Hooks must be called in the same order on every render`

A hook was called conditionally:

```python
if user.is_logged_in:
    name, _ = pn.use_state("")  # bad: only called sometimes
```

Move the hook above the conditional and gate the *value* instead:

```python
name, set_name = pn.use_state("")
displayed = name if user.is_logged_in else "(guest)"
```

### "It rendered, then the screen went blank"

An exception escaped a render after the first frame. Wrap the
suspect subtree with [`ErrorBoundary`][pythonnative.ErrorBoundary] to
see the failure and keep the rest of the page alive. See
[Error boundaries guide](../guides/error-boundaries.md).

### Children don't update when the underlying list changes

You're either missing keys or using positional keys. See
[Reconciliation: keyed children](../concepts/reconciliation.md#keyed-children).

## Hot reload

### Edits don't appear

- Make sure you actually launched with `--hot-reload` (the run command
  prints `[hot-reload] Watching app/ for changes` when the watcher
  starts).
- The watcher only sees `.py` files under `app/`. Code outside `app/`
  needs a manual rebuild.
- Top-level side effects re-run on each reload; if your module
  registers something into a global on import, the *second* import
  may raise. See [Hot reload guide](../guides/hot-reload.md#common-pitfalls).

### "Stale closure" errors

A captured reference to the old version of a function survived the
reload. Restart the app to clear `sys.modules`.

## Tests

### Tests fail with `RuntimeError: No handler registered for type ...`

Install the fake backend from the
[Testing guide](../guides/testing.md#a-minimal-fake-backend) before
the first render. A session-scoped fixture is the easiest place.

### `mkdocs build --strict` fails on PR with autorefs warnings

Autorefs only resolves names that are actually documented. If you
referenced `[`Foo`][pythonnative.Foo]` but `Foo` isn't exported (or
has no docstring), the build fails. Either export it from
`pythonnative/__init__.py` or use a plain code span.

## Next steps

- Conceptual questions: [FAQ](faq.md).
- File a bug: [GitHub issues](https://github.com/pythonnative/pythonnative/issues).
