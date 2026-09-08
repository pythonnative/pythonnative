# CLI (`pn`)

Reference for the `pn` console script. The implementation lives in
`pythonnative.cli.pn`; this page renders its docstrings directly so
the documented behavior never drifts from the code.

## Subcommands

- `pn init [name]`: scaffold a new project (creates `app/`,
  `pythonnative.toml`, `.gitignore`). With a name it creates `./<name>/`
  and scaffolds into it; the name must match `^[a-z][a-z0-9_-]*$`.
  Without one it uses the current directory, whatever it's called.
  Flag: `--force` to overwrite existing files or scaffold into a
  non-empty directory. See [Configuration](../guides/configuration.md).
- `pn doctor [android|ios]`: diagnose the local toolchain and validate
  `pythonnative.toml`, including that a `python3.X` matching
  `[app].python_version` is available for package resolution. Exits
  non-zero when something will block a build.
- `pn deps [android|ios]`: resolve `[requirements].packages` for every
  device target (iOS device, iOS Simulator, and each Android ABI)
  without installing anything, and report the wheel each package would
  use, flagging binary wheels, their index, and downgrades. Flags:
  `--json` for a machine-readable report, `--python` to pick the
  interpreter that runs pip. Exits non-zero when any target can't be
  satisfied. See [PyPI packages](../guides/pypi-packages.md).
- `pn start [entry]`: run the dev server. It watches `app/`, syncs
  every save to each connected debug build with Fast Refresh, relays
  their logs, and serves the browser preview page. Flags: `--port`
  (default 8765), `--host` (default `0.0.0.0`), `--open` to also open
  the browser preview. See the
  [Development workflow](../guides/dev-workflow.md).
- `pn preview [entry]`: `pn start` plus opening the browser preview in
  your default browser. Flags: `--port`, `--host`, `--no-open`. See the
  [Browser preview guide](../guides/browser-preview.md).
- `pn devices [android|ios]`: list connected devices, emulators, and
  simulators with the identifiers `--device` accepts. Flag: `--json` to
  print a JSON array to stdout for scripting; the "no devices" hints go
  to stderr instead, and an empty list prints `[]` and exits 0.
- `pn run android|ios`: build, install, and launch a debug build that
  connects to the running dev server. The native toolchain runs only
  when a native input changed (config, template, `pythonnative`
  itself, native plugins); otherwise the previous artifact is
  reinstalled. Flags: `--device` (target a specific device by
  identifier or name), `--prepare-only`, `--no-logs`, `--rebuild`
  (force the toolchain), `--dev-server URL` (override the server URL
  baked into the app), `--port` (where `pn start` listens),
  `--dev-client` (build a shell app with a connect screen that loads
  any project from a dev server).
- `pn logs android|ios`: stream logs from the running app without
  rebuilding. Flag: `--device` (target a specific device by identifier
  or name, same as `pn run`). Physical iOS devices aren't supported for
  log streaming; use Console.app or Xcode > Devices and Simulators.
- `pn build android|ios`: build distributable artifacts (release by
  default). Flags: `--debug` for the debug variant, `--upload` to send
  an iOS release build to App Store Connect. See
  [Building for release](../guides/building-for-release.md).
- `pn app-id android|ios`: print the resolved application id (Android)
  or bundle id (iOS), handy for scripts and CI.
- `pn clean`: remove the local `build/` directory.
- `pn --version` (`-V`): print the installed PythonNative version.

::: pythonnative.cli.pn
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See the [Getting started](../getting-started.md) walkthrough.
- Read the [Development workflow](../guides/dev-workflow.md) for how
  `pn start` and `pn run` work together.
