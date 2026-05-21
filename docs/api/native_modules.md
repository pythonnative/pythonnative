# Native modules

Cross-platform wrappers around device APIs that are not part of the
view tree: camera and photo gallery, GPS, app-scoped file I/O, and
local notifications. Each module is implemented twice (once per
platform) and dispatches at runtime based on the `IS_ANDROID` and
`IS_IOS` flags from `pythonnative.utils`.

Apart from `FileSystem`, every public method is a coroutine: ``await
Camera.take_photo()``, ``await Location.get_current()``, and so on.
For the call-site patterns and the runtime they're scheduled on, see
the [Async + data guide](../guides/async.md).

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

## Next steps

- See guidance and permission setup in [Native modules guide](../guides/native-modules.md).
