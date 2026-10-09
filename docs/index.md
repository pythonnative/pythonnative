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
def Counter(initial: int = 0) -> pn.Node:
    count, set_count = pn.use_state(initial)
    return pn.Column(
        pn.Text(f"Count: {count}", style=pn.style(font_size=24, bold=True)),
        pn.Button("+", on_press=lambda: set_count(count + 1)),
        style=pn.style(gap=12, padding=16),
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
- **Typed from end to end.** A component's signature is its prop
  list and it returns a [`pn.Node`][pythonnative.element.Node], so a
  strict type checker verifies element trees, props, and conditional
  children. [`pn.Style`][pythonnative.style.Style] is a `TypedDict`
  with `Literal` enums for every fixed-value field, so mypy and your
  editor catch typos in `align_items` or `font_weight` before the app
  ever runs.
- **Screens are components.** A screen's parameters are its route
  params, so `nav.push(ItemScreen(id=42))` is a checked call.
  Navigators are module-level values, and deep links come from each
  screen's `path`. See [Navigation](guides/navigation.md).
- **Native-backed navigation.** Every stack drives the platform's real
  navigation controller (fragments on Android, `UINavigationController`
  on iOS), so transitions, back gestures, and state preservation are
  exactly what users expect from a first-class native app.
- **One theme, typed style sheets, and stores.** A
  [`Theme`][pythonnative.Theme] dataclass styles the app and its
  navigators and follows dark mode;
  [`StyleSheet`][pythonnative.StyleSheet] namespaces give styles typed
  names; and a [`Store`][pythonnative.Store] holds app state with
  targeted re-renders. See [Styling](guides/styling.md) and
  [Managing state](guides/state.md).
- **A Metro-style dev loop with PythonNative Go.** `pn start` runs one
  dev server for the browser preview and every connected app, and prints
  a QR code. PythonNative Go, a prebuilt dev client, runs any project
  without native code on a simulator, emulator, or phone with no native
  build. Save a file and each client Fast Refreshes in place, preserving
  component state. See the [Development workflow](guides/dev-workflow.md)
  and [PythonNative Go and DevTools](guides/devtools.md).
- **DevTools and breakpoints.** A DevTools page shows the component tree
  with props and hooks, a REPL inside the running app, problems,
  network requests, and performance. VS Code attaches `debugpy`
  breakpoints to the Python running on a phone. See
  [Debugging](guides/debugging.md).
- **Dev-mode diagnostics.** Uncaught errors show a full-screen error
  screen with the component stack and your source instead of crashing; typos in style keys and
  duplicate list keys print "did you mean" warnings; props that don't
  match a component's annotations warn; conditional hooks raise at the
  source. Every check is skipped in production, and
  [`pn lint`](guides/linting.md) catches hook mistakes before you run
  the app.
- **Browser preview.** `pn preview` renders your app in a browser tab
  inside a phone frame, through the same bridge protocol the Swift and
  Kotlin runtimes speak, so you can iterate on UI, state, and
  navigation in milliseconds (no simulator boot required). See the
  [Browser preview guide](guides/browser-preview.md).
- **An extension SDK.** [`pythonnative.sdk`](api/sdk.md) lets you
  wrap any platform widget as a first-class element with
  type-checked props through
  [`define_component`][pythonnative.sdk.define_component], generates
  the Swift and Kotlin contract from the same declaration, and PyPI
  plugins auto-register through the `pythonnative.handlers` entry-point
  group.
- **A small surface.** A handful of element factories, a handful of
  hooks, and three navigators.

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
