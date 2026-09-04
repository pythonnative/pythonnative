# Native modules

Cross-platform wrappers around device APIs that are not part of the
view tree: camera, GPS, file I/O, notifications, clipboard, share
sheet, deep links, permissions, connectivity, secure storage, battery,
haptics, and biometrics. Each module is a Swift and a Kotlin class
registered by name in the native runtime; the Python classes below are
facades that call them through
[`native_module`][pythonnative.native_modules.registry.native_module],
with a Python implementation registered for the desktop and tests.

Both synchronous and coroutine APIs exist (chosen to match the
platform call). For the call-site patterns, the reactive
`use_app_state` / `use_net_info` hooks, and the runtime coroutines are
scheduled on, see the [Native modules guide](../guides/native-modules.md)
and the [Async + data guide](../guides/async.md).

## Registry

::: pythonnative.native_modules.registry
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Desktop implementations

::: pythonnative.native_modules.fallback
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Camera

::: pythonnative.native_modules.camera
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Location

::: pythonnative.native_modules.location
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## File system

::: pythonnative.native_modules.file_system
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Notifications

::: pythonnative.native_modules.notifications
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Clipboard

::: pythonnative.native_modules.clipboard
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Share

::: pythonnative.native_modules.share
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Linking

::: pythonnative.native_modules.linking
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Permissions

::: pythonnative.native_modules.permissions
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## App state

::: pythonnative.native_modules.app_state
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Network connectivity

::: pythonnative.native_modules.net_info
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Secure storage

::: pythonnative.native_modules.secure_store
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Battery

::: pythonnative.native_modules.battery
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Haptics & vibration

::: pythonnative.native_modules.haptics
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Biometrics

::: pythonnative.native_modules.biometrics
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- See guidance and permission setup in [Native modules guide](../guides/native-modules.md).
- Write your own: [Native modules guide](../guides/native-modules.md#writing-your-own-native-module).
