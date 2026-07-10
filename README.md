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

PythonNative is a cross-platform toolkit for building native Android and iOS apps in Python. It provides a **declarative, React-like component model** with hooks and automatic reconciliation, powered by Chaquopy on Android and rubicon-objc on iOS. Write function components with `use_state`, `use_effect`, and friends, just like React, and let PythonNative handle creating and updating native views.

## Features

- **Declarative UI:** Describe *what* your UI should look like with element functions (`Text`, `Button`, `Column`, `Row`, etc.). PythonNative creates and updates native views automatically.
- **Rich component library:** 25+ built-in components backed by real native widgets: `TextInput`, `Image` / `ImageBackground`, `ScrollView`, `FlatList` / `SectionList`, `Modal`, `Pressable` / `TouchableOpacity`, `Switch` / `Checkbox`, `Slider`, `SegmentedControl`, `Picker`, `DatePicker`, `ProgressBar` / `ActivityIndicator`, `WebView`, and more.
- **Device APIs:** Cross-platform modules for `Camera`, `Location`, `FileSystem`, `Notifications`, `Clipboard`, `Share`, `Linking`, `Permissions`, `AppState`, `NetInfo`, `SecureStore`, `Battery`, `Haptics` / `Vibration`, and `Biometrics`, plus reactive `use_app_state` and `use_net_info` hooks.
- **Hooks and function components:** Manage state with `use_state`, side effects with `use_effect` / `use_layout_effect`, refs and imperative handles with `use_ref` / `use_imperative_handle`, and navigation with `use_navigation`, all through one consistent pattern. Components can return a single element, a list of siblings, or `None`, and `Fragment`, `Portal`, and reactive `Provider` context work the way they do in React.
- **Developer feedback that finds your bugs:** In dev mode (`pn preview`, hot reload, or `PN_DEV=1`), uncaught errors from renders, effects, and event handlers show a full-screen RedBox with the traceback; unknown style keys and duplicate list keys print "did you mean" warnings; and conditional hooks raise a `HookOrderError` at the source instead of silently cross-wiring state.
- **Typed `style` prop:** Pass all visual and layout properties through a single `style` dict, fully described by the `pn.Style` `TypedDict` and the ergonomic `pn.style(...)` helper for IDE autocomplete and static checking. Compose reusable styles with `StyleSheet`.
- **Cross-platform flexbox engine:** A pure-Python, Yoga-style layout engine computes frames once and applies them to native views, so `flex`, `padding`, `aspect_ratio`, and `position: "absolute"` produce the same geometry on Android and iOS.
- **Virtual view tree + reconciler:** Element trees are diffed and patched with minimal native mutations, similar to React's reconciliation. Each commit lands as **one batched transaction** of mutation ops, and event callbacks are routed through a tag-based registry so re-renders that only change closures cost zero native calls. State updates re-render **locally**: only the component whose state changed (and its subtree) re-runs, and unchanged leaves reuse cached intrinsic measurements, so deep UIs stay responsive instead of re-rendering the whole app from the root on every tap.
- **Native-driven animations:** The `Animated` API (timing / spring / decay, awaitable or fire-and-forget) hands animations to Core Animation and `ViewPropertyAnimator` whenever possible, so no Python code runs per frame; a pure-Python ticker covers the rest.
- **Native gesture system:** Attach `Tap`, `LongPress`, `Pan`, `Swipe`, `Pinch`, and `Rotation` recognizers to any view via the `gestures=` prop, backed by `UIGestureRecognizer` on iOS and a unit-testable pure-Python arbiter on Android and desktop.
- **Virtualized lists:** `FlatList` / `SectionList` window their rows in Python over the platform scroll view: uniform, exact, or measured variable heights, grids, headers/footers, infinite scroll, and an imperative scroll controller, identical on every platform.
- **Direct native bindings:** Python calls platform APIs directly through Chaquopy and rubicon-objc, with no JavaScript bridge.
- **Custom-component SDK:** Wrap any platform widget as a first-class element with type-checked props via `pythonnative.sdk` (`Props`, `@native_component`, `element_factory`). Plugins distributed on PyPI auto-register through the `pythonnative.handlers` entry-point group.
- **CLI scaffolding:** `pn init` creates a ready-to-run project; `pn run android` and `pn run ios` build and launch your app.
- **Instant desktop preview:** `pn preview` renders your app in a native desktop window via Tkinter with Fast Refresh on every save: iterate on layout, state, and navigation in milliseconds without booting a simulator or device. The reconciler, hooks, layout engine, and navigation are the same code that ships to the phone.
- **Native-backed navigation:** Declarative `Stack`, `Tab`, and `Drawer` navigators inspired by React Navigation. The root stack drives the platform's native navigation controller (`UINavigationController` on iOS, AndroidX Navigation Component on Android), so transitions, back gestures, and the hardware back button match what users expect; `use_back_handler` intercepts the back action when a screen needs to.
- **Fast Refresh hot reload:** `pn run --hot-reload` watches `app/` and patches edits into the running app on save, preserving component state across most changes.
- **Bundled templates:** Android Gradle and iOS Xcode templates are included, so scaffolding requires no network access.

## Quick Start

### Installation

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

## Documentation

Visit [pythonnative.com](https://pythonnative.com/) for the full documentation, including getting started guides, platform-specific instructions for Android and iOS, API reference, and working examples.

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding standards, and guidelines for submitting pull requests.

## License

[MIT](LICENSE)
