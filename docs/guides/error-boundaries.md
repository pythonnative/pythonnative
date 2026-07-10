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
def UserCard(user):
    return pn.Column(
        pn.Text(user["name"]),
        pn.Text(user["email"]),
    )

@pn.component
def App(users):
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
def render_error(exc: BaseException, reset):
    return pn.Column(
        pn.Text("Something went wrong", style={"font_size": 18, "bold": True}),
        pn.Text(repr(exc), style={"color": "#888"}),
        pn.Button("Retry", on_press=reset),
    )

pn.ErrorBoundary(child, fallback=render_error)
```

## What gets caught

- Exceptions raised inside a child `@component` function during
  render.
- Exceptions raised inside a child
  [`ViewHandler`][pythonnative.native_views.base.ViewHandler]'s
  `create` or `update` while the boundary is reconciling
  that subtree.

## What doesn't get caught

- Exceptions inside [`use_effect`][pythonnative.use_effect] callbacks
  (effects run *after* commit, so the boundary has already reported
  success). Wrap the callback body in `try/except` and surface the
  error via `set_state`. In dev mode these errors show the RedBox
  overlay instead of vanishing.
- Exceptions in event handlers (`on_press`, `on_change`). Same
  reasoning: handlers fire later, on user interaction. Use
  `try/except` inside the handler. Dev mode routes these to the
  RedBox too.
- Exceptions raised from threads or async tasks scheduled by your
  code. Catch them at the boundary of the task.

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
work fine inside the Chaquopy or rubicon-objc runtime, although you'll
need to declare them in `[requirements].packages` so the bundler picks
them up.

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
