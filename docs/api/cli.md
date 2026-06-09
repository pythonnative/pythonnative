# CLI (`pn`)

Reference for the `pn` console script. The implementation lives in
`pythonnative.cli.pn`; this page renders its docstrings directly so
the documented behavior never drifts from the code.

## Subcommands

- `pn init [name]`: scaffold a new project (creates `app/`,
  `pythonnative.toml`, `.gitignore`). Flag: `--force` to overwrite
  existing files. See [Configuration](../guides/configuration.md).
- `pn doctor [android|ios]`: diagnose the local toolchain and validate
  `pythonnative.toml`. Exits non-zero when something will block a build.
- `pn preview [component]`: render the app in a desktop (Tkinter) window
  with Fast Refresh — the fastest way to iterate on UI. Flags:
  `--width`, `--height`, `--title`, `--no-hot-reload`. See the
  [Desktop preview guide](../guides/desktop-preview.md).
- `pn run android|ios`: build and run on a connected device or
  simulator. Flags: `--prepare-only`, `--hot-reload`, `--no-logs`.
- `pn build android|ios`: build distributable artifacts (release by
  default). Flag: `--debug` for the debug variant. See
  [Building for release](../guides/building-for-release.md).
- `pn app-id android|ios`: print the resolved application id (Android)
  or bundle id (iOS) — handy for scripts and CI.
- `pn clean`: remove the local `build/` directory.

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
