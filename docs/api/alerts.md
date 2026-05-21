# Alerts

The [`Alert`][pythonnative.alerts.Alert] class provides imperative
access to the host platform's alert dialogs and action sheets. Alerts
are *not* part of the element tree.

There are three entry points:

- [`Alert.show`][pythonnative.alerts.Alert.show]: fire-and-forget
  one-button notice (no return value).
- [`Alert.confirm`][pythonnative.alerts.Alert.confirm]: awaitable
  two-button yes/no, resolves to a ``bool``.
- [`Alert.choose`][pythonnative.alerts.Alert.choose]: awaitable
  multi-button picker / action sheet, resolves to the selected
  label (or ``None`` if dismissed).

::: pythonnative.alerts
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Patterns

- **Confirm before destructive actions**: ``await pn.Alert.confirm(...)``
  inside an `async def`, then branch on the boolean result.
- **Pick from options**: ``await pn.Alert.choose(title, options=[...])``
  returns the selected label.
- **Pickers**: the built-in
  [`Picker`][pythonnative.components.Picker] component is
  implemented on top of action sheets — use it for select/dropdown
  widgets.

## Testing

When running off-device (e.g., in unit tests), the alert dispatch
records each call to `Alert._test_log` instead of presenting a
dialog. Use
[`Alert.set_test_response(*indices)`][pythonnative.alerts.Alert.set_test_response]
to script the user's choices for upcoming ``confirm`` / ``choose``
calls. Reset the log with `Alert._test_log.clear()` between cases.
