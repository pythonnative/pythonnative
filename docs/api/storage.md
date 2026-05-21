# Storage

Key/value persistence backed by the platform-native store
(`NSUserDefaults` on iOS, `SharedPreferences` on Android, a local
JSON file in desktop tests). All operations are coroutines so they
don't block the framework loop.

::: pythonnative.storage
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Patterns

- **Token / session storage**: write strings with
  [`set`][pythonnative.AsyncStorage] and read with
  [`get`][pythonnative.AsyncStorage].
- **Complex values**: use
  [`set_json`][pythonnative.AsyncStorage] /
  [`get_json`][pythonnative.AsyncStorage] for dicts, lists, and
  primitives.
- **Component state that survives restarts**: reach for
  [`use_persisted_state`][pythonnative.use_persisted_state] instead
  of manually wiring an effect to `AsyncStorage`.

## Next steps

- The pattern is walked through end-to-end in the
  [Async + data guide](../guides/async.md).
