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

The `fallback` may be a static [`Element`][pythonnative.Element] or a
callable that receives the exception:

```python
def render_error(exc: BaseException):
    return pn.Column(
        pn.Text("Something went wrong", style={"font_size": 18, "bold": True}),
        pn.Text(repr(exc), style={"color": "#888"}),
    )

pn.ErrorBoundary(child, fallback=render_error)
```

## What gets caught

- Exceptions raised inside a child `@component` function during
  render.
- Exceptions raised inside a child
  [`ViewHandler`][pythonnative.native_views.base.ViewHandler]'s
  `create_view` or `update_view` while the boundary is reconciling
  that subtree.

## What doesn't get caught

- Exceptions inside [`use_effect`][pythonnative.use_effect] callbacks
  (effects run *after* commit, so the boundary has already reported
  success). Wrap the callback body in `try/except` and surface the
  error via `set_state`.
- Exceptions in event handlers (`on_click`, `on_change`). Same
  reasoning: handlers fire later, on user interaction. Use
  `try/except` inside the handler.
- Exceptions raised from threads or async tasks scheduled by your
  code. Catch them at the boundary of the task.

## Recovery

Once a boundary shows its fallback, the subtree stays in the fallback
state until something forces it to remount. The simplest reset is to
change a parent prop or `key`:

```python
@pn.component
def Panel():
    nonce, set_nonce = pn.use_state(0)
    return pn.Column(
        pn.ErrorBoundary(
            FlakySection(),
            fallback=lambda exc: pn.Column(
                pn.Text(f"Error: {exc}"),
                pn.Button("Retry", on_click=lambda: set_nonce(nonce + 1)),
            ),
            key=nonce,
        )
    )
```

Bumping `nonce` changes the boundary's key, which causes the
reconciler to unmount the old boundary instance and mount a fresh one
that retries the render.

## Reporting errors

The boundary is also the right place to wire crash reporting. Pass a
callable fallback and report the exception there:

```python
def reporting_fallback(exc: BaseException):
    crash_reporter.send(exc)
    return pn.Text("We hit a snag. The team has been notified.")
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
