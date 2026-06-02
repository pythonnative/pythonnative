# FAQ

Conceptual questions about PythonNative. For specific error messages
and their fixes, see [Troubleshooting](troubleshooting.md).

## Why "PythonNative" and not, say, Toga or Kivy?

PythonNative renders **real** native widgets via Chaquopy on Android
and rubicon-objc on iOS. A `pn.Text` becomes a `UILabel` /
`TextView`; a `pn.Button` becomes a `UIButton` / `Button`.
Accessibility, theming, and platform behaviors come along for free.

The component model is React-style (functions plus hooks plus a
reconciler) so you get a familiar declarative API on top of those
native widgets, instead of an imperative widget toolkit. There is no
JavaScript bridge: native APIs are direct method calls from Python.

## Can I write Android-only or iOS-only code?

Yes. Two patterns:

- **Branch on `IS_ANDROID` / `IS_IOS`** for small differences inside
  a shared component:

    ```python
    from pythonnative.utils import IS_ANDROID, IS_IOS

    if IS_ANDROID:
        ...
    elif IS_IOS:
        ...
    ```

- **Per-platform native modules** for larger pieces (a custom widget,
  a device API). Implement once per platform behind a single Python
  facade. See [Native modules guide](../guides/native-modules.md).

## How do I add a new widget?

Implement a [`ViewHandler`][pythonnative.native_views.base.ViewHandler]
for each platform you support, register it on
[`get_registry()`][pythonnative.native_views.get_registry], and write
a small Python factory that returns
`Element(<type>, props, children)`. Step-by-step instructions live in
[Native views (concept)](../concepts/native-views.md#custom-widgets).

## Does PythonNative work on the desktop?

Yes — for **previewing**. `pn preview` renders your app in a native
desktop window using a built-in Tkinter backend, with instant Fast
Refresh on every save. It's the fastest inner-loop: see your real UI
and iterate in seconds without booting a simulator or deploying to a
device. The same flex layout engine and reconciler drive it, so what
you see closely matches the device. See the
[Desktop preview guide](../guides/desktop-preview.md).

The desktop backend is a **development tool**, not a production target:
chrome like rounded corners, shadows, and overflow clipping are
approximated, and there's no app packaging for desktop. Ship to devices
with `pn run android` / `pn run ios`.

The core (components, hooks, reconciler) is also platform-agnostic and
runs headless with a [mock registry](../guides/testing.md#a-minimal-mock-registry) —
that's how the unit-test suite works.

## How do I package and distribute my app?

`pn run android` and `pn run ios` produce installable artifacts in
`build/`:

- Android: `build/android/android_template/app/build/outputs/apk/`.
- iOS: `build/ios/ios_template/build/Build/Products/Debug-iphonesimulator/ios_template.app`.

For release distribution, treat the staged template directory as a
normal Android Studio / Xcode project (sign, archive, upload via
Play Console / App Store Connect).

## Can I use any Python package?

Pure-Python packages, mostly yes. The `pn` CLI installs your
`requirements.txt` into the bundled site:

- **Android**: Chaquopy installs them into the APK at build time.
- **iOS**: pure-Python packages are copied into the app bundle's
  `platform-site/`.

C extensions are harder. You need a wheel that targets the right
platform / architecture (`armeabi-v7a` and `arm64-v8a` on Android,
`arm64`, `x86_64` for iOS Simulator on iOS). Many popular
extensions (numpy, Pillow) have no upstream iOS wheels yet, so you'd
need to build them locally.

Don't put `pythonnative` itself in `requirements.txt`; the CLI
bundles the installed copy directly.

## Where do `flex`, `padding`, and `position: "absolute"` actually run?

In Python. PythonNative ships its own pure-Python flexbox engine
(`pythonnative.layout`) and runs it after every commit. The engine produces an absolute frame for every element, and
the reconciler hands those frames to the platform handlers via
`set_frame`. Containers on both platforms are simple
`UIView` / `FrameLayout` instances — there is no `UIStackView` or
`LinearLayout` in the picture, so there is no platform drift between
the two backends. See [Layout engine](../concepts/layout.md) for
details.

## How is state shared across screens?

Two main options:

- [`use_context`][pythonnative.use_context] /
  [`Provider`][pythonnative.Provider] for tree-scoped values
  (themes, current user). The provider sits at the top of the
  navigator and descendants subscribe.
- A plain Python module-level object (a "store") for app-wide,
  long-lived state. Subscribe to changes via your own event bus and
  call `set_state` on a hook to trigger re-renders.

PythonNative doesn't ship a Redux-style store; the
[`use_reducer`][pythonnative.use_reducer] hook covers most cases
without one.

## How do I navigate between screens?

Use [`NavigationContainer`][pythonnative.NavigationContainer] plus one
of [`create_stack_navigator`][pythonnative.create_stack_navigator],
[`create_tab_navigator`][pythonnative.create_tab_navigator], or
[`create_drawer_navigator`][pythonnative.create_drawer_navigator].
From a screen, call [`use_navigation`][pythonnative.use_navigation]
to get an imperative handle (`navigate`, `go_back`, etc.). See the
[Navigation guide](../guides/navigation.md).

## Why hooks instead of class components?

Hooks are smaller (no inheritance), composable (a custom hook is just
a Python function that calls other hooks), and produce simpler diffs.
The React community's experience over the last few years made the
choice straightforward.

## Why function components and not just plain functions?

The `@pn.component` decorator establishes a hook context for the
function call. Without it, hooks have no slot to attach state to and
will raise. The decorator also gives the reconciler a stable
identity for the function so it can keep state across re-renders.

## How do I do animations?

Two strategies, depending on the cadence:

- **State-driven** (e.g., a fade triggered by a button press): keep
  the value in [`use_state`][pythonnative.use_state] and let the
  reconciler push updates. Fine up to a few updates per second.
- **Frame-driven** (e.g., a spring animation at 60Hz): hold a
  reference to the native view via
  [`use_ref`][pythonnative.use_ref] and mutate it directly from a
  display-link or `Choreographer` callback. Going through
  `set_state` for every frame is wasteful.

## Is there async/await support?

Yes. `asyncio.create_task` works, and many native APIs surface as
coroutine-friendly callbacks via small bridge helpers. PythonNative
does not start an event loop for you (Chaquopy/iOS run their own UI
loops); use `asyncio.run` from the entry point or schedule tasks on
the loop your platform integration provides.

## How is this different from Toga, BeeWare, Kivy, Briefcase?

| Tool | Model | Widgets |
|---|---|---|
| **PythonNative** | Declarative components plus reconciler | Real native (`UILabel`, `TextView`) via Chaquopy / rubicon-objc |
| Toga | Imperative widgets | Real native via per-platform backend |
| Kivy | Imperative widgets | Custom OpenGL renderer |
| Briefcase | Packaging only (no widgets) | n/a |

PythonNative also has a built-in `pn` CLI for the
build / install / hot-reload loop, so the equivalent of "Briefcase"
is included.

## Where do I file bugs and feature requests?

[GitHub issues](https://github.com/pythonnative/pythonnative/issues).
Smaller fixes and docs improvements are welcome as pull requests
without a prior issue. See [Contributing](contributing.md).

## Next steps

- Walk through your first app: [Getting started](../getting-started.md).
- Read the runtime model: [Mental model](../concepts/mental-model.md).
- Browse the API: [Package overview](../api/pythonnative.md).
