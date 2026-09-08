# Dev server and dev client

The development loop is a server process (`pn start`) and any number of
clients: the browser preview and debug builds on simulators, emulators,
and devices. See the [Development workflow](../guides/dev-workflow.md)
guide for how they fit together; this page documents the modules.

## `pythonnative.devserver`

::: pythonnative.devserver
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

### Server

::: pythonnative.devserver.server
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

### File watcher and source snapshots

::: pythonnative.devserver.watcher
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

### WebSocket

::: pythonnative.devserver.ws
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## `pythonnative.devclient`

::: pythonnative.devclient
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## `pythonnative.preview`

::: pythonnative.preview
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## `pythonnative.bridge.web`

::: pythonnative.bridge.web
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## `pythonnative.project.fingerprint`

::: pythonnative.project.fingerprint
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- [Fast Refresh](../guides/hot-reload.md) and the
  [hot reload API](hot_reload.md) for the device-side reload.
- [Browser preview](../guides/browser-preview.md).
