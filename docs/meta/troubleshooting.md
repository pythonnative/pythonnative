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

### `Refusing to overwrite existing non-empty directory: my_app/`

`pn init my_app` creates `my_app/` and scaffolds into it, so it stops
when that directory already holds files. Pass `--force` to scaffold over
it, choose a different name, or run `pn init` from inside the directory
to use it as is. An existing but empty directory is fine.

### `Refusing to overwrite existing file: my_app`

Something other than a directory is already at `./my_app`. `--force`
won't help here, since `pn init` can't turn a file into a directory.
Remove or rename it, or choose a different project name.

### `Refusing to treat a path as a project name: '../app'`

`pn init` takes a single directory name, not a path, so the project always
lands inside the current directory. Pass a plain name like `my_app`, or
`cd` to the directory you want the project in and run `pn init` with no
name at all. `--force` doesn't lift this one.

### `Invalid project name: 'MyApp'`

A name you pass to `pn init` has to match `^[a-z][a-z0-9_-]*$`: lowercase
letters, digits, `-`, and `_`, starting with a letter. That's the same
spirit as `flutter create` and `cargo new`, and it keeps the directory
name and the `name` field in the config identical. The error suggests a
legal name you can paste straight back, so `MyApp` suggests `myapp` and
`my app` suggests `my_app`. `--force` doesn't lift this one.

This applies only to a name you type. `pn init` with no name takes the
current directory's name as-is, so a directory called `MyProject` is
fine. To use a display name outside this set, edit `display_name` in
`pythonnative.toml` after scaffolding.

### `Refusing to scaffold through a link or outside the current directory: link`

The name resolves somewhere other than a directory directly inside the
current one, so `pn init` stops rather than writing through it. A symlink
at `./link` is the usual cause. Scaffold into a real directory, or `cd` to
the directory the link points at and run `pn init` with no name. `--force`
doesn't lift this one either.

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

## Fast Refresh

### Edits don't appear

- Is `pn start` (or `pn preview`) running? Debug builds connect to it
  on launch; the terminal prints `[pn] ios <device> connected` when
  one arrives. If you launched `pn run` with no server up, the app is
  running its bundled sources: start the server and relaunch.
- Is the device on the same network? Simulators and emulators reach
  the server through `localhost` (Android via `adb reverse`), but a
  physical iPhone needs your Mac's LAN address and an open port. Pass
  `--dev-server ws://<ip>:8765/ws?role=client` to `pn run` if the
  auto-detected address is wrong.
- The watcher only sees files under `app/`. Code outside `app/` needs
  a rebuild.
- Top-level side effects re-run on each reload; if your module
  registers something into a global on import, the *second* import
  may raise. See [Fast Refresh guide](../guides/hot-reload.md#common-pitfalls).

### `pn run` rebuilt the whole native project after a Python edit

It shouldn't: edits under `app/` sync through the dev server. A
rebuild means a native input changed (`pythonnative.toml`, the
`pythonnative` package version, native plugins) or no dev server was
running when `pn run` started. See
[When native rebuilds happen](../guides/dev-workflow.md#when-native-rebuilds-happen).

### The browser preview shows a blank frame

Open its console (`` ` ``) and check the `pn start` terminal. The usual
cause is an import error in the entry module, often a package from
`[requirements].packages` that isn't installed in the environment
running `pn start`; the CLI warns about those on startup.

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
