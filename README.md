<p align="center">
  <img src="docs/assets/banner.jpg" alt="PythonNative" width="800" />
</p>

<p align="center">
  <em>Build native Android and iOS apps in Python.</em>
</p>

<p align="center">
  <a href="https://github.com/pythonnative/pythonnative/actions/workflows/ci.yml"><img src="https://github.com/pythonnative/pythonnative/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/pythonnative/pythonnative/actions/workflows/release.yml"><img src="https://github.com/pythonnative/pythonnative/actions/workflows/release.yml/badge.svg" alt="Release" /></a>
  <a href="https://pypi.org/project/pythonnative/"><img src="https://img.shields.io/pypi/v/pythonnative" alt="PyPI Version" /></a>
  <a href="https://pypi.org/project/pythonnative/"><img src="https://img.shields.io/pypi/pyversions/pythonnative" alt="Python Versions" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/pythonnative" alt="License: MIT" /></a>
  <a href="https://pythonnative.com/"><img src="https://img.shields.io/website?url=https%3A%2F%2Fpythonnative.com&label=docs" alt="Docs" /></a>
</p>

<p align="center">
  <a href="https://pythonnative.com/">Documentation</a> ·
  <a href="https://pythonnative.com/getting-started/">Getting Started</a> ·
  <a href="https://pythonnative.com/examples/">Examples</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## Overview

PythonNative is a cross-platform toolkit for building native Android and iOS apps in Python. It provides a **declarative, React-like component model** with hooks and automatic reconciliation on top of a **native rendering core** written in Swift and Kotlin. Write function components with `use_state`, `use_effect`, and friends, just like React, and let PythonNative handle creating and updating native views.

## Features

