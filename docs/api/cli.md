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
- `pn preview [component]`: render the app in a desktop (Tkinter) window
  with Fast Refresh, the fastest way to iterate on UI. Flags:
  `--width`, `--height`, `--title`, `--no-hot-reload`. See the
  [Desktop preview guide](../guides/desktop-preview.md).
- `pn devices [android|ios]`: list connected devices, emulators, and
  simulators with the identifiers `--device` accepts. Flag: `--json` to
  print a JSON array to stdout for scripting; the "no devices" hints go
  to stderr instead, and an empty list prints `[]` and exits 0.
- `pn run android|ios`: build and run on a connected device or
  simulator. Flags: `--device` (target a specific device by identifier
  or name), `--prepare-only`, `--hot-reload`, `--no-logs`.
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
- Read about [Hot reload](../guides/hot-reload.md) when you turn on
  `--hot-reload`.
