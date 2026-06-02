# CLI (`pn`)

Reference for the `pn` console script. The implementation lives in
`pythonnative.cli.pn`; this page renders its docstrings directly so
the documented behavior never drifts from the code.

## Subcommands

- `pn init [name]`: scaffold a new project (creates `app/`,
  `pythonnative.json`, `requirements.txt`, `.gitignore`).
- `pn preview [component]`: render the app in a desktop (Tkinter) window
  with Fast Refresh — the fastest way to iterate on UI. Flags:
  `--width`, `--height`, `--title`, `--no-hot-reload`. See the
  [Desktop preview guide](../guides/desktop-preview.md).
- `pn run android|ios`: build and run on a connected device or
  simulator. Flags: `--prepare-only`, `--hot-reload`, `--no-logs`.
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