- **Declarative UI:** Describe *what* your UI should look like with element functions (`Text`, `Button`, `Column`, `Row`, etc.). PythonNative creates and updates native views automatically.
- **Rich component library:** 25+ built-in components backed by real native widgets: `TextInput`, `Image` / `ImageBackground`, `ScrollView`, `FlatList` / `SectionList`, `Modal`, `Pressable` / `TouchableOpacity`, `Switch` / `Checkbox`, `Slider`, `SegmentedControl`, `Picker`, `DatePicker`, `ProgressBar` / `ActivityIndicator`, `WebView`, and more.
- **Device APIs:** Cross-platform modules for `Camera`, `Location`, `FileSystem`, `Notifications`, `Clipboard`, `Share`, `Linking`, `Permissions`, `AppState`, `NetInfo`, `SecureStore`, `Battery`, `Haptics` / `Vibration`, and `Biometrics`, plus reactive `use_app_state` and `use_net_info` hooks.
- **Hooks and function components:** Manage state with `use_state`, side effects with `use_effect` / `use_layout_effect`, refs and imperative handles with `use_ref` / `use_imperative_handle`, and navigation with `use_navigation`, all through one consistent pattern. Components can return a single element, a list of siblings, or `None`, and `Fragment`, `Portal`, and reactive `Provider` context work the way they do in React.
- **Async-first rendering:** One `asyncio` event loop runs the whole framework on the platform's main thread. Components can be `async def` and `await` data directly in the body; `Suspense` boundaries show declarative loading states while they wait. `use_resource` fetches during render, `use_effect` accepts coroutine callbacks (cancelled automatically on unmount), `lazy` code-splits components, and `use_transition` / `use_deferred_value` keep the UI responsive during expensive updates.
- **Developer feedback that finds your bugs:** In dev mode (`pn start`, `pn preview`, debug builds from `pn run`, or `PN_DEV=1`), uncaught errors from renders, effects, and event handlers show a full-screen RedBox with the traceback; unknown style keys and duplicate list keys print "did you mean" warnings; and conditional hooks raise a `HookOrderError` at the source instead of silently cross-wiring state.
- **Typed `style` prop and theme:** Pass all visual and layout properties through a single `style` dict, fully described by the `pn.Style` `TypedDict` and the ergonomic `pn.style(...)` helper for IDE autocomplete and static checking. Compose reusable styles with `StyleSheet`, and read design tokens from a typed, immutable `pn.Theme` via `use_theme()` that follows light and dark mode by default.
- **Cross-platform flexbox engine:** A pure-Python, Yoga-style layout engine computes frames once and applies them to native views, so `flex`, `padding`, `aspect_ratio`, and `position: "absolute"` produce the same geometry on Android and iOS.
- **Virtual view tree + reconciler:** Element trees are diffed and patched with minimal native mutations, similar to React's reconciliation. Each commit lands as **one batched transaction** of mutation ops, and event callbacks are routed through a tag-based registry so re-renders that only change closures cost zero native calls. State updates re-render **locally**: only the component whose state changed (and its subtree) re-runs, and unchanged leaves reuse cached intrinsic measurements, so deep UIs stay responsive instead of re-rendering the whole app from the root on every tap.
- **Native-driven animations:** The `Animated` API (timing / spring / decay / loop / stagger, awaitable or fire-and-forget) hands animations to Core Animation and `ViewPropertyAnimator` whenever possible, so no Python code runs per frame; a pure-Python ticker covers the rest. `interpolate`, arithmetic operators on animated nodes, `Animated.event` scroll binding, and `diff_clamp` cover the scroll-driven patterns (collapsing headers, parallax) that define native feel.
- **Native gesture system:** Attach `Tap`, `LongPress`, `Pan`, `Swipe`, `Fling`, `Pinch`, and `Rotation` recognizers to any view via the `gestures=` prop, backed by `UIGestureRecognizer` on iOS and a unit-testable pure-Python arbiter on Android and in the browser preview. Compose them with `Race`, `Exclusive`, and `Simultaneous` for cross-gesture arbitration (single vs. double tap, drag vs. long press).
- **Virtualized lists:** `FlatList` / `SectionList` window their rows in Python over the platform scroll view: uniform, exact, or measured variable heights, grids, headers/footers, infinite scroll, and an imperative scroll controller, identical on every platform.
- **Native rendering core:** each commit is one serialized transaction applied by Swift and Kotlin component managers, the same shape as React Native's Fabric. Device APIs are native modules registered by name (TurboModules-style), callable from thin Python facades.
- **Custom-component SDK:** Wrap any platform widget as a first-class element with type-checked props via `pythonnative.sdk` (`Props`, `@native_component`, `element_factory`). Plugins distributed on PyPI auto-register through the `pythonnative.handlers` entry-point group.
- **Metro-style dev loop:** `pn start` runs one dev server that serves the browser preview and every connected debug build. Save a file and each client Fast Refreshes in place, keeping component state; their `print` output and tracebacks stream back into the same terminal. `pn run android` / `pn run ios` bakes the server URL into a debug build and rebuilds the native project only when a native input actually changed, so relaunching after a Python edit takes seconds, not minutes.
- **PyPI packages, binary wheels included:** List requirements in `pythonnative.toml` and the CLI resolves them for the *device* (iOS wheels via PEP 730 and BeeWare's index, Android wheels via PEP 738 and Chaquopy), bundling numpy, Pillow, cryptography, and friends alongside pure-Python packages. `pn deps` reports what each target resolves to before you build, and a weekly-checked compatibility matrix keeps the docs honest.
- **Browser preview:** `pn preview` renders your app in a browser tab inside a phone frame (pick a device, rotate, toggle dark mode) with Fast Refresh on every save. The page is a bridge peer exactly like the Swift and Kotlin runtimes, so the reconciler, hooks, layout engine, navigation, and screen host are the same code that ships to the phone; only the leaf widgets are DOM elements.
- **Native-backed navigation:** Declarative `Stack`, `Tab`, and `Drawer` navigators inspired by React Navigation. The root stack drives the platform's native navigation controller (`UINavigationController` on iOS, AndroidX Navigation Component on Android), so transitions, back gestures, and the hardware back button match what users expect; `use_back_handler` intercepts the back action when a screen needs to.
- **Dev client:** Build a shell app once with `pn run ios --dev-client` and point it at any project's dev server from a connect screen, the way Expo Go does; physical phones on the same Wi-Fi get the same Fast Refresh as simulators.
- **Bundled templates:** Android Gradle and iOS Xcode templates are included, so scaffolding requires no network access.

## Quick Start

### Installation

Requires Python 3.13 or newer.

```bash
pip install pythonnative
```

### Usage

```python
import pythonnative as pn


@pn.component
def App():
    count, set_count = pn.use_state(0)
    return pn.Column(
        pn.Text(f"Count: {count}", style=pn.style(font_size=24, bold=True)),
        pn.Button(
            "Tap me",
            on_press=lambda: set_count(count + 1),
        ),
        style=pn.style(spacing=12, padding=16),
    )
```

### Develop

```bash
pn init my-app && cd my-app
pn preview          # dev server + browser preview with Fast Refresh
pn run ios          # in another terminal: debug build that connects to the same server
pn run android
pn build ios        # standalone release artifacts
```

## Documentation

Visit [pythonnative.com](https://pythonnative.com/) for the full documentation, including getting started guides, platform-specific instructions for Android and iOS, API reference, and working examples.

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding standards, and guidelines for submitting pull requests.

## License

[MIT](LICENSE)
