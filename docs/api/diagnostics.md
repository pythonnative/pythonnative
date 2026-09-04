# Diagnostics

Developer-mode warnings and error reporting. This module powers the
feedback you get while developing: `[PN] WARN` messages for suspicious
props and styles, the [`HookOrderError`][pythonnative.HookOrderError]
raised on conditional hooks, and the RedBox overlay that surfaces
uncaught errors from renders, effects, and event handlers.

Dev mode is enabled automatically by `pn start` / `pn preview` and in
the debug builds `pn run` produces, or explicitly with the `PN_DEV=1`
environment variable.
In production builds every check in this module is skipped, so
shipping apps pay no overhead.

```python
import pythonnative as pn

if pn.diagnostics.is_dev():
    pn.diagnostics.warn("fetching from a staging endpoint")
```

Most apps never call this module directly; it exists so framework
code (and custom component libraries) can report problems in a way
that reaches the developer instead of disappearing into a log.

::: pythonnative.diagnostics
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members_order: source
      filters: ["!^_"]

## Next steps

- Catch render errors in the tree with
  [`ErrorBoundary`][pythonnative.ErrorBoundary]: see the
  [Error boundaries guide](../guides/error-boundaries.md).
- The rules of hooks and what `HookOrderError` means:
  [Hooks](../concepts/hooks.md).
