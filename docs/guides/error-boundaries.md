# Error boundaries

[`ErrorBoundary`][pythonnative.ErrorBoundary] catches exceptions thrown
during render or commit of its child subtree and renders a fallback
instead. It's the difference between a single buggy widget showing a
"something went wrong" message and the entire screen disappearing into
a stack trace.

## When to use one

A good rule of thumb: wrap a boundary around any subtree whose failure
shouldn't take down the rest of the page. Common cases:

- Each route within a navigator (so navigation itself keeps working
  even if one screen crashes).
- A list item that renders user-supplied data (so one bad row doesn't
  hide the rest).
- A panel that loads from a third-party API (network errors, schema
  drift).

Don't wrap *every* component. Boundaries that are too granular hide
real bugs and add noise; boundaries at the wrong layer (above the
content you actually want to recover) defeat the purpose.

## The shape of a boundary

```python
import pythonnative as pn

@pn.component
def UserCard(user: dict[str, str]) -> pn.Node:
    return pn.Column(
        pn.Text(user["name"]),
        pn.Text(user["email"]),
    )

@pn.component
def App(users: list[dict[str, str]]) -> pn.Node:
    return pn.Column(
        *[
            pn.ErrorBoundary(
                UserCard(user),
                fallback=pn.Text("Failed to render this card"),
                key=user["id"],
            )
            for user in users
        ]
    )
```

The `fallback` may be a static [`Element`][pythonnative.Element], a
callable that receives the exception, or a callable that receives the
exception *and* a `reset` function:

```python
from collections.abc import Callable


def render_error(exc: BaseException, reset: Callable[[], None]) -> pn.Node:
    return pn.Column(
        pn.Text("Something went wrong", style={"font_size": 18, "bold": True}),
        pn.Text(repr(exc), style={"color": "#888"}),
        pn.Button("Retry", on_press=reset),
    )

pn.ErrorBoundary(child, fallback=render_error)
```

## What gets caught

- Exceptions raised inside a child `@component` function during
  render, including the synchronous part of an `async def` body.
- Exceptions raised by a child's
  [`use_layout_effect`][pythonnative.use_layout_effect] or
  [`use_effect`][pythonnative.use_effect] callback (the synchronous
  body, or the cleanup it returned). The reconciler routes them to the
  nearest boundary exactly like render errors; a failing effect never
  fails the native surface.
- `RuntimeError("Too many re-renders")`, raised from a component that
  keeps re-dirtying itself for more than fifty passes.

## What doesn't get caught

- Exceptions raised *inside an async task* after its first `await`:
  an `async def` effect that fails later, or a coroutine started with
  `pn.run_async`. Catch them at the boundary of the task, or surface
  the error via `set_state`. In dev mode these errors show the RedBox
  overlay instead of vanishing.
- Exceptions in event handlers (`on_press`, `on_change`). Handlers
  fire later, on user interaction. Use `try/except` inside the
  handler. Dev mode routes these to the RedBox too.
- Exceptions raised from threads you start yourself.

## Recovery

Once a boundary shows its fallback, the subtree stays in the fallback
state until it's reset. Use the `reset` callable passed to the
fallback; it clears the error and remounts the original children with
fresh state:

```python
pn.ErrorBoundary(
    FlakySection(),
    fallback=lambda exc, reset: pn.Column(
        pn.Text(f"Error: {exc}"),
        pn.Button("Retry", on_press=reset),
    ),
)
```

Changing the boundary's `key` from a parent also works (it unmounts
the old boundary instance entirely), but `reset` is simpler and keeps
the boundary's position in the tree stable.

## Reporting errors

The boundary is also the right place to wire crash reporting. Pass an
`on_error` callback; it fires once when the boundary catches, before
the fallback mounts:

```python
pn.ErrorBoundary(
    child,
    fallback=pn.Text("We hit a snag. The team has been notified."),
    on_error=lambda exc: crash_reporter.send(exc),
)
```

Most crash reporters (Sentry, Bugsnag, etc.) ship Python clients that
work fine inside the embedded CPython runtime, although you'll
need to declare them in `[requirements].packages` so the bundler picks
them up.

## Errors no boundary caught

Every uncaught error, in any build, reaches
[`pn.set_error_handler`][pythonnative.diagnostics.set_error_handler], with the phase it came from.
That includes the handler and task errors a boundary can't see, so it's the one place a crash reporter
needs to attach:

```python
pn.set_error_handler(lambda error, phase: crash_reporter.capture(error, tags={"phase": phase}))
```

Development builds show the error screen. A release build has no error screen, so it wraps each screen in
a boundary of its own. A render error no boundary of yours caught replaces the screen with a message and
a "Try again" button that remounts it with fresh state. Replace that screen with
[`pn.set_error_fallback`][pythonnative.set_error_fallback], which takes the same forms as `fallback`:

```python
pn.set_error_fallback(lambda error, reset: SorryScreen(on_retry=reset))
```

Errors in event handlers and tasks don't replace the screen. They reach the handler, and the app carries on.

If the UI thread can't mount an update, the screen remounts with a fresh tree once. A second failure
within a minute means the tree itself is the problem, so it shows the fallback instead of looping.

## Boundaries vs `use_effect` cleanup

Effect cleanups always run on unmount, even when an exception triggered
the unmount. That's by design; you can rely on cleanups to release
resources (timers, subscriptions, file handles) without checking
whether the unmount was "graceful".

## Next steps

- Read the wider rendering model: [Reconciliation](../concepts/reconciliation.md).
- Wire up logging for the rest of your app: [Hot reload](hot-reload.md)
  (because hot-reload's log stream is also where boundary fallbacks
  print their messages).
