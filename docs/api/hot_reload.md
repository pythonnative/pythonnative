# Hot reload

Fast Refresh comes in two cooperating pieces: the
[dev server](devserver.md) that watches `app/` and pushes changed files
to every connected client, and this device-side module reloader that
swaps the new code in and refreshes every mounted screen. Debug builds
launched with `pn run` while `pn start` is running are wired up
automatically.

::: pythonnative.hot_reload
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See the workflow in the [Fast Refresh guide](../guides/hot-reload.md).
- The other half: [Dev server and dev client](devserver.md).
