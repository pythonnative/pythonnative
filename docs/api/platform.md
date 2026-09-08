# Platform

The [`Platform`][pythonnative.Platform] class exposes runtime
information about the host platform and a `select` helper for writing
platform-aware code without scattering `if IS_IOS` / `if IS_ANDROID`
branches throughout the codebase.

::: pythonnative.platform
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Quick reference

| Attribute | Values |
|---|---|
| `Platform.OS` | `"ios"`, `"android"`, `"web"`, or `"test"` |
| `Platform.Version` | Best-effort OS version string |
| `Platform.is_ios` / `Platform.is_android` / `Platform.is_web` / `Platform.is_test` | Booleans |
| `Platform.select(spec, default=None)` | Pick a value matching the current platform |

- `"web"` means the `pn preview` browser preview.

## See also

- [Window dimensions, safe area, keyboard hooks](hooks.md) for
  reactive metric access.
