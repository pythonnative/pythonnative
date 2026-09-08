# PythonNative

PythonNative is a cross-platform toolkit for building native **Android**
and **iOS** apps in plain Python. The component model is React-style
(function components plus hooks plus a reconciler); rendering and
device APIs are native Swift and Kotlin, driven over a small bridge
with one transaction per commit. Application components run in Python.

## A taste

```python
import pythonnative as pn


@pn.component
def Counter(initial: int = 0):
    count, set_count = pn.use_state(initial)
    return pn.Column(
        pn.Text(f"Count: {count}", style=pn.style(font_size=24, bold=True)),
        pn.Button("+", on_press=lambda: set_count(count + 1)),
        style=pn.style(spacing=12, padding=16),
    )
```

That same `Counter` mounts as a `UILabel` plus a `UIButton` inside a
`UIView` on iOS, and as a `TextView` plus a `Button` inside a
`FrameLayout` on Android. The shared Yoga layout engine interprets
`flex`, `padding`, and `position` beside the native widgets.
Platform controls and fonts supply their own intrinsic sizes.

## Why PythonNative?

- **Real native widgets.** UIKit and Android controls provide platform
  behavior. Configure accessibility labels and roles, and test navigation
  and interaction on each platform.
- **A familiar component model**. If you know React or React Native,
  you already know how PythonNative works.
- **Python application code.** Components run on a dedicated asyncio
  application thread. Validated commits connect Python state to native widgets.
- **Ordinary asyncio.** One standard application loop runs Python work
  independently of the native UI thread. Components can be `async def` and await data right in
  the body, with [`Suspense`][pythonnative.Suspense] providing the
  loading state declaratively. See the
  [Async + data guide](guides/async.md).
- **Typed styling.** [`pn.Style`][pythonnative.style.Style] is a
  `TypedDict` with `Literal` enums for every fixed-value field, so
  mypy and your editor catch typos in `align_items` or
  `font_weight` before the app ever runs. The
  [`pn.style(...)`][pythonnative.style.style] helper makes the
  call sites tidy.
- **Native-backed navigation.** The root `Stack.Navigator` drives
  the platform's real navigation controller (Android Navigation
  Component fragments on Android, `UINavigationController` on iOS),
  so transitions, back gestures, and state preservation are exactly
  what users expect from a first-class native app.
- **A Metro-style dev loop.** `pn start` runs one dev server for the
  browser preview and every connected debug build. Save a file and
  each client Fast Refreshes in place, preserving component state;
  their logs stream back into the same terminal. See the
  [Development workflow](guides/dev-workflow.md).
- **Dev-mode diagnostics.** Uncaught errors show a full-screen RedBox
  with the traceback instead of crashing; typos in style keys and
  duplicate list keys print "did you mean" warnings; conditional
  hooks raise at the source. Every check is skipped in production.
- **Browser preview.** `pn preview` renders your app in a browser tab
  inside a phone frame, through the same bridge protocol the Swift and
  Kotlin runtimes speak, so you can iterate on UI, state, and
  navigation in milliseconds (no simulator boot required). See the
  [Browser preview guide](guides/browser-preview.md).
- **An extension SDK.** [`pythonnative.sdk`](api/sdk.md) lets you
  wrap any platform widget as a first-class element with
  type-checked props, and PyPI plugins auto-register through the
  `pythonnative.handlers` entry-point group.
- **A small surface.** A handful of element factories, a handful of
  hooks, and one navigation primitive.

## Quick links

- New here? Start with [Getting started](getting-started.md).
- Want to see it run right now? Try the
  [Browser preview](guides/browser-preview.md).
- Want the bigger picture? Read [Mental model](concepts/mental-model.md).
- Looking up an API? [Package overview](api/pythonnative.md).
- Wrapping a custom widget? Read
  [Custom native components](guides/custom-native-components.md).
- Stuck on an error? Try [Troubleshooting](meta/troubleshooting.md).

## Project status

PythonNative is under active development. The public API documented
on this site is the supported surface; expect breaking changes only at
minor version bumps until 1.0. See the
[Changelog](meta/changelog.md) for what shipped in each release.

## Get involved

- Source code:
  [github.com/pythonnative/pythonnative](https://github.com/pythonnative/pythonnative).
- File a bug or feature request:
  [GitHub issues](https://github.com/pythonnative/pythonnative/issues).
- Contribute: [Contributing](meta/contributing.md).

## Next steps

- Install and scaffold your first project: [Getting started](getting-started.md).
- Learn how the runtime fits together: [Architecture](concepts/architecture.md).
