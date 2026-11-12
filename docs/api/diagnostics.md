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
from pythonnative import diagnostics

if diagnostics.is_dev():
    diagnostics.warn("fetching from a staging endpoint")
```

Most apps never call this module directly; it exists so framework
code (and custom component libraries) can report problems in a way
that reaches the developer instead of disappearing into a log.

## Startup timeline

Every launch, in release builds too, logs one line to the device log
once the first screen's first commit is acknowledged:

```text
[PN] startup: framework 182 ms, contracts 9 ms, bridge 30 ms, app 310 ms, render 41 ms, commit 28 ms, total 640 ms
```

[`startup_timeline`][pythonnative.diagnostics.startup_timeline] returns
the same numbers as a dict, and a running
[profiler](../guides/dev-workflow.md#profiling) records them as
`startup.<phase>_ms` gauges. The docstring below says what each phase
covers.

[](){ #pythonnative.diagnostics }

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
